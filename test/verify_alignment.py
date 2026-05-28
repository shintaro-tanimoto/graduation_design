#!/usr/bin/env python3
"""
Verify that seed points are inside their corresponding Voronoi cells.
"""

import sys
import os
import numpy as np
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LaguerreVoronoi import compute_cell_polyhedron

# Load JSON data
with open('test/sites_data.json', 'r') as f:
    data = json.load(f)

print("="*60)
print("  Verifying Point-to-Cell Alignment")
print("="*60)

# Extract points and weights
points = []
weights = []
for site in data['sites']:
    pos = site['position']
    weight = site['weight']
    points.append(pos)
    weights.append(weight)

points = np.array(points)
weights = np.array(weights)

box_min = np.array(data['box_min'])
box_max = np.array(data['box_max'])

print(f"\nTotal points: {len(points)}")
print(f"Bounding box: [{box_min[0]}, {box_min[1]}, {box_min[2]}] to [{box_max[0]}, {box_max[1]}, {box_max[2]}]")

# Check first 5 points
print("\n" + "="*60)
print("  Checking if seed points are inside their cells")
print("="*60)

for i in range(min(5, len(points))):
    # Compute cell for this point
    verts, faces = compute_cell_polyhedron(points, weights, i, box_min, box_max, debug=False)

    if verts is None:
        print(f"\nPoint {i}: FAILED to compute cell")
        continue

    # Check if seed point is inside the cell
    seed = points[i]

    # Calculate cell center (centroid)
    centroid = np.mean(verts, axis=0)

    # Calculate distance from seed to centroid
    distance = np.linalg.norm(seed - centroid)

    # Calculate cell bounding box
    cell_min = verts.min(axis=0)
    cell_max = verts.max(axis=0)

    # Check if seed is within cell bounding box
    inside_bbox = np.all(seed >= cell_min - 1e-6) and np.all(seed <= cell_max + 1e-6)

    print(f"\nPoint {i}:")
    print(f"  Seed position:  ({seed[0]:.2f}, {seed[1]:.2f}, {seed[2]:.2f})")
    print(f"  Cell centroid:  ({centroid[0]:.2f}, {centroid[1]:.2f}, {centroid[2]:.2f})")
    print(f"  Distance:       {distance:.2f}")
    print(f"  Cell bbox:      ({cell_min[0]:.2f}, {cell_min[1]:.2f}, {cell_min[2]:.2f}) to")
    print(f"                  ({cell_max[0]:.2f}, {cell_max[1]:.2f}, {cell_max[2]:.2f})")
    print(f"  Inside bbox:    {'YES' if inside_bbox else 'NO'}")

print("\n" + "="*60)
print("  Summary")
print("="*60)
print("If seed points are inside their cell bounding boxes,")
print("the coordinates are correctly aligned.")
print("\nNote: For Laguerre Voronoi (weighted), the seed point")
print("may not be at the cell centroid due to the weight influence.")
print("="*60)
