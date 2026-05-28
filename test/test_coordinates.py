#!/usr/bin/env python3
"""
Test script to verify coordinate alignment between JSON and OBJ files.
"""

import sys
import os
import numpy as np
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LaguerreVoronoi import compute_power_diagram

# Load JSON data
with open('test/sites_data.json', 'r') as f:
    data = json.load(f)

print("="*60)
print("  Coordinate Verification Test")
print("="*60)

# Extract points from JSON
sites = []
for site in data['sites']:
    pos = site['position']
    weight = site['weight']
    sites.append([pos[0], pos[1], pos[2], weight])

sites = np.array(sites)

print(f"\nTotal points in JSON: {len(sites)}")
print("\nFirst 5 points from JSON:")
for i in range(min(5, len(sites))):
    x, y, z, w = sites[i]
    print(f"  Point {i}: ({x:.2f}, {y:.2f}, {z:.2f}), weight={w:.2f}")

# Generate OBJ with spheres to verify coordinates
print("\nGenerating test OBJ with spheres...")
box_min = np.array([0.0, 0.0, 0.0])
box_max = np.array([1000.0, 1000.0, 1000.0])

compute_power_diagram(
    sites=sites,
    box_min=box_min,
    box_max=box_max,
    output_path="test/test_with_spheres.obj",
    export_spheres=True,  # Export spheres to verify coordinates
    export_mode='faces'
)

print("\n" + "="*60)
print("  Checking sphere centers in OBJ file")
print("="*60)

# Parse OBJ file to find sphere groups
with open('test/test_with_spheres.obj', 'r') as f:
    lines = f.readlines()

sphere_groups = {}
current_group = None
vertices = []

for line in lines:
    line = line.strip()
    if line.startswith('v '):
        # Parse vertex
        parts = line.split()
        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
        vertices.append([x, y, z])
    elif line.startswith('g sphere_'):
        # Start of sphere group
        sphere_idx = int(line.split('_')[1])
        sphere_groups[sphere_idx] = len(vertices)  # Index of first vertex

print(f"\nFound {len(sphere_groups)} sphere groups in OBJ")
print("\nSphere centers (computed from first vertex of each sphere):")

for i in range(min(5, len(sphere_groups))):
    if i in sphere_groups:
        first_vert_idx = sphere_groups[i]
        # First vertex of sphere should be close to center
        vert = vertices[first_vert_idx]

        # Compare with JSON
        json_pos = sites[i][:3]

        print(f"\nSphere {i}:")
        print(f"  JSON:     ({json_pos[0]:.2f}, {json_pos[1]:.2f}, {json_pos[2]:.2f})")
        print(f"  OBJ vert: ({vert[0]:.2f}, {vert[1]:.2f}, {vert[2]:.2f})")

        # Calculate difference
        diff = np.array(vert) - json_pos
        dist = np.linalg.norm(diff)
        print(f"  Distance: {dist:.2f}")

print("\n" + "="*60)
print("If distances are small (<100), coordinates are aligned.")
print("="*60)
