#!/usr/bin/env python3
"""
generate_pair.py - Interactive Evolutionary Computation - Form Generator

Generates two candidate forms (A and B) for human preference selection.
Uses 3D weighted Voronoi diagrams (power diagrams) as phenotype.

Usage:
    python generate_pair.py --init              # Generate random initial pair
    python generate_pair.py --parent meta_A.json   # Generate pair from parent
"""

import sys
import os
import json
import argparse
import hashlib
import random
from datetime import datetime

import numpy as np
from scipy.spatial.distance import pdist, squareform

# Import the Laguerre Voronoi module from parent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from LaguerreVoronoi import compute_power_diagram


# ===== Evolution Parameters =====
# Architectural scale: 800mm x 700mm x 400mm bounding box
DEFAULT_PARAMS = {
    'n_points': 10,              # Initial number of points (excluding fixed points)
    'pos_mutation_sigma': 30.0,  # Position perturbation std (mm)
    'weight_mutation_sigma': 10.0, # Weight perturbation std
    'add_point_prob': 0.1,       # Probability to add new point
    'remove_point_prob': 0.1,    # Probability to remove point
    'bounds_min': [0.0, 0.0, -50.0],      # Fixed bounding box (mm)
    'bounds_max': [800.0, 700.0, 400.0], # Fixed bounding box (mm)
    'weight_min': 10.0,          # Minimum weight (mm)
    'weight_max': 50.0,         # Maximum weight (mm)
}

# Fixed points that must always be included and never modified
FIXED_POINTS = np.array([
    [400.0, 350.0, 200.0],
    [400.0, 350.0, -50.0],
])

FIXED_WEIGHTS = np.array([100.0, 100.0])

# ===== Iteration Counter Management =====
# Tracks generation number for hybrid active learning strategy

ITERATION_COUNTER_FILE = 'log/iteration_counter.txt'


def load_iteration_counter():
    """
    Load current iteration/generation number.

    Returns:
        int: Current iteration number (0 if file doesn't exist)
    """
    if os.path.exists(ITERATION_COUNTER_FILE):
        try:
            with open(ITERATION_COUNTER_FILE, 'r') as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            return 0
    return 0


def increment_iteration_counter():
    """
    Increment iteration counter and save to file.

    Returns:
        int: New iteration number after increment
    """
    current = load_iteration_counter()
    new_value = current + 1

    os.makedirs(os.path.dirname(ITERATION_COUNTER_FILE), exist_ok=True)
    with open(ITERATION_COUNTER_FILE, 'w') as f:
        f.write(str(new_value))

    return new_value


# ===== Genotype I/O =====

def save_genotype(points, weights, filepath, parent_hash=None, iteration=0, crossover_info=None, params=None, generation_params=None):
    """
    Save genotype to JSON file with XY-pair metrics.

    Args:
        points: (N, 3) array of positions
        weights: (N,) array of weights
        filepath: output JSON path
        parent_hash: hash of parent genotype (None for initial generation)
        iteration: generation number
        crossover_info: dict with crossover metadata (None if mutation was used)
        params: dict of generation parameters (n_points, target_pairs, mutation sigmas, etc.)
        generation_params: dict of runtime generation parameters (actual_pairs, z_alignment_count, z_alignment_rate)
    """
    genotype = {
        'points': [
            {
                'position': [float(p[0]), float(p[1]), float(p[2])],
                'weight': float(w)
            }
            for p, w in zip(points, weights)
        ],
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'iteration': iteration,
            'parent_hash': parent_hash,
            'n_points': len(points),
            'hash': compute_genotype_hash(points, weights)
        }
    }

    # Add XY-pair metrics
    pair_metrics = compute_pair_metrics(points, tolerance=1.0)
    genotype['metadata']['metrics'] = pair_metrics

    # Add crossover info if available
    if crossover_info is not None:
        genotype['metadata']['crossover_info'] = crossover_info

    # Add generation configuration (for parameter inheritance)
    if params is not None:
        genotype['metadata']['generation_config'] = {
            'n_points': params.get('n_points', DEFAULT_PARAMS['n_points']),
            'target_pairs': params.get('target_pairs', 0),
            'pos_mutation_sigma': params.get('pos_mutation_sigma', DEFAULT_PARAMS['pos_mutation_sigma']),
            'weight_mutation_sigma': params.get('weight_mutation_sigma', DEFAULT_PARAMS['weight_mutation_sigma']),
            'add_point_prob': params.get('add_point_prob', DEFAULT_PARAMS['add_point_prob']),
            'remove_point_prob': params.get('remove_point_prob', DEFAULT_PARAMS['remove_point_prob']),
        }

    # Add runtime generation parameters
    if generation_params is not None:
        genotype['metadata']['generation_params'] = generation_params

    with open(filepath, 'w') as f:
        json.dump(genotype, f, indent=2)

    return genotype['metadata']['hash']


def load_genotype(filepath):
    """
    Load genotype from JSON file.

    Returns:
        points: (N, 3) array
        weights: (N,) array
        metadata: dict
        generation_config: dict (generation parameters for inheritance)
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    points = np.array([p['position'] for p in data['points']])
    weights = np.array([p['weight'] for p in data['points']])
    metadata = data.get('metadata', {})

    # Load generation configuration (with backward compatibility)
    generation_config = metadata.get('generation_config')
    if generation_config is None:
        # Legacy metadata - create default config by deriving from actual count
        actual_n_points = metadata.get('n_points', 10)
        generation_config = {
            'n_points': max(0, actual_n_points - 2),  # Subtract fixed points
            'target_pairs': 0,  # Unknown, assume 0
            'pos_mutation_sigma': DEFAULT_PARAMS['pos_mutation_sigma'],
            'weight_mutation_sigma': DEFAULT_PARAMS['weight_mutation_sigma'],
            'add_point_prob': DEFAULT_PARAMS['add_point_prob'],
            'remove_point_prob': DEFAULT_PARAMS['remove_point_prob'],
        }

    return points, weights, metadata, generation_config


def compute_genotype_hash(points, weights):
    """Compute deterministic hash of genotype for tracking lineage."""
    data = np.concatenate([points.flatten(), weights])
    hash_input = ','.join(f'{x:.6f}' for x in data)
    return hashlib.md5(hash_input.encode()).hexdigest()[:8]


# ===== XY-Pair Detection and Metrics =====

def detect_xy_clusters(points, tolerance=1.0):
    """
    Detect XY-aligned point clusters (points sharing same (x,y) coordinates).

    Args:
        points: (N, 3) array of point positions
        tolerance: XY distance tolerance in mm (default: 1.0mm)

    Returns:
        clusters: List of point index lists
            Example: [[0, 5], [2, 7, 9]]
                     - Cluster 0: points 0 and 5 share same XY
                     - Cluster 1: points 2, 7, 9 share same XY

    Algorithm:
        1. Extract XY coordinates: xy = points[:, :2]
        2. Compute pairwise XY distances
        3. Group points where distance < tolerance
        4. Return only clusters with size ≥ 2 (ignore singletons)
    """
    if len(points) < 2:
        return []

    xy = points[:, :2]  # Extract (x, y) coordinates
    dist_matrix = squareform(pdist(xy))  # Pairwise XY distances

    clusters = []
    visited = set()

    for i in range(len(points)):
        if i in visited:
            continue

        # Find all points within tolerance of point i
        cluster_indices = np.where(dist_matrix[i] < tolerance)[0].tolist()

        if len(cluster_indices) >= 2:
            clusters.append(cluster_indices)
            visited.update(cluster_indices)

    return clusters


def count_xy_pairs(points, tolerance=1.0):
    """
    Count number of XY-pairs (clusters with ≥ 2 points).

    Returns:
        pair_count: Number of XY clusters
    """
    clusters = detect_xy_clusters(points, tolerance)
    return len(clusters)


def compute_pair_metrics(points, tolerance=1.0):
    """
    Compute XY-pair structural metrics for logging.

    Args:
        points: (N, 3) array of positions
        tolerance: XY clustering tolerance (mm)

    Returns:
        metrics: dict with keys:
            - xy_pair_count: Number of XY-aligned clusters
            - mean_pair_dz: Average vertical range within pairs (mm)
            - std_pair_dz: Std dev of vertical range within pairs (mm)
            - max_pair_dz: Maximum vertical range among all pairs (mm)
            - min_pair_dz: Minimum vertical range among all pairs (mm)

    Metric Definition:
        - For each XY cluster (size ≥ 2):
            dz_cluster = max(z) - min(z)
        - mean_pair_dz = average(dz_cluster over all clusters)
        - std_pair_dz = std(dz_cluster over all clusters)
        - If no pairs exist: all metrics = 0.0
    """
    clusters = detect_xy_clusters(points, tolerance)

    if len(clusters) == 0:
        return {
            'xy_pair_count': 0,
            'mean_pair_dz': 0.0,
            'std_pair_dz': 0.0,
            'max_pair_dz': 0.0,
            'min_pair_dz': 0.0
        }

    # Compute dz (vertical range) for each cluster
    dz_values = []
    for cluster_indices in clusters:
        z_coords = points[cluster_indices, 2]  # Extract Z values
        dz = z_coords.max() - z_coords.min()
        dz_values.append(dz)

    dz_values = np.array(dz_values)

    return {
        'xy_pair_count': len(clusters),
        'mean_pair_dz': float(dz_values.mean()),
        'std_pair_dz': float(dz_values.std()),
        'max_pair_dz': float(dz_values.max()),
        'min_pair_dz': float(dz_values.min())
    }


# ===== Mutation Operators =====

def ensure_fixed_points(points, weights):
    """
    Ensure all fixed points are present in the genotype.
    Add missing fixed points if necessary.

    Args:
        points: (N, 3) array
        weights: (N,) array

    Returns:
        points: (N+M, 3) array with fixed points
        weights: (N+M,) array with fixed weights
    """
    points_list = list(points)
    weights_list = list(weights)

    for i, (fixed_pt, fixed_wt) in enumerate(zip(FIXED_POINTS, FIXED_WEIGHTS)):
        # Check if this fixed point already exists
        found = False
        for j, pt in enumerate(points_list):
            if np.allclose(pt, fixed_pt, atol=1e-6):
                # Update weight to fixed weight if different
                weights_list[j] = fixed_wt
                found = True
                break

        # Add fixed point if not found
        if not found:
            points_list.insert(i, fixed_pt)
            weights_list.insert(i, fixed_wt)

    return np.array(points_list), np.array(weights_list)


def is_fixed_point(point, tolerance=1e-6):
    """
    Check if a point is one of the fixed points.

    Args:
        point: (3,) array [x, y, z]
        tolerance: numerical tolerance for comparison

    Returns:
        bool: True if point matches a fixed point
    """
    for fixed_pt in FIXED_POINTS:
        if np.allclose(point, fixed_pt, atol=tolerance):
            return True
    return False


def get_fixed_point_indices(points, tolerance=1e-6):
    """
    Get indices of fixed points in the points array.

    Args:
        points: (N, 3) array
        tolerance: numerical tolerance for comparison

    Returns:
        list of indices that correspond to fixed points
    """
    fixed_indices = []
    for i, point in enumerate(points):
        if is_fixed_point(point, tolerance):
            fixed_indices.append(i)
    return fixed_indices


def is_in_exclusion_zone(point):
    """
    Check if a point is in the exclusion zone.

    Exclusion zone:
    - X: [200, 600]
    - Y: [200, 500]
    - Z: [0, 400]

    Args:
        point: (3,) array [x, y, z]

    Returns:
        bool: True if point is in exclusion zone
    """
    x, y, z = point
    return (200 <= x <= 600) and (200 <= y <= 500) and (0 <= z <= 300)


def generate_point_outside_exclusion(bounds_min, bounds_max, max_attempts=100):
    """
    Generate a random point outside the exclusion zone.
    Z coordinate is always >= 0.

    Args:
        bounds_min: (3,) array of minimum bounds
        bounds_max: (3,) array of maximum bounds
        max_attempts: maximum number of attempts before giving up

    Returns:
        point: (3,) array outside exclusion zone
    """
    for _ in range(max_attempts):
        # Generate X, Y from full bounds, but Z from 0 to max
        x = np.random.uniform(bounds_min[0], bounds_max[0])
        y = np.random.uniform(bounds_min[1], bounds_max[1])
        z = np.random.uniform(0, bounds_max[2])
        point = np.array([x, y, z])

        if not is_in_exclusion_zone(point):
            return point

    # Fallback: force point to be in a safe zone
    # Use corner regions that are definitely outside exclusion
    x = np.random.choice([
        np.random.uniform(bounds_min[0], 200),  # Left side
        np.random.uniform(600, bounds_max[0])   # Right side
    ])
    y = np.random.uniform(bounds_min[1], bounds_max[1])
    z = np.random.uniform(0, bounds_max[2])  # Z always >= 0

    return np.array([x, y, z])


def mutate_position(points, sigma=0.15, bounds_min=None, bounds_max=None, preserve_xy=False):
    """
    Add Gaussian noise to positions and clip to bounds.
    Fixed points are not mutated.

    Args:
        points: (N, 3) array
        sigma: standard deviation of perturbation
        bounds_min, bounds_max: bounding box limits
        preserve_xy: if True, only mutate Z for XY-paired points (preserves pair structure)

    Returns:
        mutated_points: (N, 3) array
    """
    mutated = points.copy()
    fixed_indices = get_fixed_point_indices(points)

    # Detect XY-pairs if preserve_xy is enabled
    if preserve_xy:
        clusters = detect_xy_clusters(points, tolerance=1.0)
        paired_indices = {idx for cluster in clusters for idx in cluster}
    else:
        paired_indices = set()

    # Apply mutation only to non-fixed points
    for i in range(len(points)):
        if i not in fixed_indices:
            if preserve_xy and i in paired_indices:
                # Paired point: mutate Z only
                noise_z = np.random.normal(0, sigma)
                mutated[i][2] = points[i][2] + noise_z
            else:
                # Singleton or preserve_xy=False: mutate XYZ
                noise = np.random.normal(0, sigma, size=3)
                mutated[i] = points[i] + noise

            if bounds_min is not None and bounds_max is not None:
                mutated[i] = np.clip(mutated[i], bounds_min, bounds_max)

    return mutated


def mutate_weight(weights, points, sigma=0.3, weight_min=0.05, weight_max=0.5):
    """
    Add Gaussian noise to weights and clip to valid range.
    Fixed points' weights are not mutated.

    Args:
        weights: (N,) array
        points: (N, 3) array - needed to identify fixed points
        sigma: standard deviation of perturbation
        weight_min, weight_max: weight limits

    Returns:
        mutated_weights: (N,) array
    """
    mutated = weights.copy()
    fixed_indices = get_fixed_point_indices(points)

    # Apply mutation only to non-fixed points
    for i in range(len(weights)):
        if i not in fixed_indices:
            noise = np.random.normal(0, sigma)
            mutated[i] = weights[i] + noise
            mutated[i] = np.clip(mutated[i], weight_min, weight_max)

    return mutated


def mutate_add_point(points, weights, prob=0.1, bounds_min=None, bounds_max=None,
                     weight_min=0.05, weight_max=0.5):
    """
    Randomly add a new point with given probability.
    New point will be outside the exclusion zone.

    Returns:
        points: (N+1, 3) or (N, 3) array
        weights: (N+1,) or (N,) array
        added: bool indicating if point was added
    """
    if np.random.random() > prob:
        return points, weights, False

    # Generate random position outside exclusion zone
    new_pos = generate_point_outside_exclusion(bounds_min, bounds_max)
    new_weight = np.random.uniform(weight_min, weight_max)

    points = np.vstack([points, new_pos])
    weights = np.append(weights, new_weight)

    return points, weights, True


def mutate_remove_point(points, weights, prob=0.1, min_points=3):
    """
    Randomly remove a point with given probability.
    Ensures minimum number of points.
    Fixed points are never removed.

    Returns:
        points: (N-1, 3) or (N, 3) array
        weights: (N-1,) or (N,) array
        removed: bool indicating if point was removed
    """
    if len(points) <= min_points:
        return points, weights, False

    if np.random.random() > prob:
        return points, weights, False

    # Get indices of non-fixed points
    fixed_indices = get_fixed_point_indices(points)
    non_fixed_indices = [i for i in range(len(points)) if i not in fixed_indices]

    # Cannot remove if only fixed points remain
    if len(non_fixed_indices) == 0:
        return points, weights, False

    # Remove random non-fixed point
    idx = np.random.choice(non_fixed_indices)
    points = np.delete(points, idx, axis=0)
    weights = np.delete(weights, idx)

    return points, weights, True


def mutate_xy_structure(points, weights, strategy='NONE', params=DEFAULT_PARAMS):
    """
    Apply XY-structure-aware mutation.

    Strategies:
        'PRESERVE_XY': Keep existing XY-pairs intact (only mutate Z and weights)
        'BREAK_XY': Randomly shift X or Y of some paired points (break pairs)
        'INCREASE_XY': Attempt to create new pairs by aligning XY coords
        'NONE': No XY-specific mutation (pass through)

    Args:
        points: (N, 3) array
        weights: (N,) array
        strategy: XY mutation strategy
        params: mutation parameters (for bounds)

    Returns:
        points_mutated: (N, 3) array
        weights_mutated: (N,) array
    """
    points_out = points.copy()
    weights_out = weights.copy()

    bounds_min = np.array(params['bounds_min'])
    bounds_max = np.array(params['bounds_max'])

    if strategy == 'PRESERVE_XY':
        # Detect existing pairs
        clusters = detect_xy_clusters(points)
        fixed_indices = get_fixed_point_indices(points)

        # For each cluster, keep XY fixed, mutate Z only
        for cluster_indices in clusters:
            for idx in cluster_indices:
                if idx not in fixed_indices:
                    # Mutate Z coordinate only
                    points_out[idx, 2] += np.random.normal(0, 30.0)
                    points_out[idx, 2] = np.clip(points_out[idx, 2],
                                                 bounds_min[2], bounds_max[2])

                    # Mutate weight
                    weights_out[idx] += np.random.normal(0, 10.0)
                    weights_out[idx] = np.clip(weights_out[idx],
                                               params['weight_min'], params['weight_max'])

    elif strategy == 'BREAK_XY':
        # Randomly break some pairs by shifting XY
        clusters = detect_xy_clusters(points)
        fixed_indices = get_fixed_point_indices(points)

        for cluster_indices in clusters:
            # Never break fixed points
            non_fixed_in_cluster = [i for i in cluster_indices if i not in fixed_indices]

            if len(non_fixed_in_cluster) >= 2 and np.random.random() < 0.3:
                # Break this pair: shift one point's XY
                break_idx = np.random.choice(non_fixed_in_cluster)
                shift = np.random.normal(0, 50.0, size=2)  # XY shift
                points_out[break_idx, :2] += shift

                # Clip to bounds
                points_out[break_idx, 0] = np.clip(points_out[break_idx, 0],
                                                   bounds_min[0], bounds_max[0])
                points_out[break_idx, 1] = np.clip(points_out[break_idx, 1],
                                                   bounds_min[1], bounds_max[1])

    elif strategy == 'INCREASE_XY':
        # Try to create new pairs by aligning random points
        clusters = detect_xy_clusters(points)
        fixed_indices = get_fixed_point_indices(points)

        # Get all paired point indices
        paired_set = set()
        for cluster in clusters:
            paired_set.update(cluster)

        # Find non-paired, non-fixed points
        non_paired_indices = [i for i in range(len(points))
                             if i not in paired_set and i not in fixed_indices]

        if len(non_paired_indices) >= 2:
            # Pick 2 random unpaired points, align their XY
            idx1, idx2 = np.random.choice(non_paired_indices, 2, replace=False)

            # Copy XY from idx1 to idx2 (keep Z different)
            points_out[idx2, :2] = points_out[idx1, :2]

    # strategy == 'NONE': no XY-specific mutation

    return points_out, weights_out


def mutate_genotype(points, weights, params=DEFAULT_PARAMS, xy_strategy='NONE'):
    """
    Apply all mutation operators to genotype with optional XY-structure awareness.
    Fixed points are never modified or removed.

    Args:
        points: (N, 3) parent positions
        weights: (N,) parent weights
        params: dict of mutation parameters
        xy_strategy: XY-structure mutation strategy (default: 'NONE')

    Returns:
        new_points: mutated positions
        new_weights: mutated weights
    """
    # Step 1: Apply XY-structure mutation (if specified)
    if xy_strategy != 'NONE':
        points, weights = mutate_xy_structure(points, weights, strategy=xy_strategy, params=params)

    # Step 2: Position mutation (fixed points are preserved)
    # Preserve XY-pairs if xy_strategy is PRESERVE_XY
    preserve_xy = (xy_strategy == 'PRESERVE_XY')

    new_points = mutate_position(
        points.copy(),
        sigma=params['pos_mutation_sigma'],
        bounds_min=np.array(params['bounds_min']),
        bounds_max=np.array(params['bounds_max']),
        preserve_xy=preserve_xy
    )

    # Weight mutation (fixed points' weights are preserved)
    new_weights = mutate_weight(
        weights.copy(),
        new_points,  # Pass points to identify fixed ones
        sigma=params['weight_mutation_sigma'],
        weight_min=params['weight_min'],
        weight_max=params['weight_max']
    )

    # Add point
    new_points, new_weights, added = mutate_add_point(
        new_points, new_weights,
        prob=params['add_point_prob'],
        bounds_min=np.array(params['bounds_min']),
        bounds_max=np.array(params['bounds_max']),
        weight_min=params['weight_min'],
        weight_max=params['weight_max']
    )

    # Remove point (fixed points cannot be removed)
    new_points, new_weights, removed = mutate_remove_point(
        new_points, new_weights,
        prob=params['remove_point_prob']
    )

    return new_points, new_weights


# ===== Adaptive Mutation Strength (Issue 6: Simulated Annealing) =====

def get_adaptive_sigma(base_sigma, iteration, annealing_rate=0.05):
    """
    Exponentially decrease mutation strength over generations.

    This implements simulated annealing: broad exploration early,
    fine-grained refinement later.

    Args:
        base_sigma: Initial mutation strength
        iteration: Current generation number
        annealing_rate: Cooling schedule (typical: 0.01 - 0.1)
                       Higher = faster cooling

    Returns:
        Adaptive sigma for this iteration
    """
    if iteration == 0:
        return base_sigma

    # Exponential decay: sigma_t = sigma_0 * exp(-k * t)
    return base_sigma * np.exp(-annealing_rate * iteration)


# ===== Multi-Candidate Generation (Phase 3: Preference Learning) =====

def scale_mutation_params(params, scale_factor):
    """
    Scale mutation parameters by a factor.

    Args:
        params: Base mutation parameters
        scale_factor: Multiplier (e.g., 0.5 for conservative, 2.0 for bold)

    Returns:
        scaled_params: New parameter dict
    """
    scaled = params.copy()
    scaled['pos_mutation_sigma'] = params['pos_mutation_sigma'] * scale_factor
    scaled['weight_mutation_sigma'] = params['weight_mutation_sigma'] * scale_factor
    return scaled


def generate_many(parent_points, parent_weights, params, iteration, M=100):
    """
    Generate M completely random candidates (parent is ignored).

    NOTE: This function has been changed from mutation-based to completely random generation.
    The parent_points and parent_weights arguments are kept for backward compatibility but are not used.

    Args:
        parent_points: (N, 3) parent positions (UNUSED - kept for compatibility)
        parent_weights: (N,) parent weights (UNUSED - kept for compatibility)
        params: Generation parameters (used for generate_random_genotype)
        iteration: Current iteration (kept for compatibility with selection strategy)
        M: Number of candidates to generate

    Returns:
        candidates: List of dict with keys 'points', 'weights', 'features', 'generation_method'
    """
    from extract_features import extract_features_from_genotype

    candidates = []

    # Use target_pairs from params if available
    target_pairs = params.get('target_pairs', 0)

    for i in range(M):
        # Complete random generation (parent is ignored)
        # Note: target_pairs enables variable pairs, Z-alignment, and role-based point distribution
        points, weights, generation_params = generate_random_genotype(params=params, target_pairs=target_pairs)

        # Extract features (with volume estimation)
        features = extract_features_from_genotype(points, weights, include_volume=True)

        candidates.append({
            'points': points,
            'weights': weights,
            'features': features,
            'generation_method': 'random',  # Debug marker
            'generation_params': generation_params  # Store runtime params
        })

    return candidates


def select_best_pair(candidates, model, scaler, strategy='top_and_uncertain'):
    """
    Use trained preference model to select 2 candidates for human evaluation.

    Strategies:
        'top_2': Two highest predicted scores (pure exploitation)
        'top_and_uncertain': Best + most uncertain (balanced)
        'diverse': Best + most feature-different (exploration)
        'expected_improvement': Best + likely to improve (active learning)
        'uncertainty_sampling': Two most uncertain (maximum learning)

    Args:
        candidates: List of candidate dicts
        model: Trained LogisticRegression model
        scaler: Fitted StandardScaler
        strategy: Selection strategy

    Returns:
        (candidate_A, candidate_B): Two selected candidates
    """
    # Extract features
    features = np.array([c['features'] for c in candidates])

    # Normalize features
    features_scaled = scaler.transform(features)

    # Predict preference scores (probability of being preferred)
    scores = model.predict_proba(features_scaled)[:, 1]  # P(user prefers this)

    if strategy == 'top_2':
        # Simply pick top 2
        top_indices = np.argsort(scores)[-2:]
        return candidates[top_indices[0]], candidates[top_indices[1]]

    elif strategy == 'top_and_uncertain':
        # Exploitation: best candidate
        best_idx = np.argmax(scores)

        # Exploration: most uncertain (score closest to 0.5)
        uncertainty = 1.0 - np.abs(scores - 0.5) * 2  # 1.0 at 0.5, 0.0 at extremes
        uncertainty[best_idx] = -1  # Don't pick same candidate twice
        uncertain_idx = np.argmax(uncertainty)

        # Ensure we don't return the same candidate twice
        if best_idx == uncertain_idx:
            # Pick second-best instead
            scores_copy = scores.copy()
            scores_copy[best_idx] = -np.inf
            uncertain_idx = np.argmax(scores_copy)

        return candidates[best_idx], candidates[uncertain_idx]

    elif strategy == 'diverse':
        # Pick top candidate + most different from it
        best_idx = np.argmax(scores)
        best_features = features[best_idx]

        # Compute feature distances
        distances = np.linalg.norm(features - best_features, axis=1)
        distances[best_idx] = 0  # Don't pick same candidate
        diverse_idx = np.argmax(distances)

        return candidates[best_idx], candidates[diverse_idx]

    elif strategy == 'expected_improvement':
        # Expected Improvement: best + candidate likely to improve upon best
        best_idx = np.argmax(scores)
        best_score = scores[best_idx]

        # Compute improvement potential: score + uncertainty
        uncertainty = 1.0 - np.abs(scores - 0.5) * 2
        improvement = (scores - best_score) + 0.5 * uncertainty
        improvement[best_idx] = -np.inf  # Don't pick same candidate

        ei_idx = np.argmax(improvement)

        return candidates[best_idx], candidates[ei_idx]

    elif strategy == 'uncertainty_sampling':
        # Pure active learning: pick two most uncertain
        uncertainty = 1.0 - np.abs(scores - 0.5) * 2
        top_uncertain_indices = np.argsort(uncertainty)[-2:]

        return candidates[top_uncertain_indices[0]], candidates[top_uncertain_indices[1]]

    else:
        raise ValueError(f"Unknown strategy: {strategy}")


def normalize_meta_features(candidates):
    """
    Extract and normalize meta features from candidates for diversity calculation.

    Args:
        candidates: List of candidate dicts (each with 'features' key)

    Returns:
        normalized: (M, D) array of normalized meta features
    """
    from sklearn.preprocessing import StandardScaler

    # Extract feature matrix
    feature_matrix = []
    for cand in candidates:
        # candidates[i]['features'] is the 17-dim feature vector from extract_features_from_genotype()
        feature_matrix.append(cand['features'])

    feature_matrix = np.array(feature_matrix)  # [M, 17]

    # Normalize with StandardScaler (mean=0, std=1)
    scaler = StandardScaler()
    normalized = scaler.fit_transform(feature_matrix)

    return normalized


def select_best_pair_gnn(candidates, gnn_predictor, strategy='top_and_uncertain', iteration=0):
    """
    Use trained GNN model to select 2 candidates for human evaluation.

    Similar to select_best_pair() but uses GNN predictor instead of sklearn model.

    Args:
        candidates: List of candidate dicts
        gnn_predictor: GNNPredictor instance
        strategy: Selection strategy ('hybrid_active' for new active learning strategy)
        iteration: Current generation number (used for hybrid_active strategy)

    Returns:
        (candidate_A, candidate_B): Two selected candidates
    """
    # Score all candidates using GNN
    scored = gnn_predictor.score_candidates(candidates, verbose=False)

    # Extract scores
    scores = np.array([s for _, s in scored])

    if strategy == 'hybrid_active':
        # New hybrid active learning strategy
        # A: Top score (exploitation)
        # B: Top-K diversity (default) OR uncertainty (every 5 generations)

        TOP_K = 20

        # A案: トップスコア（exploitation）
        best_idx = np.argmax(scores)
        candidate_A = candidates[best_idx]

        # B案: 世代番号で戦略切り替え
        # 5世代ごとに不確実性サンプリング（0, 5, 10, 15, ...）
        use_uncertainty = (iteration > 0 and iteration % 5 == 0)

        if use_uncertainty:
            # 不確実性サンプリング: スコアが0.5に最も近い候補
            uncertainty = 1.0 - np.abs(scores - 0.5) * 2  # [0, 1]
            uncertainty[best_idx] = -1  # A案は除外
            uncertain_idx = np.argmax(uncertainty)
            candidate_B = candidates[uncertain_idx]

            print(f"  [Iteration {iteration}] Strategy: Uncertainty Sampling")
            print(f"  A (best): score={scores[best_idx]:.3f}")
            print(f"  B (uncertain): score={scores[uncertain_idx]:.3f}, uncertainty={uncertainty[uncertain_idx]:.3f}")

        else:
            # Top-K多様性サンプリング
            top_k_indices = np.argsort(scores)[-TOP_K:]  # Top-20のインデックス

            # メタ特徴を正規化
            meta_features = normalize_meta_features(candidates)

            # A案のメタ特徴
            feat_A = meta_features[best_idx]

            # Top-K内でA案と最も距離が遠い候補を選択
            max_distance = -1
            diverse_idx = None

            for idx in top_k_indices:
                if idx == best_idx:
                    continue  # A案自身は除外

                # L2距離
                dist = np.linalg.norm(meta_features[idx] - feat_A)

                if dist > max_distance:
                    max_distance = dist
                    diverse_idx = idx

            if diverse_idx is None:
                # Fallback: pick second best if all top-K are same as best
                scores_copy = scores.copy()
                scores_copy[best_idx] = -np.inf
                diverse_idx = np.argmax(scores_copy)

            candidate_B = candidates[diverse_idx]

            print(f"  [Iteration {iteration}] Strategy: Top-{TOP_K} Diversity")
            print(f"  A (best): score={scores[best_idx]:.3f}")
            print(f"  B (diverse): score={scores[diverse_idx]:.3f}, distance={max_distance:.3f}")

        return candidate_A, candidate_B

    elif strategy == 'top_2':
        # Simply pick top 2
        top_indices = np.argsort(scores)[-2:]
        return candidates[top_indices[0]], candidates[top_indices[1]]

    elif strategy == 'top_and_uncertain':
        # Exploitation: best candidate
        best_idx = np.argmax(scores)

        # Exploration: most uncertain (score closest to 0.5)
        uncertainty = 1.0 - np.abs(scores - 0.5) * 2
        uncertainty[best_idx] = -1
        uncertain_idx = np.argmax(uncertainty)

        if best_idx == uncertain_idx:
            scores_copy = scores.copy()
            scores_copy[best_idx] = -np.inf
            uncertain_idx = np.argmax(scores_copy)

        return candidates[best_idx], candidates[uncertain_idx]

    elif strategy == 'diverse':
        # Exploitation: best candidate
        best_idx = np.argmax(scores)

        # Exploration: feature-wise most different
        # Use GNN scores as proxy for diversity (lowest correlation)
        distances = np.abs(scores - scores[best_idx])
        distances[best_idx] = 0
        diverse_idx = np.argmax(distances)

        return candidates[best_idx], candidates[diverse_idx]

    elif strategy == 'expected_improvement':
        # Active learning: best + expected improvement
        best_idx = np.argmax(scores)
        best_score = scores[best_idx]

        uncertainty = 1.0 - np.abs(scores - 0.5) * 2
        improvement = (scores - best_score) + 0.5 * uncertainty
        improvement[best_idx] = -np.inf

        ei_idx = np.argmax(improvement)

        return candidates[best_idx], candidates[ei_idx]

    elif strategy == 'uncertainty_sampling':
        # Pure active learning: pick two most uncertain
        uncertainty = 1.0 - np.abs(scores - 0.5) * 2
        top_uncertain_indices = np.argsort(uncertainty)[-2:]

        return candidates[top_uncertain_indices[0]], candidates[top_uncertain_indices[1]]

    else:
        raise ValueError(f"Unknown strategy: {strategy}")


# ===== Helper Functions for Improved Random Generation =====

def _decide_actual_pairs(target_pairs):
    """
    Decide actual number of pairs to generate from target_pairs upper limit.

    Args:
        target_pairs: Upper limit from CLI argument

    Returns:
        Actual number of pairs (randomized within range)

    Examples:
        target_pairs=20 → randint(12, 20)
        target_pairs=8  → randint(4, 8)
        target_pairs=0  → 0
    """
    if target_pairs == 0:
        return 0
    elif target_pairs >= 12:
        return random.randint(12, target_pairs)
    else:
        # For small values, use proportional range
        return random.randint(max(1, target_pairs // 2), target_pairs)


def _generate_pair_with_z_control(bounds_min, bounds_max, align_z_prob=0.25):
    """
    Generate a single pair (2 points) with independent XY coordinates and optional Z-alignment.

    Args:
        bounds_min: Minimum bounds [x, y, z]
        bounds_max: Maximum bounds [x, y, z]
        align_z_prob: Probability of Z-alignment mode (default: 0.25)

    Returns:
        points: (2, 3) array - the pair with same XY, different Z
        weights: (2,) array - weights in [0.6, 1.0] range (relative)
        align_z: bool - whether Z-alignment mode was used
    """
    # Generate independent XY coordinates (outside exclusion zone)
    xy_point = generate_point_outside_exclusion(bounds_min, bounds_max)
    xy = xy_point[:2]

    # Decide Z-alignment mode
    align_z = (random.random() < align_z_prob)

    if align_z:
        # Z-alignment mode: narrow range (±15-30mm)
        z_center = random.uniform(0, bounds_max[2])
        z_spread = random.uniform(15, 30)
        z1 = np.clip(z_center + random.uniform(-z_spread, z_spread), 0, bounds_max[2])
        z2 = np.clip(z_center + random.uniform(-z_spread, z_spread), 0, bounds_max[2])

        # Relaxed minimum separation (10mm)
        while abs(z1 - z2) < 10:
            z2 = np.clip(z_center + random.uniform(-z_spread, z_spread), 0, bounds_max[2])
    else:
        # Normal mode: random Z with 50mm minimum separation
        z1 = random.uniform(0, bounds_max[2])
        z2 = random.uniform(0, bounds_max[2])

        while abs(z1 - z2) < 50:
            z2 = random.uniform(0, bounds_max[2])

    # Weights for pair points (axis category)
    w1 = random.uniform(0.6, 1.0)
    w2 = random.uniform(0.6, 1.0)

    points = np.array([[xy[0], xy[1], z1], [xy[0], xy[1], z2]])
    weights = np.array([w1, w2])

    return points, weights, align_z


def _generate_near_axis_points(axis_points, n_near, bounds_min, bounds_max):
    """
    Generate points near existing axis points (50-100mm radius).

    Args:
        axis_points: (N, 3) array of pair points to generate near
        n_near: Number of near-axis points to generate
        bounds_min: Minimum bounds [x, y, z]
        bounds_max: Maximum bounds [x, y, z]

    Returns:
        points: (n_near, 3) array
        weights: (n_near,) array in [0.4, 0.7] range (relative)
    """
    points_list = []
    weights_list = []

    for _ in range(n_near):
        # Choose a random axis point as reference
        base_point = axis_points[random.randint(0, len(axis_points) - 1)]

        # Random distance 50-100mm
        radius = random.uniform(50, 100)
        angle = random.uniform(0, 2 * np.pi)

        # Generate point in XY plane around base
        x = base_point[0] + radius * np.cos(angle)
        y = base_point[1] + radius * np.sin(angle)
        z = random.uniform(0, bounds_max[2])

        # Clip to bounds
        x = np.clip(x, bounds_min[0], bounds_max[0])
        y = np.clip(y, bounds_min[1], bounds_max[1])

        # Weight for near-axis points
        w = random.uniform(0.4, 0.7)

        points_list.append([x, y, z])
        weights_list.append(w)

    return np.array(points_list), np.array(weights_list)


def _generate_free_points(n_free, bounds_min, bounds_max):
    """
    Generate free random points outside exclusion zone.

    Args:
        n_free: Number of free points to generate
        bounds_min: Minimum bounds [x, y, z]
        bounds_max: Maximum bounds [x, y, z]

    Returns:
        points: (n_free, 3) array
        weights: (n_free,) array in [0.2, 0.6] range (relative)
    """
    points = np.array([
        generate_point_outside_exclusion(bounds_min, bounds_max)
        for _ in range(n_free)
    ])

    weights = np.array([random.uniform(0.2, 0.6) for _ in range(n_free)])

    return points, weights


def _generate_biased_points(n_biased, bounds_min, bounds_max):
    """
    Generate biased points (periphery, top, or bottom regions).

    Args:
        n_biased: Number of biased points to generate
        bounds_min: Minimum bounds [x, y, z]
        bounds_max: Maximum bounds [x, y, z]

    Returns:
        points: (n_biased, 3) array
        weights: (n_biased,) array in [0.3, 0.6] range (relative)
    """
    points_list = []
    weights_list = []

    for _ in range(n_biased):
        bias_type = random.choice(['periphery', 'top', 'bottom'])

        if bias_type == 'periphery':
            # Outer edges in XY plane
            if random.random() < 0.5:
                # Left or right edge
                x = random.choice([
                    random.uniform(bounds_min[0], bounds_min[0] + 100),
                    random.uniform(bounds_max[0] - 100, bounds_max[0])
                ])
                y = random.uniform(bounds_min[1], bounds_max[1])
            else:
                # Top or bottom edge (in Y direction)
                x = random.uniform(bounds_min[0], bounds_max[0])
                y = random.choice([
                    random.uniform(bounds_min[1], bounds_min[1] + 100),
                    random.uniform(bounds_max[1] - 100, bounds_max[1])
                ])
            z = random.uniform(0, bounds_max[2])

        elif bias_type == 'top':
            # Upper Z region
            x = random.uniform(bounds_min[0], bounds_max[0])
            y = random.uniform(bounds_min[1], bounds_max[1])
            z = random.uniform(bounds_max[2] * 0.75, bounds_max[2])

        else:  # bottom
            # Lower Z region
            x = random.uniform(bounds_min[0], bounds_max[0])
            y = random.uniform(bounds_min[1], bounds_max[1])
            z = random.uniform(0, bounds_max[2] * 0.25)

        # Weight for biased points
        w = random.uniform(0.3, 0.6)

        points_list.append([x, y, z])
        weights_list.append(w)

    return np.array(points_list), np.array(weights_list)


def _normalize_weights(weights, target_min=10.0, target_max=50.0):
    """
    Normalize relative weights to absolute range [target_min, target_max].

    Args:
        weights: (N,) array of relative weights
        target_min: Minimum weight (default: 10.0mm)
        target_max: Maximum weight (default: 50.0mm)

    Returns:
        Normalized weights in [target_min, target_max] range
    """
    if len(weights) == 0:
        return weights

    w_min = weights.min()
    w_max = weights.max()

    if w_max - w_min < 1e-6:
        # All weights are the same, return midpoint
        return np.full_like(weights, (target_min + target_max) / 2)

    # Linear scaling: [w_min, w_max] → [target_min, target_max]
    normalized = target_min + (weights - w_min) / (w_max - w_min) * (target_max - target_min)

    return normalized


# ===== Initial Generation =====

def generate_random_genotype(params=DEFAULT_PARAMS, target_pairs=0):
    """
    Generate random initial genotype with improved variation strategy.

    Features:
    - Variable pair counts (target_pairs as upper limit)
    - Z-alignment control (20-30% of pairs have Z values in narrow range)
    - Role-differentiated non-pair points:
      * 40% near-axis (50-100mm from pair XY coordinates)
      * 40% free random (anywhere outside exclusion zone)
      * 20% biased (periphery/top/bottom regions)
    - 3-tier weight system:
      * Pair points: [0.6-1.0] → normalized to [10-50]mm
      * Near-axis: [0.4-0.7] → normalized to [10-50]mm
      * Free/biased: [0.2-0.6] → normalized to [10-50]mm

    Args:
        params: Generation parameters
        target_pairs: Upper limit for number of XY-pairs (default: 0)

    Returns:
        points: (N, 3) array - includes fixed points at the beginning
        weights: (N,) array - normalized to [weight_min, weight_max]

    Example:
        target_pairs=20, n_points=120 → generates:
            - actual_pairs: randint(12, 20) e.g., 17 pairs (34 points)
            - Z-aligned pairs: ~4-5 (25% of 17)
            - Non-pair points: 86 (34 near-axis, 34 free, 18 biased)
            - Total: 122 points (2 fixed + 120 generated)
    """
    bounds_min = np.array(params['bounds_min'])
    bounds_max = np.array(params['bounds_max'])

    # STEP 1: Decide actual number of pairs
    actual_pairs = _decide_actual_pairs(target_pairs)

    if target_pairs > 0:
        print(f"  Generating variable XY-pairs (target_pairs={target_pairs} → actual_pairs={actual_pairs})...")

    # STEP 2: Generate pair points with Z-control
    pair_points_list = []
    pair_weights_list = []
    z_aligned_count = 0

    for i in range(actual_pairs):
        pts, wts, align_z = _generate_pair_with_z_control(bounds_min, bounds_max, align_z_prob=0.25)
        pair_points_list.append(pts)
        pair_weights_list.append(wts)
        if align_z:
            z_aligned_count += 1

    if pair_points_list:
        pair_points = np.vstack(pair_points_list)
        pair_weights = np.concatenate(pair_weights_list)

        if actual_pairs > 0:
            z_align_rate = z_aligned_count / actual_pairs  # 0.0-1.0 range
            print(f"  Pairs: {actual_pairs}, Z-aligned: {z_aligned_count} ({z_align_rate*100:.1f}%)")
        else:
            z_align_rate = 0.0
    else:
        pair_points = np.zeros((0, 3))
        pair_weights = np.array([])
        z_align_rate = 0.0

    # STEP 3: Generate non-pair points (role-based distribution)
    n_remaining = params['n_points'] - len(pair_points)
    n_near = int(n_remaining * 0.4)
    n_free = int(n_remaining * 0.4)
    n_biased = n_remaining - n_near - n_free

    if target_pairs > 0 and n_remaining > 0:
        print(f"  Non-pair: {n_remaining} (near-axis: {n_near}, free: {n_free}, biased: {n_biased})")

    all_points = [pair_points] if len(pair_points) > 0 else []
    all_weights = [pair_weights] if len(pair_weights) > 0 else []

    # Near-axis points (only if we have pairs to reference)
    if n_near > 0 and len(pair_points) > 0:
        near_pts, near_wts = _generate_near_axis_points(pair_points, n_near, bounds_min, bounds_max)
        all_points.append(near_pts)
        all_weights.append(near_wts)
    elif n_near > 0:
        # No pairs available, convert to free points
        n_free += n_near
        n_near = 0

    # Free random points
    if n_free > 0:
        free_pts, free_wts = _generate_free_points(n_free, bounds_min, bounds_max)
        all_points.append(free_pts)
        all_weights.append(free_wts)

    # Biased points
    if n_biased > 0:
        biased_pts, biased_wts = _generate_biased_points(n_biased, bounds_min, bounds_max)
        all_points.append(biased_pts)
        all_weights.append(biased_wts)

    # Combine all generated points
    if all_points:
        points = np.vstack(all_points)
        weights = np.concatenate(all_weights)
    else:
        points = np.zeros((0, 3))
        weights = np.array([])

    # STEP 4: Normalize weights to [weight_min, weight_max]
    if len(weights) > 0:
        weights = _normalize_weights(weights, params['weight_min'], params['weight_max'])
        print(f"  Weight range: [{weights.min():.1f}, {weights.max():.1f}]mm")

    # STEP 5: Add fixed points at the beginning
    points = np.vstack([FIXED_POINTS, points])
    weights = np.concatenate([FIXED_WEIGHTS, weights])

    print(f"  Total: {len(points)} points (fixed: {len(FIXED_POINTS)}, generated: {len(points) - len(FIXED_POINTS)})")

    # Prepare generation_params for metadata
    generation_params = {
        'actual_pairs': actual_pairs,
        'z_alignment_count': z_aligned_count,
        'z_alignment_rate': z_align_rate  # 0.0-1.0 range
    }

    return points, weights, generation_params


# ===== Main Generation Function =====

def export_xy_pair_lines(points, obj_path, tolerance=1.0):
    """
    Export XY-pair connection lines as OBJ file.

    Coordinate system: Uses original (x, y, z) coordinates without conversion.

    Args:
        points: (N, 3) array of point positions
        obj_path: Output OBJ file path
        tolerance: XY clustering tolerance (mm)

    Returns:
        Number of lines exported
    """
    clusters = detect_xy_clusters(points, tolerance)

    if len(clusters) == 0:
        print(f"  No XY-pairs found (tolerance={tolerance}mm)")
        return 0

    with open(obj_path, 'w') as f:
        f.write("# XY-Pair Connection Lines\n")
        f.write(f"# Generated by IEC XY-Pair Evolution System\n")
        f.write(f"# Coordinate system: (x, y, z) - no transformation\n")
        f.write(f"# Tolerance: {tolerance}mm\n")
        f.write(f"# Clusters: {len(clusters)}\n\n")

        vertex_count = 0
        line_count = 0

        for cluster_idx, cluster_indices in enumerate(clusters):
            f.write(f"# Cluster {cluster_idx + 1}\n")

            # Write vertices for this cluster
            cluster_points = points[cluster_indices]
            start_vertex = vertex_count + 1

            for pt in cluster_points:
                # Use original (x, y, z) coordinates without conversion
                x, y, z = pt[0], pt[1], pt[2]
                f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
                vertex_count += 1

            # Write lines connecting all pairs in cluster
            cluster_size = len(cluster_indices)
            for i in range(cluster_size):
                for j in range(i + 1, cluster_size):
                    v1 = start_vertex + i
                    v2 = start_vertex + j
                    f.write(f"l {v1} {v2}\n")
                    line_count += 1

            f.write("\n")

    return line_count


def generate_pair(parent_path=None, params=DEFAULT_PARAMS, output_dir='../gen',
                  use_model=False, model_dir='../model', n_candidates=100, strategy='top_and_uncertain',
                  target_pairs=0, export_xy_lines=False, remove_boundary_cells=False,
                  enable_crossover=False, crossover_probability=0.5,
                  crossover_mode='blend', preserve_xy_pairs=True,
                  use_gnn_model=False, gnn_model_dir='../model/gnn'):
    """
    Generate a pair of candidate forms (A and B).

    Args:
        parent_path: path to parent meta_*.json (None for initial generation)
        params: mutation parameters
        output_dir: directory to save outputs
        use_model: Use preference learning model for candidate selection
        model_dir: Directory containing trained model
        n_candidates: Number of candidates to generate when using model
        strategy: Selection strategy for AI mode
        target_pairs: Number of XY-pairs to include in initial generation (default: 0)
        export_xy_lines: Export XY-pair connection lines as separate OBJ files (default: False)
        remove_boundary_cells: Remove cells that touch the bounding box boundary (default: False)
        enable_crossover: Enable crossover between parent and sibling (default: False)
        crossover_probability: Probability of applying crossover (default: 0.5)
        crossover_mode: Crossover mode - 'blend', 'uniform', or 'structure_aware' (default: 'blend')
        preserve_xy_pairs: Preserve XY-pair structures during crossover (default: True)
        use_gnn_model: Use GNN preference learning model for candidate selection (default: False)
        gnn_model_dir: Directory containing trained GNN model (default: ../model/gnn)

    Returns:
        tuple of (hash_A, hash_B)
    """
    os.makedirs(output_dir, exist_ok=True)

    # Determine iteration number
    iteration = 0
    parent_hash = None

    # Initialize crossover info (will be None if mutation or initial generation is used)
    crossover_info_A = None
    crossover_info_B = None

    if parent_path is None:
        # Initial generation: create two random genotypes
        # Clear gen_log directory to start fresh evolution
        import shutil
        gen_log_dir = os.path.join(os.path.dirname(output_dir), 'gen_log')
        if os.path.exists(gen_log_dir):
            print(f"Clearing generation history: {gen_log_dir}/")
            shutil.rmtree(gen_log_dir)
            print("  ✓ Previous generation history cleared")

        # Clear choices.csv to start fresh selection history
        log_dir = os.path.join(os.path.dirname(output_dir), 'log')
        choices_csv = os.path.join(log_dir, 'choices.csv')
        if os.path.exists(choices_csv):
            print(f"Clearing selection history: {choices_csv}")
            os.remove(choices_csv)
            print("  ✓ Previous selection history cleared")

        if target_pairs > 0:
            print(f"Generating initial random pair with {target_pairs} XY-pairs each...")
        else:
            print("Generating initial random pair...")
        points_A, weights_A, gen_params_A = generate_random_genotype(params, target_pairs=target_pairs)
        points_B, weights_B, gen_params_B = generate_random_genotype(params, target_pairs=target_pairs)

        # Create params with target_pairs for saving
        params_with_pairs = params.copy()
        params_with_pairs['target_pairs'] = target_pairs
    else:
        # Load parent and mutate to create two offspring
        print(f"Loading parent: {parent_path}")
        parent_points, parent_weights, parent_meta, parent_config = load_genotype(parent_path)

        # Ensure fixed points are present in parent
        parent_points, parent_weights = ensure_fixed_points(parent_points, parent_weights)

        iteration = parent_meta.get('iteration', 0) + 1
        parent_hash = parent_meta.get('hash', None)

        # Inherit generation configuration from parent
        inherited_params = params.copy()
        inherited_params['n_points'] = parent_config['n_points']
        inherited_params['target_pairs'] = parent_config.get('target_pairs', 0)
        print(f"  Inherited n_points: {parent_config['n_points']} (from parent config)")
        if inherited_params['target_pairs'] > 0:
            print(f"  Inherited target_pairs: {inherited_params['target_pairs']}")

        # Use inherited params for all generation methods
        params = inherited_params

        print(f"Generating offspring (iteration {iteration})...")

        # === IMPROVEMENT: Issue 6 - Adaptive mutation strength ===
        # Calculate adaptive mutation parameters (used for both crossover+mutation and mutation-only)
        adaptive_pos_sigma = get_adaptive_sigma(
            params['pos_mutation_sigma'], iteration, annealing_rate=0.05
        )
        adaptive_weight_sigma = get_adaptive_sigma(
            params['weight_mutation_sigma'], iteration, annealing_rate=0.05
        )

        print(f"  Adaptive sigma: pos={adaptive_pos_sigma:.2f}, weight={adaptive_weight_sigma:.2f}")

        # === IMPROVEMENT: Issue 3 - Differentiated A/B mutation policies ===
        # A: Position-focused (spatial exploration)
        params_A = params.copy()
        params_A['pos_mutation_sigma'] = adaptive_pos_sigma * 1.5
        params_A['weight_mutation_sigma'] = adaptive_weight_sigma * 0.5

        # B: Weight-focused (scale exploration)
        params_B = params.copy()
        params_B['pos_mutation_sigma'] = adaptive_pos_sigma * 0.5
        params_B['weight_mutation_sigma'] = adaptive_weight_sigma * 1.5

        print(f"  Strategy A (position-focused): pos={params_A['pos_mutation_sigma']:.2f}")
        print(f"  Strategy B (weight-focused): weight={params_B['weight_mutation_sigma']:.2f}")

        # === NEW: XY-pair structure mutation strategies ===
        # Randomly select XY strategy for each child
        xy_strategies = ['PRESERVE_XY', 'BREAK_XY', 'INCREASE_XY', 'NONE']
        xy_probabilities = [0.3, 0.2, 0.2, 0.3]  # Favor preservation and no-op

        xy_strategy_A = np.random.choice(xy_strategies, p=xy_probabilities)
        xy_strategy_B = np.random.choice(xy_strategies, p=xy_probabilities)

        print(f"  XY strategy A: {xy_strategy_A}")
        print(f"  XY strategy B: {xy_strategy_B}")

        # === NEW: Crossover Logic ===
        # Decide whether to use crossover this generation
        use_crossover_this_gen = enable_crossover and (np.random.random() < crossover_probability)

        if use_crossover_this_gen:
            print(f"\n🧬 Crossover Mode: Enabled (probability={crossover_probability:.2f})")

            # Try to load sibling (the other candidate from previous generation)
            sibling_path = get_sibling_meta_path(parent_path)

            if sibling_path and os.path.exists(sibling_path):
                sibling_points, sibling_weights, sibling_meta, _ = load_genotype(sibling_path)
                sibling_points, sibling_weights = ensure_fixed_points(sibling_points, sibling_weights)

                print(f"  Parent 1 (selected): {os.path.basename(parent_path)} - {len(parent_points)} points")
                print(f"  Parent 2 (sibling):  {os.path.basename(sibling_path)} - {len(sibling_points)} points")

                # Perform crossover to generate two children
                points_A, weights_A, crossover_info_A = crossover_genotypes(
                    parent_points, parent_weights,
                    sibling_points, sibling_weights,
                    params, crossover_mode, preserve_xy_pairs
                )

                points_B, weights_B, crossover_info_B = crossover_genotypes(
                    sibling_points, sibling_weights,
                    parent_points, parent_weights,
                    params, crossover_mode, preserve_xy_pairs
                )

                print(f"  Crossover A: {len(points_A)} points (from {crossover_info_A['n_from_parent1']}+{crossover_info_A['n_from_parent2']}, ratio={crossover_info_A['inheritance_ratio']:.2f})")
                print(f"  Crossover B: {len(points_B)} points (from {crossover_info_B['n_from_parent1']}+{crossover_info_B['n_from_parent2']}, ratio={crossover_info_B['inheritance_ratio']:.2f})")

                # === NEW: Apply mutation after crossover ===
                print(f"\n🔬 Applying mutation after crossover...")
                points_A, weights_A = mutate_genotype(points_A, weights_A, params_A, xy_strategy=xy_strategy_A)
                points_B, weights_B = mutate_genotype(points_B, weights_B, params_B, xy_strategy=xy_strategy_B)
                print(f"  Mutation A: {len(points_A)} points")
                print(f"  Mutation B: {len(points_B)} points")

            else:
                print(f"  ⚠ Sibling not found at {sibling_path if sibling_path else 'N/A'}")
                print(f"  Falling back to mutation...")
                use_crossover_this_gen = False

        # If crossover was not used (disabled, failed, or sibling not found), use mutation only
        if not use_crossover_this_gen:
            # === IMPROVEMENT: Phase 3 - AI-assisted candidate selection ===
            if use_model:
                import pickle
                model_path = os.path.join(model_dir, 'preference_model.pkl')
                scaler_path = os.path.join(model_dir, 'scaler.pkl')

                # Check if model exists
                if not os.path.exists(model_path) or not os.path.exists(scaler_path):
                    print(f"\n⚠ Warning: Model not found at {model_dir}")
                    print(f"  Falling back to traditional mutation...")
                    use_model = False

            if use_model:
                # Load model
                with open(model_path, 'rb') as f:
                    model = pickle.load(f)
                with open(scaler_path, 'rb') as f:
                    scaler = pickle.load(f)

                print(f"\n🤖 AI-Assisted Mode:")
                print(f"  Generating {n_candidates} candidates...")

                # Generate many candidates
                candidates = generate_many(parent_points, parent_weights, params, iteration, M=n_candidates)

                print(f"  AI selecting best pair from {n_candidates} candidates...")
                print(f"  Strategy: {strategy}")

                # Select best 2 using model
                candidate_A, candidate_B = select_best_pair(candidates, model, scaler, strategy=strategy)

                points_A = candidate_A['points']
                weights_A = candidate_A['weights']
                points_B = candidate_B['points']
                weights_B = candidate_B['weights']

                print(f"  ✓ Selected: A (mutation scale={candidate_A['scale_factor']:.1f}x), B (mutation scale={candidate_B['scale_factor']:.1f}x)")

            elif use_gnn_model:
                # === GNN-Assisted candidate selection ===
                import sys
                import site
                from pathlib import Path

                # Add pytorch_project venv to path for torch dependencies
                project_root = os.path.dirname(os.path.dirname(__file__))
                venv_path = os.path.join(project_root, 'pytorch_project', '.venv')

                if os.path.exists(venv_path):
                    # Add venv site-packages to Python path
                    import glob
                    site_packages = glob.glob(os.path.join(venv_path, 'lib', 'python*', 'site-packages'))
                    if site_packages:
                        sys.path.insert(0, site_packages[0])

                # Add pytorch_project to path
                pytorch_project_path = os.path.join(project_root, 'pytorch_project')
                if os.path.exists(pytorch_project_path):
                    sys.path.insert(0, pytorch_project_path)

                # Check if GNN model exists
                gnn_config_path = os.path.join(gnn_model_dir, 'training_config.json')
                gnn_model_path = os.path.join(gnn_model_dir, 'preference_gnn.pt')

                if not os.path.exists(gnn_config_path) or not os.path.exists(gnn_model_path):
                    print(f"\n⚠ Warning: GNN model not found at {gnn_model_dir}")
                    print(f"  Falling back to traditional mutation...")
                    use_gnn_model = False

                if use_gnn_model:
                    try:
                        from inference.predict import GNNPredictor

                        # Load GNN predictor
                        gnn_predictor = GNNPredictor(model_dir=gnn_model_dir)

                        print(f"\n🧠 GNN-Assisted Mode:")
                        print(f"  Generating {n_candidates} candidates...")

                        # Generate many candidates
                        candidates = generate_many(parent_points, parent_weights, params, iteration, M=n_candidates)

                        print(f"  GNN selecting best pair from {n_candidates} candidates...")
                        print(f"  Strategy: {strategy}")

                        # Select best 2 using GNN
                        candidate_A, candidate_B = select_best_pair_gnn(candidates, gnn_predictor, strategy=strategy)

                        points_A = candidate_A['points']
                        weights_A = candidate_A['weights']
                        gen_params_A = candidate_A.get('generation_params', {'actual_pairs': 0, 'z_alignment_count': 0, 'z_alignment_rate': 0.0})
                        points_B = candidate_B['points']
                        weights_B = candidate_B['weights']
                        gen_params_B = candidate_B.get('generation_params', {'actual_pairs': 0, 'z_alignment_count': 0, 'z_alignment_rate': 0.0})

                        print(f"  ✓ Selected: A (mutation scale={candidate_A['scale_factor']:.1f}x), B (mutation scale={candidate_B['scale_factor']:.1f}x)")

                    except Exception as e:
                        print(f"\n⚠ Error loading GNN model: {e}")
                        print(f"  Falling back to traditional mutation...")
                        use_gnn_model = False

                if not use_gnn_model:
                    # Fallback to random generation
                    print(f"  Generating 2 random candidates...")
                    target_pairs = params.get('target_pairs', 0)
                    points_A, weights_A, gen_params_A = generate_random_genotype(params=params, target_pairs=target_pairs)
                    points_B, weights_B, gen_params_B = generate_random_genotype(params=params, target_pairs=target_pairs)

            else:
                # Random generation (no model) - Phase 1 behavior
                print(f"  Generating 2 random candidates...")
                target_pairs = params.get('target_pairs', 0)
                points_A, weights_A, gen_params_A = generate_random_genotype(params=params, target_pairs=target_pairs)
                points_B, weights_B, gen_params_B = generate_random_genotype(params=params, target_pairs=target_pairs)

    # Ensure fixed points are present before saving
    points_A, weights_A = ensure_fixed_points(points_A, weights_A)
    points_B, weights_B = ensure_fixed_points(points_B, weights_B)

    # Save genotypes
    meta_A_path = os.path.join(output_dir, 'meta_A.json')
    meta_B_path = os.path.join(output_dir, 'meta_B.json')

    # Determine which params to save
    if parent_path is None:
        # Initial generation: use params_with_pairs
        save_params = params_with_pairs
    else:
        # Parent generation: use parent_config to inherit settings
        save_params = parent_config

    hash_A = save_genotype(points_A, weights_A, meta_A_path, parent_hash, iteration, crossover_info_A, save_params, gen_params_A)
    hash_B = save_genotype(points_B, weights_B, meta_B_path, parent_hash, iteration, crossover_info_B, save_params, gen_params_B)

    print(f"  A: {len(points_A)} points, hash={hash_A}")
    print(f"  B: {len(points_B)} points, hash={hash_B}")

    # Generate phenotypes (power diagrams)
    bounds_min = np.array(params['bounds_min'])
    bounds_max = np.array(params['bounds_max'])

    obj_A_path = os.path.join(output_dir, 'A.obj')
    obj_B_path = os.path.join(output_dir, 'B.obj')

    print("\nComputing Power Diagram for A...")
    sites_A = np.column_stack([points_A, weights_A])
    compute_power_diagram(sites_A, bounds_min, bounds_max, obj_A_path,
                         export_spheres=False, export_mode='faces')

    print("\nComputing Power Diagram for B...")
    sites_B = np.column_stack([points_B, weights_B])
    compute_power_diagram(sites_B, bounds_min, bounds_max, obj_B_path,
                         export_spheres=False, export_mode='faces')

    # Export boundary-removed versions if requested
    if remove_boundary_cells:
        print("\nExporting boundary-removed versions...")
        obj_A_inner_path = os.path.join(output_dir, 'A_inner.obj')
        obj_B_inner_path = os.path.join(output_dir, 'B_inner.obj')

        print("  Computing inner cells for A...")
        compute_power_diagram(sites_A, bounds_min, bounds_max, obj_A_inner_path,
                             export_spheres=False, export_mode='faces', remove_boundary_cells=True)

        print("  Computing inner cells for B...")
        compute_power_diagram(sites_B, bounds_min, bounds_max, obj_B_inner_path,
                             export_spheres=False, export_mode='faces', remove_boundary_cells=True)

    # Export XY-pair connection lines (optional)
    if export_xy_lines:
        print("\nExporting XY-pair connection lines...")

        lines_A_path = os.path.join(output_dir, 'A_xy_lines.obj')
        lines_B_path = os.path.join(output_dir, 'B_xy_lines.obj')

        num_lines_A = export_xy_pair_lines(points_A, lines_A_path, tolerance=1.0)
        num_lines_B = export_xy_pair_lines(points_B, lines_B_path, tolerance=1.0)

        print(f"  A: {num_lines_A} lines exported → {lines_A_path}")
        print(f"  B: {num_lines_B} lines exported → {lines_B_path}")

    # Save generation-numbered copies for history tracking
    print("\nSaving generation history...")
    import shutil

    # Create gen_log directory in the parent of output_dir
    gen_log_dir = os.path.join(os.path.dirname(output_dir), 'gen_log')
    os.makedirs(gen_log_dir, exist_ok=True)

    gen_prefix = f"gen{iteration}"

    # Copy OBJ files with generation number to gen_log
    gen_obj_A = os.path.join(gen_log_dir, f'{gen_prefix}_A.obj')
    gen_obj_B = os.path.join(gen_log_dir, f'{gen_prefix}_B.obj')
    shutil.copy2(obj_A_path, gen_obj_A)
    shutil.copy2(obj_B_path, gen_obj_B)

    # Copy metadata files with generation number to gen_log
    gen_meta_A = os.path.join(gen_log_dir, f'{gen_prefix}_meta_A.json')
    gen_meta_B = os.path.join(gen_log_dir, f'{gen_prefix}_meta_B.json')
    shutil.copy2(meta_A_path, gen_meta_A)
    shutil.copy2(meta_B_path, gen_meta_B)

    # Copy XY lines if exported to gen_log
    if export_xy_lines:
        gen_lines_A = os.path.join(gen_log_dir, f'{gen_prefix}_A_xy_lines.obj')
        gen_lines_B = os.path.join(gen_log_dir, f'{gen_prefix}_B_xy_lines.obj')
        shutil.copy2(lines_A_path, gen_lines_A)
        shutil.copy2(lines_B_path, gen_lines_B)

    # Copy inner versions if exported to gen_log
    if remove_boundary_cells:
        gen_inner_A = os.path.join(gen_log_dir, f'{gen_prefix}_A_inner.obj')
        gen_inner_B = os.path.join(gen_log_dir, f'{gen_prefix}_B_inner.obj')
        shutil.copy2(obj_A_inner_path, gen_inner_A)
        shutil.copy2(obj_B_inner_path, gen_inner_B)

    print(f"  Saved to gen_log/: {gen_prefix}_A.obj, {gen_prefix}_B.obj")
    print(f"  Saved to gen_log/: {gen_prefix}_meta_A.json, {gen_prefix}_meta_B.json")
    if export_xy_lines:
        print(f"  Saved to gen_log/: {gen_prefix}_A_xy_lines.obj, {gen_prefix}_B_xy_lines.obj")
    if remove_boundary_cells:
        print(f"  Saved to gen_log/: {gen_prefix}_A_inner.obj, {gen_prefix}_B_inner.obj")

    print("\n✓ Pair generation complete!")
    print(f"  Latest generation: {output_dir}/")
    print(f"    - A.obj, meta_A.json")
    print(f"    - B.obj, meta_B.json")
    if export_xy_lines:
        print(f"    - A_xy_lines.obj, B_xy_lines.obj")
    if remove_boundary_cells:
        print(f"    - A_inner.obj, B_inner.obj (boundary cells removed, bottom face kept)")
    print(f"  History: {gen_log_dir}/")
    print(f"    - {gen_prefix}_A.obj, {gen_prefix}_meta_A.json")
    print(f"    - {gen_prefix}_B.obj, {gen_prefix}_meta_B.json")
    if export_xy_lines:
        print(f"    - {gen_prefix}_A_xy_lines.obj, {gen_prefix}_B_xy_lines.obj")
    if remove_boundary_cells:
        print(f"    - {gen_prefix}_A_inner.obj, {gen_prefix}_B_inner.obj")

    return hash_A, hash_B


# ===== Crossover Functions =====

def get_sibling_meta_path(meta_path):
    """
    Get the sibling (other candidate) meta path.

    Examples:
        meta_A.json → meta_B.json
        meta_B.json → meta_A.json

    Args:
        meta_path: Path to one meta file

    Returns:
        Path to sibling meta file, or None if not found
    """
    if 'meta_A.json' in meta_path:
        return meta_path.replace('meta_A.json', 'meta_B.json')
    elif 'meta_B.json' in meta_path:
        return meta_path.replace('meta_B.json', 'meta_A.json')
    else:
        return None


def get_non_fixed_indices(points, tolerance=1e-6):
    """
    Get indices of non-fixed points.

    Args:
        points: (N, 3) array of positions
        tolerance: Distance tolerance for fixed point detection

    Returns:
        Array of indices for non-fixed points
    """
    non_fixed = []
    fixed_indices = get_fixed_point_indices(points, tolerance)
    for i in range(len(points)):
        if i not in fixed_indices:
            non_fixed.append(i)
    return np.array(non_fixed)


def select_points_with_clusters(points, clusters, target_count):
    """
    Select points while preferentially preserving XY-pair structure.

    Strategy:
    1. Select whole clusters (to keep pairs intact)
    2. Fill remaining quota with singleton points

    Args:
        points: (N, 3) array of positions
        clusters: List of lists, each containing indices of an XY cluster
        target_count: Number of points to select

    Returns:
        Array of selected indices
    """
    selected_indices = []

    # Shuffle clusters for randomness
    shuffled_clusters = clusters.copy()
    np.random.shuffle(shuffled_clusters)

    # Select clusters as units
    for cluster in shuffled_clusters:
        if len(selected_indices) + len(cluster) <= target_count:
            selected_indices.extend(cluster)

    # Get all clustered indices
    all_clustered = set(idx for cluster in clusters for idx in cluster)

    # Find singleton points (not in any cluster)
    singleton_indices = [i for i in range(len(points)) if i not in all_clustered]

    # Fill remaining quota with singletons
    remaining = target_count - len(selected_indices)
    if remaining > 0 and len(singleton_indices) > 0:
        n_to_add = min(remaining, len(singleton_indices))
        additional = np.random.choice(singleton_indices, n_to_add, replace=False)
        selected_indices.extend(additional)

    return np.array(selected_indices)


def find_matching_xy_cluster(point, target_points, tolerance=1.0):
    """
    Find a point in target_points with the same XY coordinates as point.

    Args:
        point: (3,) array - reference point
        target_points: (N, 3) array - points to search
        tolerance: XY distance threshold (default 1.0mm)

    Returns:
        int or None: index of matching point, or None if no match found
    """
    if len(target_points) == 0:
        return None

    xy = point[:2]
    for i, target_point in enumerate(target_points):
        if np.linalg.norm(xy - target_point[:2]) < tolerance:
            return i

    return None


def match_xy_clusters(clusters1, points1, clusters2, points2, tolerance=1.0):
    """
    Match XY-clusters between two parents based on XY proximity.

    Args:
        clusters1: List of cluster indices from parent1
        points1: Parent1 points array
        clusters2: List of cluster indices from parent2
        points2: Parent2 points array
        tolerance: XY distance threshold for matching (default 1.0mm)

    Returns:
        matched_pairs: List of (cluster1_idx, cluster2_idx) tuples
        unmatched1: List of unmatched cluster indices from parent1
        unmatched2: List of unmatched cluster indices from parent2
    """
    matched_pairs = []
    used1 = set()
    used2 = set()

    for i, cluster1 in enumerate(clusters1):
        if i in used1:
            continue

        # Get representative XY from cluster1 (use first point)
        xy1 = points1[cluster1[0]][:2]

        # Find matching cluster in parent2
        best_match = None
        best_dist = float('inf')

        for j, cluster2 in enumerate(clusters2):
            if j in used2:
                continue

            xy2 = points2[cluster2[0]][:2]
            dist = np.linalg.norm(xy1 - xy2)

            if dist < tolerance and dist < best_dist:
                best_match = j
                best_dist = dist

        if best_match is not None:
            matched_pairs.append((i, best_match))
            used1.add(i)
            used2.add(best_match)

    unmatched1 = [i for i in range(len(clusters1)) if i not in used1]
    unmatched2 = [j for j in range(len(clusters2)) if j not in used2]

    return matched_pairs, unmatched1, unmatched2


def blend_xy_cluster(cluster1, points1, weights1, cluster2, points2, weights2,
                     alpha=0.7, output_size=2):
    """
    Blend two XY-clusters into one output cluster.

    Args:
        cluster1: Indices of points in cluster1
        points1, weights1: Parent1 data
        cluster2: Indices of points in cluster2
        points2, weights2: Parent2 data
        alpha: Blend ratio (favor parent1 if > 0.5)
        output_size: Number of points in output cluster (default: 2)

    Returns:
        blended_points: (output_size, 3) array
        blended_weights: (output_size,) array
    """
    # Get representative XY (average of cluster1's XY coordinates)
    xy1_coords = np.array([points1[idx][:2] for idx in cluster1])
    xy_representative = np.mean(xy1_coords, axis=0)

    # Collect Z coordinates and weights from both clusters
    z1_values = [points1[idx][2] for idx in cluster1]
    w1_values = [weights1[idx] for idx in cluster1]
    z2_values = [points2[idx][2] for idx in cluster2]
    w2_values = [weights2[idx] for idx in cluster2]

    blended_points = []
    blended_weights = []

    for i in range(output_size):
        # Select Z and weight from each parent
        z1 = z1_values[i % len(z1_values)]
        w1 = w1_values[i % len(w1_values)]
        z2 = z2_values[i % len(z2_values)]
        w2 = w2_values[i % len(w2_values)]

        # Blend Z and weight
        blended_z = alpha * z1 + (1 - alpha) * z2
        blended_w = alpha * w1 + (1 - alpha) * w2

        # Create blended point
        blended_point = np.array([xy_representative[0], xy_representative[1], blended_z])
        blended_points.append(blended_point)
        blended_weights.append(blended_w)

    return np.array(blended_points), np.array(blended_weights)


def crossover_genotypes(points1, weights1, points2, weights2,
                       params=DEFAULT_PARAMS, crossover_mode='blend',
                       preserve_xy_pairs=True):
    """
    Generate a child genotype by crossover between two parents.

    NEW: Treats XY-pair clusters as atomic units to prevent pair inflation.

    Algorithm:
    1. Detect XY-clusters in both parents
    2. Match clusters between parents by XY proximity
    3. Blend matched clusters as atomic units (one cluster pair → one output cluster)
    4. Add singletons to reach target point count
    5. Return child with controlled pair count

    Args:
        points1: (N1, 3) parent 1 positions
        weights1: (N1,) parent 1 weights
        points2: (N2, 3) parent 2 positions
        weights2: (N2,) parent 2 weights
        params: Parameter dictionary (bounds, weight limits, etc.)
        crossover_mode: 'blend', 'uniform', or 'structure_aware'
        preserve_xy_pairs: If True, treat XY-pairs as atomic units

    Returns:
        child_points: (M, 3) child positions
        child_weights: (M,) child weights
        crossover_info: dict with crossover metadata
    """
    bounds_min = np.array(params['bounds_min'])
    bounds_max = np.array(params['bounds_max'])
    weight_min = params['weight_min']
    weight_max = params['weight_max']

    # Step 1: Exclude fixed points
    non_fixed_indices1 = get_non_fixed_indices(points1)
    non_fixed_indices2 = get_non_fixed_indices(points2)

    parent1_points = points1[non_fixed_indices1]
    parent1_weights = weights1[non_fixed_indices1]
    parent2_points = points2[non_fixed_indices2]
    parent2_weights = weights2[non_fixed_indices2]

    # Step 2: Detect XY-pair clusters in both parents
    full_clusters1 = detect_xy_clusters(points1, tolerance=1.0)
    full_clusters2 = detect_xy_clusters(points2, tolerance=1.0)

    # Map to non-fixed indices
    clusters1 = []
    clusters2 = []
    non_fixed_set1 = set(non_fixed_indices1)
    non_fixed_set2 = set(non_fixed_indices2)

    for cluster in full_clusters1:
        mapped_cluster = [list(non_fixed_indices1).index(idx)
                        for idx in cluster if idx in non_fixed_set1]
        if len(mapped_cluster) >= 2:  # Only keep actual pairs
            clusters1.append(mapped_cluster)

    for cluster in full_clusters2:
        mapped_cluster = [list(non_fixed_indices2).index(idx)
                        for idx in cluster if idx in non_fixed_set2]
        if len(mapped_cluster) >= 2:
            clusters2.append(mapped_cluster)

    # Step 3: Determine target numbers
    target_n_points = params.get('n_points', 100)
    target_pairs = params.get('target_pairs', 40)

    child_points_list = []
    child_weights_list = []

    if preserve_xy_pairs and crossover_mode == 'xy_cluster_swap':
        # クラスタ一致(match)を要求しない：クラスタを"単位"として交換
        pool = [(1, i) for i in range(len(clusters1))] + [(2, j) for j in range(len(clusters2))]
        np.random.shuffle(pool)

        # 目標ペア数ぶんクラスタを選択（取れるだけ）
        n_select = min(target_pairs, len(pool))
        selected = pool[:n_select]

        # 親2側のクラスタが空のときのフォールバック（blend相手）
        has_c2 = (len(clusters2) > 0)
        has_c1 = (len(clusters1) > 0)

        for side, idx in selected:
            alpha = np.random.uniform(0.6, 0.8)

            if side == 1:
                cluster_xy = clusters1[idx]
                # blend相手（Z/weight供給元）は親2のランダムクラスタ、無ければ親1から
                if has_c2:
                    cluster_z = clusters2[np.random.randint(0, len(clusters2))]
                    pts, wts = blend_xy_cluster(cluster_xy, parent1_points, parent1_weights,
                                                cluster_z, parent2_points, parent2_weights,
                                                alpha=alpha, output_size=2)
                else:
                    # 親2クラスタが無いなら、同じ親内でblend（Zだけ揺らす効果）
                    cluster_z = clusters1[np.random.randint(0, len(clusters1))]
                    pts, wts = blend_xy_cluster(cluster_xy, parent1_points, parent1_weights,
                                                cluster_z, parent1_points, parent1_weights,
                                                alpha=alpha, output_size=2)

            else:  # side == 2
                cluster_xy = clusters2[idx]
                if has_c1:
                    cluster_z = clusters1[np.random.randint(0, len(clusters1))]
                    # ここでは"XYは親2コピー"にしたいので、cluster_xy を第1引数にする
                    pts, wts = blend_xy_cluster(cluster_xy, parent2_points, parent2_weights,
                                                cluster_z, parent1_points, parent1_weights,
                                                alpha=alpha, output_size=2)
                else:
                    cluster_z = clusters2[np.random.randint(0, len(clusters2))]
                    pts, wts = blend_xy_cluster(cluster_xy, parent2_points, parent2_weights,
                                                cluster_z, parent2_points, parent2_weights,
                                                alpha=alpha, output_size=2)

            for pt, wt in zip(pts, wts):
                child_points_list.append(pt)
                child_weights_list.append(wt)

    else:
        # 既存ロジック（matched_pairs を使う方）
        matched_pairs, unmatched1, unmatched2 = match_xy_clusters(
            clusters1, parent1_points, clusters2, parent2_points, tolerance=1.0
        )
        n_matched = len(matched_pairs)
        n_clusters_to_select = min(target_pairs, n_matched)

        if n_matched > 0:
            selected_match_indices = np.random.choice(
                len(matched_pairs),
                min(n_clusters_to_select, n_matched),
                replace=False
            )
        else:
            selected_match_indices = []

        for match_idx in selected_match_indices:
            c1_idx, c2_idx = matched_pairs[match_idx]
            cluster1 = clusters1[c1_idx]
            cluster2 = clusters2[c2_idx]
            alpha = np.random.uniform(0.6, 0.8)
            blended_pts, blended_wts = blend_xy_cluster(
                cluster1, parent1_points, parent1_weights,
                cluster2, parent2_points, parent2_weights,
                alpha=alpha, output_size=2
            )
            for pt, wt in zip(blended_pts, blended_wts):
                child_points_list.append(pt)
                child_weights_list.append(wt)

    # Step 4: Add singleton points if needed to reach target_n_points
    current_count = len(child_points_list)
    needed = target_n_points - current_count

    if needed > 0:
        # Collect singleton indices
        all_clustered1 = set(idx for cluster in clusters1 for idx in cluster)
        all_clustered2 = set(idx for cluster in clusters2 for idx in cluster)

        singletons1 = [i for i in range(len(parent1_points)) if i not in all_clustered1]
        singletons2 = [i for i in range(len(parent2_points)) if i not in all_clustered2]

        # Sample singletons from both parents
        n_from_s1 = min(needed // 2, len(singletons1))
        n_from_s2 = min(needed - n_from_s1, len(singletons2))

        if n_from_s1 > 0:
            selected_s1 = np.random.choice(singletons1, n_from_s1, replace=False)
            for idx in selected_s1:
                child_points_list.append(parent1_points[idx])
                child_weights_list.append(parent1_weights[idx])

        if n_from_s2 > 0:
            selected_s2 = np.random.choice(singletons2, n_from_s2, replace=False)
            for idx in selected_s2:
                child_points_list.append(parent2_points[idx])
                child_weights_list.append(parent2_weights[idx])

    # Step 7: Convert to arrays and add fixed points
    if len(child_points_list) > 0:
        child_points = np.array(child_points_list)
        child_weights = np.array(child_weights_list)
    else:
        # Fallback
        child_points = parent1_points[:3].copy()
        child_weights = parent1_weights[:3].copy()

    # Clip to bounds
    child_points = np.clip(child_points, bounds_min, bounds_max)
    child_weights = np.clip(child_weights, weight_min, weight_max)

    # Add fixed points back
    child_points, child_weights = ensure_fixed_points(child_points, child_weights)

    # Step 5: Record metadata
    if preserve_xy_pairs and crossover_mode == 'xy_cluster_swap':
        crossover_info = {
            'mode': crossover_mode,
            'n_clusters_used': len(selected),
            'n_singletons_added': len(child_points_list) - 2 * len(selected),
            'preserve_xy_pairs': preserve_xy_pairs,
            'n_clusters_parent1': len(clusters1),
            'n_clusters_parent2': len(clusters2)
        }
    else:
        crossover_info = {
            'mode': crossover_mode,
            'n_matched_clusters': len(matched_pairs) if 'matched_pairs' in locals() else 0,
            'n_selected_clusters': len(selected_match_indices) if 'selected_match_indices' in locals() else 0,
            'n_singletons_added': len(child_points_list) - 2 * (len(selected_match_indices) if 'selected_match_indices' in locals() else 0),
            'preserve_xy_pairs': preserve_xy_pairs,
            'n_clusters_parent1': len(clusters1),
            'n_clusters_parent2': len(clusters2)
        }

    return child_points, child_weights, crossover_info


# ===== CLI Interface =====

def main():
    parser = argparse.ArgumentParser(
        description='Generate pair of candidate forms for IEC'
    )
    parser.add_argument('--init', action='store_true',
                       help='Generate random initial pair')
    parser.add_argument('--parent', type=str,
                       help='Path to parent meta_*.json file')
    parser.add_argument('--output', type=str, default='../gen',
                       help='Output directory (default: ../gen)')

    # Mutation parameter overrides
    parser.add_argument('--n-points', type=int, default=DEFAULT_PARAMS['n_points'],
                       help=f"Initial number of points (default: {DEFAULT_PARAMS['n_points']})")
    parser.add_argument('--pos-sigma', type=float, default=DEFAULT_PARAMS['pos_mutation_sigma'],
                       help=f"Position mutation sigma (default: {DEFAULT_PARAMS['pos_mutation_sigma']})")
    parser.add_argument('--weight-sigma', type=float, default=DEFAULT_PARAMS['weight_mutation_sigma'],
                       help=f"Weight mutation sigma (default: {DEFAULT_PARAMS['weight_mutation_sigma']})")

    # XY-pair structure options
    parser.add_argument('--target-pairs', type=int, default=0,
                       help='Number of XY-pairs to create in initial generation (default: 0)')
    parser.add_argument('--export-xy-lines', action='store_true',
                       help='Export XY-pair connection lines as separate OBJ files')
    parser.add_argument('--remove-boundary-cells', action='store_true',
                       help='Remove cells that touch the bounding box boundary (except bottom face)')

    # AI-assisted mode (Phase 3 & 4: Preference Learning + Active Learning)
    parser.add_argument('--use-model', action='store_true',
                       help='Use preference learning model (LogisticRegression) for AI-assisted candidate selection')
    parser.add_argument('--model-dir', type=str, default='../model',
                       help='Directory containing trained model (default: ../model)')
    parser.add_argument('--use-gnn-model', action='store_true',
                       help='Use GNN preference learning model for AI-assisted candidate selection')
    parser.add_argument('--gnn-model-dir', type=str, default='../model/gnn',
                       help='Directory containing trained GNN model (default: ../model/gnn)')
    parser.add_argument('--candidates', type=int, default=100,
                       help='Number of candidates to generate when using model (default: 100)')
    parser.add_argument('--strategy', type=str, default='top_and_uncertain',
                       choices=['top_2', 'top_and_uncertain', 'diverse',
                               'expected_improvement', 'uncertainty_sampling'],
                       help='Selection strategy for AI mode (default: top_and_uncertain)')

    # Crossover options
    parser.add_argument('--enable-crossover', action='store_true',
                       help='Enable crossover between parent and sibling (default: False)')
    parser.add_argument('--crossover-prob', type=float, default=0.5,
                       help='Probability of applying crossover (default: 0.5)')
    parser.add_argument('--crossover-mode', type=str, default='blend',
                       choices=['blend', 'uniform', 'structure_aware'],
                       help='Crossover mode (default: blend)')
    parser.add_argument('--no-preserve-xy-in-crossover', action='store_true',
                       help='Do not preserve XY-pair structures during crossover (default: preserve)')

    args = parser.parse_args()

    # Validate arguments
    if not args.init and args.parent is None:
        parser.error("Must specify either --init or --parent")

    if args.init and args.parent is not None:
        parser.error("Cannot specify both --init and --parent")

    # Build parameters dict
    params = DEFAULT_PARAMS.copy()
    params['n_points'] = args.n_points
    params['pos_mutation_sigma'] = args.pos_sigma
    params['weight_mutation_sigma'] = args.weight_sigma

    # Set random seed for reproducibility (optional)
    seed = int(datetime.now().timestamp() * 1000) % (2**32)
    np.random.seed(seed)
    print(f"Random seed: {seed}\n")

    # Generate pair
    parent_path = None if args.init else args.parent
    generate_pair(
        parent_path=parent_path,
        params=params,
        output_dir=args.output,
        use_model=args.use_model,
        model_dir=args.model_dir,
        n_candidates=args.candidates,
        strategy=args.strategy,
        target_pairs=args.target_pairs,
        export_xy_lines=args.export_xy_lines,
        remove_boundary_cells=args.remove_boundary_cells,
        enable_crossover=args.enable_crossover,
        crossover_probability=args.crossover_prob,
        crossover_mode=args.crossover_mode,
        preserve_xy_pairs=not args.no_preserve_xy_in_crossover,
        use_gnn_model=args.use_gnn_model,
        gnn_model_dir=args.gnn_model_dir
    )


if __name__ == '__main__':
    main()
