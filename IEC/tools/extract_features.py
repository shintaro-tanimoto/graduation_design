#!/usr/bin/env python3
"""
extract_features.py - Feature Extraction for Preference Learning

Extracts numerical feature vectors from genotype (meta_*.json) for
machine learning models.

Usage:
    python extract_features.py meta_A.json
    python extract_features.py meta_A.json --verbose
"""

import sys
import os
import json
import argparse
import numpy as np
from scipy.spatial import distance_matrix

# Import XY-pair computation from generate_pair.py
sys.path.insert(0, os.path.dirname(__file__))
try:
    from generate_pair import compute_pair_metrics
except ImportError:
    # Fallback: define a minimal version if import fails
    def compute_pair_metrics(points, tolerance=1.0):
        return {
            'xy_pair_count': 0,
            'mean_pair_dz': 0.0,
            'std_pair_dz': 0.0,
            'max_pair_dz': 0.0,
            'min_pair_dz': 0.0
        }


# ===== Configuration =====

# Bounding box (must match generate_pair.py)
BBOX_MIN = np.array([0.0, 0.0, -200.0])
BBOX_MAX = np.array([800.0, 700.0, 400.0])
BBOX_VOLUME = (BBOX_MAX[0] - BBOX_MIN[0]) * \
              (BBOX_MAX[1] - BBOX_MIN[1]) * \
              (BBOX_MAX[2] - BBOX_MIN[2])


# ===== Feature Extraction Functions =====

def load_genotype(meta_path):
    """
    Load genotype from JSON file.

    Returns:
        points: (N, 3) array
        weights: (N,) array
        metadata: dict
    """
    with open(meta_path, 'r') as f:
        data = json.load(f)

    points = np.array([p['position'] for p in data['points']])
    weights = np.array([p['weight'] for p in data['points']])
    metadata = data.get('metadata', {})

    return points, weights, metadata


def estimate_cell_volumes(weights, bbox_volume=BBOX_VOLUME, alpha=1.5):
    """
    Estimate cell volumes from weights using power-law heuristic.

    Formula: Vi = bbox_volume × (wi^α / Σ(wj^α))

    Args:
        weights: (N,) array of point weights
        bbox_volume: Total bounding box volume [mm³]
        alpha: Scaling exponent (1.5 for 3D empirical optimum)

    Returns:
        estimated_volumes: (N,) array of estimated volumes [mm³]
    """
    # Apply power-law scaling
    weighted_powers = weights ** alpha

    # Normalize to sum = 1
    relative_volumes = weighted_powers / weighted_powers.sum()

    # Scale to bounding box volume
    estimated_volumes = relative_volumes * bbox_volume

    return estimated_volumes


def compute_point_density_features(points):
    """
    Compute point spacing/density features.

    Returns:
        density_mean: Average nearest-neighbor distance
        density_std: Std of nearest-neighbor distances
    """
    if len(points) < 2:
        return 0.0, 0.0

    # Compute pairwise distances
    dist_matrix = distance_matrix(points, points)

    # For each point, find nearest neighbor (exclude self)
    np.fill_diagonal(dist_matrix, np.inf)
    nearest_distances = dist_matrix.min(axis=1)

    density_mean = nearest_distances.mean()
    density_std = nearest_distances.std()

    return density_mean, density_std


def compute_centrality_features(points, bbox_min=BBOX_MIN, bbox_max=BBOX_MAX):
    """
    Compute spatial distribution features.

    Returns:
        centrality_mean: Average distance to bbox center
        boundary_proximity: Average distance to nearest boundary
    """
    # Bounding box center
    bbox_center = (bbox_min + bbox_max) / 2.0

    # Distance to center
    distances_to_center = np.linalg.norm(points - bbox_center, axis=1)
    centrality_mean = distances_to_center.mean()

    # Distance to nearest boundary (for each axis)
    boundary_distances = []
    for i in range(3):  # x, y, z
        dist_to_min = np.abs(points[:, i] - bbox_min[i])
        dist_to_max = np.abs(points[:, i] - bbox_max[i])
        nearest_boundary = np.minimum(dist_to_min, dist_to_max)
        boundary_distances.append(nearest_boundary)

    boundary_distances = np.array(boundary_distances).T  # (N, 3)
    boundary_proximity = boundary_distances.min(axis=1).mean()  # Closest boundary per point

    return centrality_mean, boundary_proximity


def extract_features(meta_path, verbose=False, include_volume=False):
    """
    Extract feature vector from genotype.

    Args:
        meta_path: Path to meta_*.json file
        verbose: Print detailed breakdown
        include_volume: Include volume estimation features (default: False)

    Returns:
        features: dict with feature values
        feature_vector: np.array for ML models
            - 13 dimensions (without volume)
            - 17 dimensions (with volume)
    """
    # Load genotype
    points, weights, metadata = load_genotype(meta_path)

    n_points = len(points)

    # === Basic Weight Features ===
    weight_mean = weights.mean()
    weight_std = weights.std()
    weight_min = weights.min()
    weight_max = weights.max()
    weight_range = weight_max - weight_min

    # === Point Density Features ===
    density_mean, density_std = compute_point_density_features(points)

    # === Centrality Features ===
    centrality_mean, boundary_proximity = compute_centrality_features(points)

    # === XY-Pair Features ===
    # Try to get from metadata first, otherwise compute directly
    xy_metrics = metadata.get('metrics', {})
    if 'xy_pair_count' in xy_metrics and 'std_pair_dz' in xy_metrics:
        # Use metadata if all required fields are present
        xy_pair_count = xy_metrics['xy_pair_count']
        mean_pair_dz = xy_metrics.get('mean_pair_dz', 0.0)
        std_pair_dz = xy_metrics['std_pair_dz']
    else:
        # Compute directly from points (for older metadata without std_pair_dz)
        xy_metrics_computed = compute_pair_metrics(points)
        xy_pair_count = xy_metrics_computed['xy_pair_count']
        mean_pair_dz = xy_metrics_computed['mean_pair_dz']
        std_pair_dz = xy_metrics_computed['std_pair_dz']

    # === Assemble Feature Dictionary (Basic Features Only) ===
    features = {
        # Basic (5)
        'n_points': n_points,
        'weight_mean': weight_mean,
        'weight_std': weight_std,
        'weight_min': weight_min,
        'weight_max': weight_max,

        # Density (2)
        'point_density_mean': density_mean,
        'point_density_std': density_std,

        # Spatial (2)
        'centrality_mean': centrality_mean,
        'boundary_proximity': boundary_proximity,

        # Derived (1)
        'weight_range': weight_range,

        # XY-Pair (3)
        'xy_pair_count': xy_pair_count,
        'mean_pair_dz': mean_pair_dz,
        'std_pair_dz': std_pair_dz,
    }

    # Convert to feature vector (fixed order)
    feature_vector = np.array([
        features['n_points'],
        features['weight_mean'],
        features['weight_std'],
        features['weight_min'],
        features['weight_max'],
        features['point_density_mean'],
        features['point_density_std'],
        features['centrality_mean'],
        features['boundary_proximity'],
        features['weight_range'],
        features['xy_pair_count'],
        features['mean_pair_dz'],
        features['std_pair_dz'],
    ])

    # === Optional: Volume Features ===
    if include_volume:
        estimated_volumes = estimate_cell_volumes(weights)
        volume_mean = estimated_volumes.mean()
        volume_max = estimated_volumes.max()
        volume_std = estimated_volumes.std()
        volume_cv = volume_std / volume_mean if volume_mean > 0 else 0.0

        # Add to features dict
        features.update({
            'volume_mean': volume_mean,
            'volume_max': volume_max,
            'volume_std': volume_std,
            'volume_cv': volume_cv,
        })

        # Extend feature vector
        feature_vector = np.append(feature_vector, [
            volume_mean,
            volume_max,
            volume_std,
            volume_cv,
        ])

    # === Verbose Output ===
    if verbose:
        print(f"Feature extraction from: {os.path.basename(meta_path)}")
        print(f"  Points: {n_points}")
        print(f"\nWeight Features:")
        print(f"  Mean:  {weight_mean:.2f} mm")
        print(f"  Std:   {weight_std:.2f} mm")
        print(f"  Range: [{weight_min:.2f}, {weight_max:.2f}] mm")
        print(f"\nDensity Features:")
        print(f"  Avg spacing: {density_mean:.2f} mm")
        print(f"  Spacing std: {density_std:.2f} mm")
        print(f"\nSpatial Features:")
        print(f"  Centrality:  {centrality_mean:.2f} mm")
        print(f"  Boundary proximity: {boundary_proximity:.2f} mm")
        print(f"\nXY-Pair Features:")
        print(f"  Pair count:  {xy_pair_count}")
        print(f"  Mean dz:     {mean_pair_dz:.2f} mm")
        print(f"  Std dz:      {std_pair_dz:.2f} mm")

        if include_volume:
            print(f"\nEstimated Volume Features:")
            print(f"  Mean volume: {features['volume_mean']:.0f} mm³")
            print(f"  Max volume:  {features['volume_max']:.0f} mm³")
            print(f"  Volume std:  {features['volume_std']:.0f} mm³")
            print(f"  Volume CV:   {features['volume_cv']:.3f}")

        print(f"\nFeature vector shape: {feature_vector.shape}")

    return features, feature_vector


def extract_features_from_genotype(points, weights, include_volume=False):
    """
    Extract features directly from points and weights arrays.
    (Used when genotype is already loaded in memory)

    Args:
        points: (N, 3) array
        weights: (N,) array
        include_volume: Include volume estimation features (default: False)

    Returns:
        feature_vector: np.array (13,) or (17,) depending on include_volume
    """
    n_points = len(points)

    # Weight features
    weight_mean = weights.mean()
    weight_std = weights.std()
    weight_min = weights.min()
    weight_max = weights.max()
    weight_range = weight_max - weight_min

    # Density features
    density_mean, density_std = compute_point_density_features(points)

    # Centrality features
    centrality_mean, boundary_proximity = compute_centrality_features(points)

    # XY-Pair features
    xy_metrics = compute_pair_metrics(points)
    xy_pair_count = xy_metrics['xy_pair_count']
    mean_pair_dz = xy_metrics['mean_pair_dz']
    std_pair_dz = xy_metrics['std_pair_dz']

    # Assemble vector (basic features)
    feature_vector = np.array([
        n_points,
        weight_mean,
        weight_std,
        weight_min,
        weight_max,
        density_mean,
        density_std,
        centrality_mean,
        boundary_proximity,
        weight_range,
        xy_pair_count,
        mean_pair_dz,
        std_pair_dz,
    ])

    # Optional: Volume features
    if include_volume:
        estimated_volumes = estimate_cell_volumes(weights)
        volume_mean = estimated_volumes.mean()
        volume_max = estimated_volumes.max()
        volume_std = estimated_volumes.std()
        volume_cv = volume_std / volume_mean if volume_mean > 0 else 0.0

        feature_vector = np.append(feature_vector, [
            volume_mean,
            volume_max,
            volume_std,
            volume_cv,
        ])

    return feature_vector


# ===== CLI Interface =====

def main():
    parser = argparse.ArgumentParser(
        description='Extract feature vector from genotype'
    )
    parser.add_argument('meta_path', type=str,
                       help='Path to meta_*.json file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Print detailed feature breakdown')
    parser.add_argument('--include-volume', action='store_true',
                       help='Include volume estimation features (adds 4 dimensions)')
    parser.add_argument('--output', '-o', type=str,
                       help='Save feature vector to file (optional)')

    args = parser.parse_args()

    # Extract features
    features, feature_vector = extract_features(
        args.meta_path,
        verbose=args.verbose,
        include_volume=args.include_volume
    )

    # Print feature vector
    if not args.verbose:
        print("Feature vector:")
        print(feature_vector)

    # Save to file if requested
    if args.output:
        np.save(args.output, feature_vector)
        print(f"\nSaved feature vector to: {args.output}")


if __name__ == '__main__':
    main()
