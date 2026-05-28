#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
visualize_xy_pairs.py - Visualize XY-Pair Connections in Rhino

XY座標が同じ頂点ペア間に線を表示するRhinoスクリプト

Usage in Rhino:
    1. RunPythonScript path/to/visualize_xy_pairs.py
    または
    2. Rhinoのコマンドラインで:
       import sys
       sys.path.append('path/to/IEC/rhino')
       import visualize_xy_pairs
       visualize_xy_pairs.visualize_pairs('path/to/meta_A.json')
"""

import sys
import os
import json
import rhinoscriptsyntax as rs
from System.Drawing import Color

# Import XY detection from generate_pair.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../tools'))
try:
    from generate_pair import detect_xy_clusters, compute_pair_metrics
except ImportError:
    print("Error: Cannot import generate_pair.py")
    print("Make sure generate_pair.py is in IEC/tools/")
    sys.exit(1)


def load_genotype(filepath):
    """
    Load genotype from JSON file.

    Returns:
        points: List of [x, y, z] positions
        weights: List of weights
        metadata: dict
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    points = [p['position'] for p in data['points']]
    weights = [p['weight'] for p in data['points']]
    metadata = data.get('metadata', {})

    return points, weights, metadata


def visualize_pairs(meta_path, tolerance=1.0, layer_name="XY_Pairs",
                   line_color=None, sphere_color=None, show_spheres=True):
    """
    Visualize XY-pair connections in Rhino.

    Args:
        meta_path: Path to meta_*.json file
        tolerance: XY clustering tolerance (mm)
        layer_name: Layer name for XY-pair geometry
        line_color: Color for connection lines (default: red)
        sphere_color: Color for spheres (default: blue)
        show_spheres: Whether to show spheres at points (default: True)

    Returns:
        dict with visualization statistics
    """
    # Default colors
    if line_color is None:
        line_color = Color.FromArgb(255, 0, 0)  # Red
    if sphere_color is None:
        sphere_color = Color.FromArgb(0, 100, 255)  # Blue

    # Load genotype
    print("\n" + "="*60)
    print("XY-Pair Visualization")
    print("="*60)
    print(f"Loading: {os.path.basename(meta_path)}")

    points, weights, metadata = load_genotype(meta_path)
    n_points = len(points)

    # Convert to numpy array for detection
    import numpy as np
    points_array = np.array(points)

    # Detect XY clusters
    clusters = detect_xy_clusters(points_array, tolerance=tolerance)
    metrics = compute_pair_metrics(points_array, tolerance=tolerance)

    print(f"\nPoints: {n_points}")
    print(f"XY-Pairs: {metrics['xy_pair_count']}")
    print(f"Mean dz: {metrics['mean_pair_dz']:.1f} mm")

    # Create layer
    if not rs.IsLayer(layer_name):
        rs.AddLayer(layer_name, Color.FromArgb(255, 255, 0))  # Yellow layer
    rs.CurrentLayer(layer_name)

    # Draw visualization
    line_objects = []
    sphere_objects = []
    text_objects = []

    for cluster_idx, cluster_indices in enumerate(clusters):
        # Get cluster points
        cluster_points = [points[i] for i in cluster_indices]
        cluster_weights = [weights[i] for i in cluster_indices]

        # Compute cluster Z range
        z_values = [p[2] for p in cluster_points]
        dz = max(z_values) - min(z_values)

        # Draw spheres at each point (optional)
        if show_spheres:
            for i, (pt, wt) in enumerate(zip(cluster_points, cluster_weights)):
                # Rhino uses Z-up, but our data is already in correct orientation
                sphere = rs.AddSphere(pt, wt / 2.0)  # Radius = weight/2
                rs.ObjectColor(sphere, sphere_color)
                rs.ObjectLayer(sphere, layer_name)
                sphere_objects.append(sphere)

        # Draw lines connecting all pairs in cluster
        for i in range(len(cluster_points)):
            for j in range(i + 1, len(cluster_points)):
                pt1 = cluster_points[i]
                pt2 = cluster_points[j]

                # Add line
                line = rs.AddLine(pt1, pt2)
                rs.ObjectColor(line, line_color)
                rs.ObjectLayer(line, layer_name)
                line_objects.append(line)

        # Add text label at cluster center
        # Center XY = average of cluster points' XY
        center_xy = [
            sum(p[0] for p in cluster_points) / len(cluster_points),
            sum(p[1] for p in cluster_points) / len(cluster_points),
            max(z_values) + 50  # Slightly above highest point
        ]

        text = f"Pair {cluster_idx + 1}\ndz={dz:.1f}mm"
        text_obj = rs.AddText(text, center_xy, height=20)
        rs.ObjectColor(text_obj, Color.FromArgb(255, 255, 255))  # White text
        rs.ObjectLayer(text_obj, layer_name)
        text_objects.append(text_obj)

    # Summary
    print(f"\n✓ Visualization complete:")
    print(f"  Lines drawn: {len(line_objects)}")
    if show_spheres:
        print(f"  Spheres drawn: {len(sphere_objects)}")
    print(f"  Labels added: {len(text_objects)}")
    print(f"  Layer: {layer_name}")

    # Zoom to objects
    all_objects = line_objects + sphere_objects + text_objects
    if all_objects:
        rs.ZoomExtents()

    return {
        'metrics': metrics,
        'lines': line_objects,
        'spheres': sphere_objects,
        'texts': text_objects,
        'layer': layer_name
    }


def visualize_comparison(meta_A_path, meta_B_path, tolerance=1.0):
    """
    Visualize XY-pairs for both A and B side-by-side.

    Args:
        meta_A_path: Path to meta_A.json
        meta_B_path: Path to meta_B.json
        tolerance: XY clustering tolerance

    Returns:
        dict with both visualizations
    """
    print("\n" + "="*60)
    print("XY-Pair Comparison Visualization")
    print("="*60)

    # Visualize A (left side)
    print("\n--- Candidate A ---")
    viz_A = visualize_pairs(
        meta_A_path,
        tolerance=tolerance,
        layer_name="XY_Pairs_A",
        line_color=Color.FromArgb(255, 0, 0),  # Red
        sphere_color=Color.FromArgb(255, 100, 100),
        show_spheres=True
    )

    # Visualize B (right side, shifted)
    print("\n--- Candidate B ---")

    # Load B points to compute shift
    points_B, _, _ = load_genotype(meta_B_path)
    import numpy as np
    points_B_array = np.array(points_B)
    x_max_B = points_B_array[:, 0].max()
    shift_x = x_max_B + 200  # 200mm gap

    # Create shifted version of B
    import tempfile
    import shutil
    temp_meta_B = tempfile.mktemp(suffix='.json')

    with open(meta_B_path, 'r') as f:
        data_B = json.load(f)

    # Shift all points
    for pt in data_B['points']:
        pt['position'][0] += shift_x

    with open(temp_meta_B, 'w') as f:
        json.dump(data_B, f)

    viz_B = visualize_pairs(
        temp_meta_B,
        tolerance=tolerance,
        layer_name="XY_Pairs_B",
        line_color=Color.FromArgb(0, 0, 255),  # Blue
        sphere_color=Color.FromArgb(100, 100, 255),
        show_spheres=True
    )

    # Clean up temp file
    os.remove(temp_meta_B)

    # Add comparison labels
    import rhinoscriptsyntax as rs

    # Label A
    rs.CurrentLayer("XY_Pairs_A")
    label_A = rs.AddText(
        f"A | Pairs: {viz_A['metrics']['xy_pair_count']} | Mean dz: {viz_A['metrics']['mean_pair_dz']:.1f}mm",
        [0, -100, 0],
        height=40
    )
    rs.ObjectColor(label_A, Color.FromArgb(255, 0, 0))

    # Label B
    rs.CurrentLayer("XY_Pairs_B")
    label_B = rs.AddText(
        f"B | Pairs: {viz_B['metrics']['xy_pair_count']} | Mean dz: {viz_B['metrics']['mean_pair_dz']:.1f}mm",
        [shift_x, -100, 0],
        height=40
    )
    rs.ObjectColor(label_B, Color.FromArgb(0, 0, 255))

    rs.ZoomExtents()

    print("\n" + "="*60)
    print("✓ Comparison visualization complete")
    print("="*60)
    print(f"A: {viz_A['metrics']['xy_pair_count']} pairs, mean dz = {viz_A['metrics']['mean_pair_dz']:.1f}mm")
    print(f"B: {viz_B['metrics']['xy_pair_count']} pairs, mean dz = {viz_B['metrics']['mean_pair_dz']:.1f}mm")

    return {
        'A': viz_A,
        'B': viz_B
    }


def clear_visualization(layer_name="XY_Pairs"):
    """
    Clear XY-pair visualization from Rhino.

    Args:
        layer_name: Layer to clear (default: "XY_Pairs")
    """
    if rs.IsLayer(layer_name):
        objects = rs.ObjectsByLayer(layer_name)
        if objects:
            rs.DeleteObjects(objects)
            print(f"✓ Cleared {len(objects)} objects from layer '{layer_name}'")
        else:
            print(f"Layer '{layer_name}' is already empty")
    else:
        print(f"Layer '{layer_name}' does not exist")


def clear_all_visualizations():
    """Clear all XY-pair visualizations (A and B)."""
    clear_visualization("XY_Pairs")
    clear_visualization("XY_Pairs_A")
    clear_visualization("XY_Pairs_B")


# ===== Command-line interface for testing =====

def main():
    """Main function for command-line testing."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Visualize XY-Pair connections in Rhino'
    )
    parser.add_argument('meta_path', type=str, nargs='?',
                       help='Path to meta_*.json file')
    parser.add_argument('--compare', type=str,
                       help='Path to second meta file for comparison')
    parser.add_argument('--tolerance', type=float, default=1.0,
                       help='XY clustering tolerance (default: 1.0mm)')
    parser.add_argument('--clear', action='store_true',
                       help='Clear existing visualizations')

    args = parser.parse_args()

    if args.clear:
        clear_all_visualizations()
        return

    if not args.meta_path:
        parser.error("meta_path is required (unless using --clear)")

    if args.compare:
        # Comparison mode
        visualize_comparison(args.meta_path, args.compare, tolerance=args.tolerance)
    else:
        # Single visualization
        visualize_pairs(args.meta_path, tolerance=args.tolerance)


# ===== Rhino script execution =====

if __name__ == '__main__':
    # Check if running in Rhino
    try:
        import rhinoscriptsyntax as rs
        IN_RHINO = True
    except:
        IN_RHINO = False

    if IN_RHINO:
        # Running in Rhino - use default paths
        import os
        project_root = os.path.dirname(os.path.dirname(__file__))

        # Try to find gen directory
        gen_dir = os.path.join(project_root, 'gen')

        if os.path.exists(gen_dir):
            meta_A = os.path.join(gen_dir, 'meta_A.json')
            meta_B = os.path.join(gen_dir, 'meta_B.json')

            if os.path.exists(meta_A) and os.path.exists(meta_B):
                print("Found both meta_A.json and meta_B.json")
                print("Visualizing comparison...")
                visualize_comparison(meta_A, meta_B)
            elif os.path.exists(meta_A):
                print("Found meta_A.json only")
                visualize_pairs(meta_A)
            else:
                print("No meta files found in gen/")
                print("Please generate geometry first:")
                print("  cd IEC/tools")
                print("  python generate_pair.py --init --target-pairs 3")
        else:
            print(f"gen directory not found: {gen_dir}")
            print("Please run from IEC project directory")
    else:
        # Running from command line
        main()
