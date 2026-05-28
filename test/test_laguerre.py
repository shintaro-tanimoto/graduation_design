#!/usr/bin/env python3
"""
Test program for Laguerre Voronoi diagram generation.

This program:
1. Generates 40 random weighted points in a 1000x1000x1000 space
2. Computes the Laguerre Voronoi (Power Diagram) diagram
3. Exports the result as an OBJ file
"""

import sys
import os
import json
import numpy as np

# Add parent directory to path to import LaguerreVoronoi
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LaguerreVoronoi import compute_power_diagram

def generate_random_sites(n_points=40, box_size=1000, weight_range=(10, 100), seed=None):
    """
    Generate random weighted points in a cubic space.

    Args:
        n_points: Number of points to generate (default: 40)
        box_size: Size of the cubic bounding box (default: 1000)
        weight_range: Tuple of (min_weight, max_weight) (default: (10, 100))
        seed: Random seed for reproducibility (default: None)

    Returns:
        sites: (N, 4) numpy array [x, y, z, w]
        box_min: (3,) array of minimum bounds
        box_max: (3,) array of maximum bounds
    """
    if seed is not None:
        np.random.seed(seed)

    # Generate random positions in [0, box_size]^3
    positions = np.random.uniform(0, box_size, size=(n_points, 3))

    # Generate random weights
    weights = np.random.uniform(weight_range[0], weight_range[1], size=n_points)

    # Combine positions and weights
    sites = np.column_stack([positions, weights])

    # Define bounding box
    box_min = np.array([0.0, 0.0, 0.0])
    box_max = np.array([box_size, box_size, box_size])

    return sites, box_min, box_max


def main():
    """Main function to generate and compute Laguerre Voronoi diagram."""

    # Configuration
    N_POINTS = 40
    BOX_SIZE = 1000
    WEIGHT_RANGE = (10, 100)
    OUTPUT_FILE = "test/laguerre_test.obj"
    OUTPUT_FILE_WITH_SPHERES = "test/laguerre_test_with_spheres.obj"
    JSON_FILE = "test/sites_data.json"
    SEED = 42  # For reproducibility

    print("="*60)
    print("  Laguerre Voronoi Test Program")
    print("="*60)
    print(f"Configuration:")
    print(f"  Number of points: {N_POINTS}")
    print(f"  Bounding box: {BOX_SIZE}x{BOX_SIZE}x{BOX_SIZE}")
    print(f"  Weight range: {WEIGHT_RANGE[0]} - {WEIGHT_RANGE[1]}")
    print(f"  Random seed: {SEED}")
    print(f"  Output OBJ files:")
    print(f"    - {OUTPUT_FILE}")
    print(f"    - {OUTPUT_FILE_WITH_SPHERES}")
    print(f"  Output JSON file: {JSON_FILE}")
    print("="*60)

    # Generate random sites
    print("\nGenerating random weighted points...")
    sites, box_min, box_max = generate_random_sites(
        n_points=N_POINTS,
        box_size=BOX_SIZE,
        weight_range=WEIGHT_RANGE,
        seed=SEED
    )

    print(f"Generated {len(sites)} points")
    print(f"Bounding box: [{box_min[0]}, {box_min[1]}, {box_min[2]}] to [{box_max[0]}, {box_max[1]}, {box_max[2]}]")

    # Display sample points
    print("\nSample points (first 5):")
    for i in range(min(5, len(sites))):
        x, y, z, w = sites[i]
        print(f"  Point {i}: position=({x:.2f}, {y:.2f}, {z:.2f}), weight={w:.2f}")

    # Save sites data to JSON file for Rhino script
    print(f"\nSaving point data to JSON: {JSON_FILE}")
    sites_data = {
        "n_points": N_POINTS,
        "box_size": BOX_SIZE,
        "weight_range": list(WEIGHT_RANGE),
        "seed": SEED,
        "box_min": box_min.tolist(),
        "box_max": box_max.tolist(),
        "sites": [
            {
                "index": i,
                "position": [float(sites[i][0]), float(sites[i][1]), float(sites[i][2])],
                "weight": float(sites[i][3])
            }
            for i in range(len(sites))
        ]
    }

    with open(JSON_FILE, 'w') as f:
        json.dump(sites_data, f, indent=2)
    print(f"Saved {len(sites)} points to {JSON_FILE}")

    # Compute Power Diagram (without spheres)
    print("\nComputing Laguerre Voronoi (Power Diagram)...")
    cells = compute_power_diagram(
        sites=sites,
        box_min=box_min,
        box_max=box_max,
        output_path=OUTPUT_FILE,
        export_spheres=False,  # Do not export site spheres
        export_mode='faces'    # Export cell faces only
    )

    # Also generate version with spheres for visual verification
    print(f"\nGenerating version with spheres for visual verification...")
    cells_with_spheres = compute_power_diagram(
        sites=sites,
        box_min=box_min,
        box_max=box_max,
        output_path=OUTPUT_FILE_WITH_SPHERES,
        export_spheres=True,   # Export site spheres for verification
        export_mode='faces'    # Export cell faces and spheres
    )

    # Count successful cells
    successful_cells = sum(1 for V, F in cells if V is not None)
    print(f"\nResults:")
    print(f"  Total cells: {len(cells)}")
    print(f"  Successful cells: {successful_cells}")
    print(f"  Failed cells: {len(cells) - successful_cells}")

    print("\n" + "="*60)
    print("  Computation complete!")
    print("="*60)
    print(f"\nOutput files:")
    print(f"  1. {OUTPUT_FILE} - Voronoi cells only")
    print(f"  2. {OUTPUT_FILE_WITH_SPHERES} - Voronoi cells + spheres (for verification)")
    print(f"  3. {JSON_FILE} - Point data for Rhino script")
    print("\nHow to use:")
    print("  Option A: Import OBJ with spheres to verify alignment visually")
    print(f"            File > Import > {OUTPUT_FILE_WITH_SPHERES}")
    print("  Option B: Import OBJ + Run Rhino script to create spheres")
    print(f"            1. File > Import > {OUTPUT_FILE}")
    print(f"            2. RunPythonScript > create_spheres_rhino.py")

    return cells


if __name__ == "__main__":
    cells = main()
