# -*- coding: utf-8 -*-
"""
Rhino CLI Wrapper for 6-Candidate Comparison System
Parameterized version of import2objs.py that accepts command-line arguments

Usage:
    python import2objs_cli.py --obj-a path/to/A.obj --obj-b path/to/B.obj
    python import2objs_cli.py --obj-a A.obj --obj-b B.obj --obj-a-inner A_inner.obj --spacing 1500
"""

import rhinoscriptsyntax as rs
import Rhino
import os
import sys
import argparse

#  ===== Default Configuration =====
DEFAULT_SPACING = 1000.0  # Horizontal spacing between A and B (mm)
DEFAULT_INNER_OFFSET_Y = 0.0  # Y offset for inner versions (mm)

# Layer names
LAYER_A = "IEC_A"
LAYER_B = "IEC_B"
LAYER_A_INNER = "IEC_A_Inner"
LAYER_B_INNER = "IEC_B_Inner"
LAYER_A_LINES = "IEC_A_Lines"
LAYER_B_LINES = "IEC_B_Lines"

# Line colors for XY-pair visualization
LINE_COLOR_A = (255, 0, 0)  # Red
LINE_COLOR_B = (0, 0, 255)  # Blue

# ===== Utility Functions =====
def ensure_layer(name):
    """Create layer if it doesn't exist."""
    if not rs.IsLayer(name):
        rs.AddLayer(name)


def delete_layer_objects(layer_name):
    """Delete all objects on a layer."""
    objs = rs.ObjectsByLayer(layer_name, select=False) or []
    if objs:
        rs.DeleteObjects(objs)


def import_obj(path):
    """
    Import OBJ file and return list of imported object IDs.

    Args:
        path: Absolute or relative path to OBJ file

    Returns:
        List of Rhino object GUIDs
    """
    if not os.path.exists(path):
        Rhino.RhinoApp.WriteLine("WARNING: File not found: {}".format(path))
        return []

    before = set(rs.AllObjects(select=False) or [])
    cmd = '_-Import "{}" _Enter'.format(path)
    rs.Command(cmd, echo=False)
    after = set(rs.AllObjects(select=False) or [])
    return list(after - before)


def move_objects_x(objs, dx):
    """Move objects in X direction."""
    if objs:
        rs.MoveObjects(objs, (dx, 0, 0))


def move_objects_y(objs, dy):
    """Move objects in Y direction."""
    if objs:
        rs.MoveObjects(objs, (0, dy, 0))


# ===== Main Import Function =====
def import_pair_to_rhino(obj_a, obj_b,
                        obj_a_inner=None, obj_b_inner=None,
                        obj_a_lines=None, obj_b_lines=None,
                        spacing=DEFAULT_SPACING,
                        inner_offset_y=DEFAULT_INNER_OFFSET_Y):
    """
    Import two OBJ files side-by-side to Rhino.

    Layout:
    - A: Left (x=0)
    - B: Right (x=spacing)
    - A_inner: Below A (y=inner_offset_y)
    - B_inner: Below B (x=spacing, y=inner_offset_y)
    - XY-pair lines: For both standard and inner versions

    Args:
        obj_a: Path to candidate A's mesh OBJ
        obj_b: Path to candidate B's mesh OBJ
        obj_a_inner: Path to candidate A's inner mesh OBJ (optional)
        obj_b_inner: Path to candidate B's inner mesh OBJ (optional)
        obj_a_lines: Path to candidate A's XY-pair lines OBJ (optional)
        obj_b_lines: Path to candidate B's XY-pair lines OBJ (optional)
        spacing: Horizontal spacing between A and B (mm)
        inner_offset_y: Y offset for inner versions (mm)
    """
    # Ensure layers exist
    ensure_layer(LAYER_A)
    ensure_layer(LAYER_B)
    ensure_layer(LAYER_A_INNER)
    ensure_layer(LAYER_B_INNER)
    ensure_layer(LAYER_A_LINES)
    ensure_layer(LAYER_B_LINES)

    # Clear existing objects (for refresh)
    delete_layer_objects(LAYER_A)
    delete_layer_objects(LAYER_B)
    delete_layer_objects(LAYER_A_INNER)
    delete_layer_objects(LAYER_B_INNER)
    delete_layer_objects(LAYER_A_LINES)
    delete_layer_objects(LAYER_B_LINES)

    # === Import A (standard mesh) ===
    Rhino.RhinoApp.WriteLine("Importing A.obj (standard mesh)...")
    objs_A = import_obj(obj_a)
    for o in objs_A:
        rs.ObjectLayer(o, LAYER_A)

    # === Import B (standard mesh) ===
    Rhino.RhinoApp.WriteLine("Importing B.obj (standard mesh)...")
    objs_B = import_obj(obj_b)
    for o in objs_B:
        rs.ObjectLayer(o, LAYER_B)

    # Move B to the right
    move_objects_x(objs_B, spacing)

    # === Import A_inner (if provided) ===
    if obj_a_inner and os.path.exists(obj_a_inner):
        Rhino.RhinoApp.WriteLine("Importing A_inner.obj (boundary cells removed)...")
        objs_A_inner = import_obj(obj_a_inner)
        for o in objs_A_inner:
            rs.ObjectLayer(o, LAYER_A_INNER)
        # Move down (Y direction)
        move_objects_y(objs_A_inner, inner_offset_y)
    elif obj_a_inner:
        Rhino.RhinoApp.WriteLine("WARNING: A_inner file not found: {}".format(obj_a_inner))

    # === Import B_inner (if provided) ===
    if obj_b_inner and os.path.exists(obj_b_inner):
        Rhino.RhinoApp.WriteLine("Importing B_inner.obj (boundary cells removed)...")
        objs_B_inner = import_obj(obj_b_inner)
        for o in objs_B_inner:
            rs.ObjectLayer(o, LAYER_B_INNER)
        # Move right and down
        move_objects_x(objs_B_inner, spacing)
        move_objects_y(objs_B_inner, inner_offset_y)
    elif obj_b_inner:
        Rhino.RhinoApp.WriteLine("WARNING: B_inner file not found: {}".format(obj_b_inner))

    # === Import XY-pair lines for A (if provided) ===
    if obj_a_lines and os.path.exists(obj_a_lines):
        Rhino.RhinoApp.WriteLine("Importing XY-pair lines for A (standard position)...")
        objs_A_lines = import_obj(obj_a_lines)
        for o in objs_A_lines:
            rs.ObjectLayer(o, LAYER_A_LINES)
            rs.ObjectColor(o, LINE_COLOR_A)

        # Also import for inner position (if inner mesh exists)
        if obj_a_inner and os.path.exists(obj_a_inner):
            Rhino.RhinoApp.WriteLine("Importing XY-pair lines for A_inner (offset position)...")
            objs_A_lines_inner = import_obj(obj_a_lines)
            for o in objs_A_lines_inner:
                rs.ObjectLayer(o, LAYER_A_LINES)
                rs.ObjectColor(o, LINE_COLOR_A)
            move_objects_y(objs_A_lines_inner, inner_offset_y)
    elif obj_a_lines:
        Rhino.RhinoApp.WriteLine("WARNING: A_lines file not found: {}".format(obj_a_lines))

    # === Import XY-pair lines for B (if provided) ===
    if obj_b_lines and os.path.exists(obj_b_lines):
        Rhino.RhinoApp.WriteLine("Importing XY-pair lines for B (standard position)...")
        objs_B_lines = import_obj(obj_b_lines)
        for o in objs_B_lines:
            rs.ObjectLayer(o, LAYER_B_LINES)
            rs.ObjectColor(o, LINE_COLOR_B)
        # Move right
        move_objects_x(objs_B_lines, spacing)

        # Also import for inner position (if inner mesh exists)
        if obj_b_inner and os.path.exists(obj_b_inner):
            Rhino.RhinoApp.WriteLine("Importing XY-pair lines for B_inner (offset position)...")
            objs_B_lines_inner = import_obj(obj_b_lines)
            for o in objs_B_lines_inner:
                rs.ObjectLayer(o, LAYER_B_LINES)
                rs.ObjectColor(o, LINE_COLOR_B)
            move_objects_x(objs_B_lines_inner, spacing)
            move_objects_y(objs_B_lines_inner, inner_offset_y)
    elif obj_b_lines:
        Rhino.RhinoApp.WriteLine("WARNING: B_lines file not found: {}".format(obj_b_lines))

    # Refresh display
    rs.Redraw()

    # Summary
    Rhino.RhinoApp.WriteLine("\n" + "=" * 60)
    Rhino.RhinoApp.WriteLine("Import complete!")
    Rhino.RhinoApp.WriteLine("  A (standard): Left side (x=0)")
    Rhino.RhinoApp.WriteLine("  B (standard): Right side (x={}mm)".format(spacing))
    if obj_a_inner or obj_b_inner:
        Rhino.RhinoApp.WriteLine("  Inner versions: Offset +{}mm in Y direction".format(inner_offset_y))
    Rhino.RhinoApp.WriteLine("=" * 60)


# ===== CLI Entry Point =====
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import two OBJ files side-by-side to Rhino for comparison"
    )

    # Required arguments
    parser.add_argument('--obj-a', required=True,
                       help="Path to candidate A's mesh OBJ file")
    parser.add_argument('--obj-b', required=True,
                       help="Path to candidate B's mesh OBJ file")

    # Optional arguments
    parser.add_argument('--obj-a-inner',
                       help="Path to candidate A's inner mesh OBJ file (optional)")
    parser.add_argument('--obj-b-inner',
                       help="Path to candidate B's inner mesh OBJ file (optional)")
    parser.add_argument('--obj-a-lines',
                       help="Path to candidate A's XY-pair lines OBJ file (optional)")
    parser.add_argument('--obj-b-lines',
                       help="Path to candidate B's XY-pair lines OBJ file (optional)")

    # Layout parameters
    parser.add_argument('--spacing', type=float, default=DEFAULT_SPACING,
                       help="Horizontal spacing between A and B in mm (default: {})".format(DEFAULT_SPACING))
    parser.add_argument('--inner-offset-y', type=float, default=DEFAULT_INNER_OFFSET_Y,
                       help="Y offset for inner versions in mm (default: {})".format(DEFAULT_INNER_OFFSET_Y))

    args = parser.parse_args()

    # Execute import
    import_pair_to_rhino(
        obj_a=args.obj_a,
        obj_b=args.obj_b,
        obj_a_inner=args.obj_a_inner,
        obj_b_inner=args.obj_b_inner,
        obj_a_lines=args.obj_a_lines,
        obj_b_lines=args.obj_b_lines,
        spacing=args.spacing,
        inner_offset_y=args.inner_offset_y
    )
