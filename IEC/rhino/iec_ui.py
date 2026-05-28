"""
iec_ui.py - Rhino Interface for Interactive Evolutionary Computation

This script runs inside Rhino to:
1. Import and display A.obj and B.obj side-by-side
2. Provide UI for selecting preferred form (A or B)
3. Log selection to choices.csv
4. Trigger next generation cycle

Usage (in Rhino Python editor or via RunPythonScript):
    import sys
    sys.path.append('path/to/IEC/rhino')
    import iec_ui
    iec_ui.run()
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
import os
import json
import csv
from datetime import datetime
import subprocess
import sys


# ===== Configuration =====

# Paths (relative to this script's location)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
GEN_DIR = os.path.join(PROJECT_ROOT, 'gen')
LOG_DIR = os.path.join(PROJECT_ROOT, 'log')
TOOLS_DIR = os.path.join(PROJECT_ROOT, 'tools')

OBJ_A_PATH = os.path.join(GEN_DIR, 'A.obj')
OBJ_B_PATH = os.path.join(GEN_DIR, 'B.obj')
META_A_PATH = os.path.join(GEN_DIR, 'meta_A.json')
META_B_PATH = os.path.join(GEN_DIR, 'meta_B.json')
CHOICES_CSV = os.path.join(LOG_DIR, 'choices.csv')
GENERATE_SCRIPT = os.path.join(TOOLS_DIR, 'generate_pair.py')

# Display settings
SPACING = 3.0  # Distance between A and B forms
LABEL_HEIGHT = 0.3
LABEL_OFFSET_Z = 1.5


# ===== Helper Functions =====

def clear_layer(layer_name):
    """Delete all objects in a layer."""
    if rs.IsLayer(layer_name):
        objects = rs.ObjectsByLayer(layer_name)
        if objects:
            rs.DeleteObjects(objects)


def setup_layers():
    """Create or clear layers for A, B, and labels."""
    layers = ['IEC_A', 'IEC_B', 'IEC_Labels']

    for layer in layers:
        if not rs.IsLayer(layer):
            rs.AddLayer(layer)
        else:
            clear_layer(layer)

    # Set colors
    rs.LayerColor('IEC_A', (255, 100, 100))  # Red
    rs.LayerColor('IEC_B', (100, 100, 255))  # Blue
    rs.LayerColor('IEC_Labels', (200, 200, 200))  # Gray


def import_obj_to_layer(obj_path, layer_name, offset_x=0):
    """
    Import OBJ file and move objects to specified layer.

    Args:
        obj_path: path to OBJ file
        layer_name: target layer name
        offset_x: horizontal offset for positioning

    Returns:
        list of imported object GUIDs
    """
    if not os.path.exists(obj_path):
        print("Error: {} not found".format(obj_path))
        return []

    # Import OBJ
    rs.CurrentLayer(layer_name)

    # Rhino's import command
    script = '_-Import "{}" _Enter'.format(obj_path)
    rs.Command(script, False)

    # Get newly imported objects (those on current layer)
    objects = rs.ObjectsByLayer(layer_name)

    # Apply offset
    if offset_x != 0 and objects:
        translation = (offset_x, 0, 0)
        for obj in objects:
            rs.MoveObject(obj, (0, 0, 0), translation)

    return objects if objects else []


def add_label(text, position, layer_name='IEC_Labels'):
    """Add text label at position."""
    rs.CurrentLayer(layer_name)
    text_obj = rs.AddText(text, position, height=LABEL_HEIGHT)
    return text_obj


def load_metadata(meta_path):
    """Load metadata from JSON file."""
    try:
        with open(meta_path, 'r') as f:
            data = json.load(f)
            return data.get('metadata', {})
    except Exception as e:
        print("Error loading metadata: {}".format(e))
        return {}


def log_choice(selected, meta_A, meta_B):
    """
    Log user's choice to choices.csv.

    Args:
        selected: 'A' or 'B'
        meta_A: metadata dict for A
        meta_B: metadata dict for B
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    # Check if file exists to determine if we need header
    file_exists = os.path.isfile(CHOICES_CSV)

    with open(CHOICES_CSV, 'a', newline='') as f:
        writer = csv.writer(f)

        # Write header if new file
        if not file_exists:
            writer.writerow(['timestamp', 'iteration', 'selected', 'parent_hash',
                           'hash_A', 'hash_B', 'n_points_A', 'n_points_B'])

        # Write selection data
        timestamp = datetime.now().isoformat()
        iteration = meta_A.get('iteration', 0)  # Both should have same iteration
        parent_hash = meta_A.get('parent_hash', 'null')
        hash_A = meta_A.get('hash', '')
        hash_B = meta_B.get('hash', '')
        n_points_A = meta_A.get('n_points', 0)
        n_points_B = meta_B.get('n_points', 0)

        writer.writerow([timestamp, iteration, selected, parent_hash,
                        hash_A, hash_B, n_points_A, n_points_B])

    print("Logged choice: {} at iteration {}".format(selected, iteration))


def trigger_next_generation(selected):
    """
    Call generate_pair.py with selected parent to create next generation.

    Args:
        selected: 'A' or 'B'
    """
    parent_path = META_A_PATH if selected == 'A' else META_B_PATH

    print("\nGenerating next generation from {}...".format(selected))

    # Build command
    python_exe = sys.executable  # Use same Python as Rhino
    cmd = [python_exe, GENERATE_SCRIPT, '--parent', parent_path]

    try:
        # Run generation script
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=TOOLS_DIR)

        print(result.stdout)
        if result.stderr:
            print("Errors:\n{}".format(result.stderr))

        if result.returncode == 0:
            print("\n✓ Next generation ready!")
            return True
        else:
            print("\n✗ Generation failed with code {}".format(result.returncode))
            return False

    except Exception as e:
        print("Error running generation script: {}".format(e))
        return False


# ===== Main Display Function =====

def display_pair():
    """
    Import and display A and B forms side-by-side.

    Returns:
        (meta_A, meta_B) metadata dicts
    """
    print("\n" + "="*50)
    print("IEC - Interactive Evolutionary Computation")
    print("="*50)

    # Setup layers
    setup_layers()

    # Load metadata
    meta_A = load_metadata(META_A_PATH)
    meta_B = load_metadata(META_B_PATH)

    iteration = meta_A.get('iteration', 0)
    print("\nIteration: {}".format(iteration))
    print("  A: {} points, hash={}".format(meta_A.get('n_points', '?'),
                                          meta_A.get('hash', '?')))
    print("  B: {} points, hash={}".format(meta_B.get('n_points', '?'),
                                          meta_B.get('hash', '?')))

    # Import forms
    print("\nImporting forms...")
    offset = SPACING / 2

    objs_A = import_obj_to_layer(OBJ_A_PATH, 'IEC_A', offset_x=-offset)
    objs_B = import_obj_to_layer(OBJ_B_PATH, 'IEC_B', offset_x=offset)

    # Add labels
    add_label("A", (-offset, 0, LABEL_OFFSET_Z))
    add_label("B", (offset, 0, LABEL_OFFSET_Z))

    # Zoom to extents
    rs.Command("_ZoomExtents", False)

    print("\n✓ Display complete!")
    print("\nForms A and B are now displayed.")
    print("Select your preferred form:")

    return meta_A, meta_B


# ===== Selection UI =====

def prompt_selection():
    """
    Prompt user to select A or B.

    Returns:
        'A', 'B', or None (if cancelled)
    """
    choice = rs.GetString("Select preferred form", "A", ["A", "B"])
    return choice


def run_selection_cycle(meta_A, meta_B):
    """
    Run one selection cycle: prompt, log, and generate next.

    Args:
        meta_A, meta_B: metadata dicts

    Returns:
        True if should continue, False to exit
    """
    # Get user selection
    selected = prompt_selection()

    if selected is None:
        print("\nSelection cancelled.")
        return False

    print("\nYou selected: {}".format(selected))

    # Log choice
    log_choice(selected, meta_A, meta_B)

    # Ask if user wants to continue
    continue_prompt = rs.GetString("Generate next generation?", "Yes", ["Yes", "No"])

    if continue_prompt == "No":
        print("\nEvolution stopped by user.")
        return False

    # Generate next generation
    success = trigger_next_generation(selected)

    if not success:
        print("\nGeneration failed. Stopping evolution.")
        return False

    # Ask if user wants to view next generation
    view_next = rs.GetString("Display next generation now?", "Yes", ["Yes", "No"])

    return view_next == "Yes"


# ===== Main Entry Point =====

def run():
    """
    Main entry point for IEC UI.
    Displays pair and enters selection loop.
    """
    # Check if generation exists
    if not os.path.exists(OBJ_A_PATH) or not os.path.exists(OBJ_B_PATH):
        print("Error: No generation found in {}".format(GEN_DIR))
        print("\nPlease run:")
        print("  python tools/generate_pair.py --init")
        return

    # Initial display
    meta_A, meta_B = display_pair()

    # Selection loop
    while True:
        should_continue = run_selection_cycle(meta_A, meta_B)

        if not should_continue:
            break

        # Reload display for next generation
        meta_A, meta_B = display_pair()

    print("\n" + "="*50)
    print("IEC session ended.")
    print("Log saved to: {}".format(CHOICES_CSV))
    print("="*50)


# ===== Quick Commands =====

def display_only():
    """Just display current generation without selection loop."""
    display_pair()


def select_A():
    """Quick select A and generate next."""
    meta_A = load_metadata(META_A_PATH)
    meta_B = load_metadata(META_B_PATH)
    log_choice('A', meta_A, meta_B)
    trigger_next_generation('A')
    print("\nRun display_pair() or run() to see next generation.")


def select_B():
    """Quick select B and generate next."""
    meta_A = load_metadata(META_A_PATH)
    meta_B = load_metadata(META_B_PATH)
    log_choice('B', meta_A, meta_B)
    trigger_next_generation('B')
    print("\nRun display_pair() or run() to see next generation.")


# ===== Auto-run if executed directly =====

if __name__ == '__main__':
    run()
