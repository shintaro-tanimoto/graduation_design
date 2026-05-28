"""
Rhino script to create spheres at weighted point locations.

This script:
1. Reads point data from sites_data.json
2. Creates a sphere at each point location with radius proportional to weight
3. Organizes spheres in a layer for easy management

Usage:
1. Open Rhino
2. Type 'RunPythonScript' in the command line
3. Select this file (create_spheres_rhino.py)
4. The script will create spheres and display summary information

Note: This script must be run from within Rhino, not from the command line.
"""

import rhinoscriptsyntax as rs
import json
import os
import sys

def load_sites_data(json_path):
    """
    Load point data from JSON file.

    Args:
        json_path: Path to the JSON file containing site data

    Returns:
        dict: Site data including points, weights, and metadata
    """
    if not os.path.exists(json_path):
        print("Error: JSON file not found at: {}".format(json_path))
        return None

    with open(json_path, 'r') as f:
        data = json.load(f)

    return data


def create_spheres_from_data(sites_data, layer_name="LaguerreSpheres", radius_scale=1.0):
    """
    Create spheres at each site location with radius proportional to weight.

    Args:
        sites_data: Dictionary containing site data
        layer_name: Name of the layer to create spheres in
        radius_scale: Scale factor for sphere radii (default: 1.0)

    Returns:
        list: List of sphere object GUIDs
    """
    if sites_data is None:
        return []

    # Create or get layer
    if not rs.IsLayer(layer_name):
        rs.AddLayer(layer_name)

    # Set current layer
    rs.CurrentLayer(layer_name)

    sites = sites_data.get('sites', [])
    sphere_guids = []

    print("\n" + "="*60)
    print("  Creating Spheres in Rhino")
    print("="*60)
    print("Configuration:")
    print("  Number of points: {}".format(sites_data.get('n_points', 0)))
    print("  Bounding box: {}x{}x{}".format(
        sites_data.get('box_size', 0),
        sites_data.get('box_size', 0),
        sites_data.get('box_size', 0)
    ))
    print("  Weight range: {} - {}".format(
        sites_data.get('weight_range', [0, 0])[0],
        sites_data.get('weight_range', [0, 0])[1]
    ))
    print("  Radius scale: {}".format(radius_scale))
    print("  Layer: {}".format(layer_name))
    print("="*60)

    # Create spheres
    for site in sites:
        index = site['index']
        position = site['position']
        weight = site['weight']

        # Sphere radius = weight * radius_scale
        radius = weight * radius_scale

        # Create sphere at position
        sphere = rs.AddSphere(position, radius)

        if sphere:
            sphere_guids.append(sphere)
            if index < 5:  # Print first 5 spheres
                print("  Sphere {}: position=({:.2f}, {:.2f}, {:.2f}), radius={:.2f}".format(
                    index, position[0], position[1], position[2], radius
                ))

    print("\n" + "="*60)
    print("  Creation Complete!")
    print("="*60)
    print("Created {} spheres in layer '{}'".format(len(sphere_guids), layer_name))
    print("\nTips:")
    print("  - Use 'SelLayer' command to select all spheres")
    print("  - Use 'Hide' command to hide spheres temporarily")
    print("  - Adjust radius_scale parameter if spheres are too large/small")

    return sphere_guids


def main():
    """Main function to run the sphere creation process."""

    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Path to JSON file (relative to script location)
    json_path = os.path.join(script_dir, "sites_data.json")

    # Alternative: Allow user to select JSON file
    # json_path = rs.OpenFileName("Select sites data JSON file", "JSON files (*.json)|*.json||")
    # if not json_path:
    #     print("No file selected. Exiting.")
    #     return

    print("Loading point data from: {}".format(json_path))

    # Load site data
    sites_data = load_sites_data(json_path)

    if sites_data is None:
        print("Failed to load site data. Exiting.")
        return

    # Confirm with user
    result = rs.MessageBox(
        "Create {} spheres from {}?\n\nThis will create a new layer 'LaguerreSpheres'.\n\nContinue?".format(
            sites_data.get('n_points', 0),
            os.path.basename(json_path)
        ),
        buttons=4 | 32,  # Yes/No + Question icon
        title="Create Spheres"
    )

    if result != 6:  # 6 = Yes
        print("Operation cancelled by user.")
        return

    # Create spheres with radius = weight
    # Adjust radius_scale if needed (e.g., 0.5 for half size, 2.0 for double size)
    sphere_guids = create_spheres_from_data(
        sites_data=sites_data,
        layer_name="LaguerreSpheres",
        radius_scale=1.0  # Change this to adjust sphere sizes
    )

    # Zoom to show all objects
    if sphere_guids:
        rs.ZoomExtents()
        rs.Redraw()

    print("\nScript completed successfully!")


# Run the main function when script is executed
if __name__ == "__main__":
    main()
