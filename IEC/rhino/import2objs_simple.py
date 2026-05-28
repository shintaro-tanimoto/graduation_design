# -*- coding: utf-8 -*-
"""
Rhino Simple Import Script for 6-Candidate Comparison System
Edit the paths below and run this script in Rhino

Usage in Rhino:
    _-RunPythonScript "path/to/import2objs_simple.py"
"""

import rhinoscriptsyntax as rs
import Rhino
import os

# ===== EDIT THESE PATHS =====
OBJ_A = "/home/shint/py_code/IEC/gen_history/gen_000/population/cand_05/mesh_inner.obj"
OBJ_B = "/home/shint/py_code/IEC/gen_history/gen_000/population/cand_03/mesh_inner.obj"

# Optional: Set these if you want to import inner meshes or lines
OBJ_A_INNER = None  # e.g., "/path/to/cand_05/mesh_inner.obj"
OBJ_B_INNER = None
OBJ_A_LINES = None
OBJ_B_LINES = None

# Layout parameters
SPACING = 1000.0  # Horizontal spacing between A and B (mm)
INNER_OFFSET_Y = 1000.0  # Y offset for inner versions (mm)
# ============================

# Layer names
LAYER_A = "IEC_A"
LAYER_B = "IEC_B"
LAYER_A_INNER = "IEC_A_Inner"
LAYER_B_INNER = "IEC_B_Inner"
LAYER_A_LINES = "IEC_A_Lines"
LAYER_B_LINES = "IEC_B_Lines"

# Line colors
LINE_COLOR_A = (255, 0, 0)
LINE_COLOR_B = (0, 0, 255)


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
    """Import OBJ file and return list of imported object IDs."""
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


# ===== Main Import =====
def main():
    """Main import function."""
    Rhino.RhinoApp.WriteLine("\n" + "=" * 60)
    Rhino.RhinoApp.WriteLine("IEC Comparison Import - Simple Version")
    Rhino.RhinoApp.WriteLine("=" * 60)

    # Ensure layers exist
    ensure_layer(LAYER_A)
    ensure_layer(LAYER_B)
    ensure_layer(LAYER_A_INNER)
    ensure_layer(LAYER_B_INNER)
    ensure_layer(LAYER_A_LINES)
    ensure_layer(LAYER_B_LINES)

    # Clear existing objects
    delete_layer_objects(LAYER_A)
    delete_layer_objects(LAYER_B)
    delete_layer_objects(LAYER_A_INNER)
    delete_layer_objects(LAYER_B_INNER)
    delete_layer_objects(LAYER_A_LINES)
    delete_layer_objects(LAYER_B_LINES)

    # Import A
    Rhino.RhinoApp.WriteLine("\nImporting A: {}".format(OBJ_A))
    objs_A = import_obj(OBJ_A)
    for o in objs_A:
        rs.ObjectLayer(o, LAYER_A)
    Rhino.RhinoApp.WriteLine("  Imported {} objects to layer {}".format(len(objs_A), LAYER_A))

    # Import B
    Rhino.RhinoApp.WriteLine("\nImporting B: {}".format(OBJ_B))
    objs_B = import_obj(OBJ_B)
    for o in objs_B:
        rs.ObjectLayer(o, LAYER_B)
    move_objects_x(objs_B, SPACING)
    Rhino.RhinoApp.WriteLine("  Imported {} objects to layer {}".format(len(objs_B), LAYER_B))

    # Import A_inner (optional)
    if OBJ_A_INNER and os.path.exists(OBJ_A_INNER):
        Rhino.RhinoApp.WriteLine("\nImporting A_inner: {}".format(OBJ_A_INNER))
        objs_A_inner = import_obj(OBJ_A_INNER)
        for o in objs_A_inner:
            rs.ObjectLayer(o, LAYER_A_INNER)
        move_objects_y(objs_A_inner, INNER_OFFSET_Y)
        Rhino.RhinoApp.WriteLine("  Imported {} objects to layer {}".format(len(objs_A_inner), LAYER_A_INNER))

    # Import B_inner (optional)
    if OBJ_B_INNER and os.path.exists(OBJ_B_INNER):
        Rhino.RhinoApp.WriteLine("\nImporting B_inner: {}".format(OBJ_B_INNER))
        objs_B_inner = import_obj(OBJ_B_INNER)
        for o in objs_B_inner:
            rs.ObjectLayer(o, LAYER_B_INNER)
        move_objects_x(objs_B_inner, SPACING)
        move_objects_y(objs_B_inner, INNER_OFFSET_Y)
        Rhino.RhinoApp.WriteLine("  Imported {} objects to layer {}".format(len(objs_B_inner), LAYER_B_INNER))

    # Import XY-pair lines for A (optional)
    if OBJ_A_LINES and os.path.exists(OBJ_A_LINES):
        Rhino.RhinoApp.WriteLine("\nImporting A_lines: {}".format(OBJ_A_LINES))
        objs_A_lines = import_obj(OBJ_A_LINES)
        for o in objs_A_lines:
            rs.ObjectLayer(o, LAYER_A_LINES)
            rs.ObjectColor(o, LINE_COLOR_A)

        # Also import for inner position (if inner mesh exists)
        if OBJ_A_INNER and os.path.exists(OBJ_A_INNER):
            objs_A_lines_inner = import_obj(OBJ_A_LINES)
            for o in objs_A_lines_inner:
                rs.ObjectLayer(o, LAYER_A_LINES)
                rs.ObjectColor(o, LINE_COLOR_A)
            move_objects_y(objs_A_lines_inner, INNER_OFFSET_Y)

    # Import XY-pair lines for B (optional)
    if OBJ_B_LINES and os.path.exists(OBJ_B_LINES):
        Rhino.RhinoApp.WriteLine("\nImporting B_lines: {}".format(OBJ_B_LINES))
        objs_B_lines = import_obj(OBJ_B_LINES)
        for o in objs_B_lines:
            rs.ObjectLayer(o, LAYER_B_LINES)
            rs.ObjectColor(o, LINE_COLOR_B)
        move_objects_x(objs_B_lines, SPACING)

        # Also import for inner position (if inner mesh exists)
        if OBJ_B_INNER and os.path.exists(OBJ_B_INNER):
            objs_B_lines_inner = import_obj(OBJ_B_LINES)
            for o in objs_B_lines_inner:
                rs.ObjectLayer(o, LAYER_B_LINES)
                rs.ObjectColor(o, LINE_COLOR_B)
            move_objects_x(objs_B_lines_inner, SPACING)
            move_objects_y(objs_B_lines_inner, INNER_OFFSET_Y)

    # Refresh display
    rs.Redraw()

    # Summary
    Rhino.RhinoApp.WriteLine("\n" + "=" * 60)
    Rhino.RhinoApp.WriteLine("Import complete!")
    Rhino.RhinoApp.WriteLine("  A: Left side (x=0) - Layer: {}".format(LAYER_A))
    Rhino.RhinoApp.WriteLine("  B: Right side (x={}mm) - Layer: {}".format(SPACING, LAYER_B))
    if OBJ_A_INNER or OBJ_B_INNER:
        Rhino.RhinoApp.WriteLine("  Inner versions: Offset +{}mm in Y direction".format(INNER_OFFSET_Y))
    Rhino.RhinoApp.WriteLine("=" * 60)


# Run main
if __name__ == "__main__":
    main()
