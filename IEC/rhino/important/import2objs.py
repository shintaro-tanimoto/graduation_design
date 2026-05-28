# -*- coding: utf-8 -*-

import rhinoscriptsyntax as rs
import Rhino
import os

# ===== 設定 =====
# File paths - HARDCODED (for tournament comparison)
BASE_DIR = r"\\wsl$\Ubuntu\home\shint\py_code\IEC\rhino\temp"
A_OBJ = BASE_DIR + r"\A_mesh.obj"
B_OBJ = BASE_DIR + r"\B_mesh.obj"
A_LINES_OBJ = BASE_DIR + r"\A_lines.obj"
B_LINES_OBJ = BASE_DIR + r"\B_lines.obj"

# Note: Inner variants removed - we now use A_mesh.obj/B_mesh.obj directly
# (which are copies of mesh_inner.obj from the tournament)

LAYER_A = "IEC_A"
LAYER_B = "IEC_B"
LAYER_A_LINES = "IEC_A_Lines"
LAYER_B_LINES = "IEC_B_Lines"

# 横並び距離（mm）
OFFSET_X = 1000.0

# Inner版のY方向オフセット（mm）
OFFSET_Y = 0.0

# XYペア線の表示色
LINE_COLOR_A = (255, 0, 0)  # 赤
LINE_COLOR_B = (0, 0, 255)  # 青

# ===== ユーティリティ =====
def ensure_layer(name):
    if not rs.IsLayer(name):
        rs.AddLayer(name)

def delete_layer_objects(layer_name):
    objs = rs.ObjectsByLayer(layer_name, select=False) or []
    if objs:
        rs.DeleteObjects(objs)

def import_obj(path):
    before = set(rs.AllObjects(select=False) or [])
    cmd = '_-Import "{}" _Enter'.format(path)
    rs.Command(cmd, echo=False)
    after = set(rs.AllObjects(select=False) or [])
    return list(after - before)

def move_objects_x(objs, dx):
    if objs:
        rs.MoveObjects(objs, (dx, 0, 0))

def move_objects_y(objs, dy):
    if objs:
        rs.MoveObjects(objs, (0, dy, 0))

# ===== メイン =====
def import_ab_side_by_side():
    """Import A and B meshes/lines side by side with fixed file names."""

    # Clear existing layers
    for layer in [LAYER_A, LAYER_B, LAYER_A_LINES, LAYER_B_LINES]:
        delete_layer_objects(layer)

    # --- Import A mesh ---
    if os.path.exists(A_OBJ):
        ensure_layer(LAYER_A)
        Rhino.RhinoApp.WriteLine("Importing A_mesh.obj...")
        objs_a = import_obj(A_OBJ)
        if objs_a:
            move_objects_x(objs_a, -OFFSET_X / 2.0)  # Move left
            for obj in objs_a:
                rs.ObjectLayer(obj, LAYER_A)
            Rhino.RhinoApp.WriteLine("Imported A mesh: {} objects".format(len(objs_a)))
    else:
        Rhino.RhinoApp.WriteLine("WARNING: A mesh not found: {}".format(A_OBJ))

    # --- Import B mesh ---
    if os.path.exists(B_OBJ):
        ensure_layer(LAYER_B)
        Rhino.RhinoApp.WriteLine("Importing B_mesh.obj...")
        objs_b = import_obj(B_OBJ)
        if objs_b:
            move_objects_x(objs_b, OFFSET_X / 2.0)  # Move right
            for obj in objs_b:
                rs.ObjectLayer(obj, LAYER_B)
            Rhino.RhinoApp.WriteLine("Imported B mesh: {} objects".format(len(objs_b)))
    else:
        Rhino.RhinoApp.WriteLine("WARNING: B mesh not found: {}".format(B_OBJ))

    # --- Import A lines (optional) ---
    if os.path.exists(A_LINES_OBJ):
        ensure_layer(LAYER_A_LINES)
        Rhino.RhinoApp.WriteLine("Importing A_lines.obj...")
        objs_a_lines = import_obj(A_LINES_OBJ)
        if objs_a_lines:
            move_objects_x(objs_a_lines, -OFFSET_X / 2.0)  # Move left
            move_objects_y(objs_a_lines, OFFSET_Y)  # Move down
            for obj in objs_a_lines:
                rs.ObjectLayer(obj, LAYER_A_LINES)
                rs.ObjectColor(obj, LINE_COLOR_A)  # Red
            Rhino.RhinoApp.WriteLine("Imported A lines: {} objects".format(len(objs_a_lines)))

    # --- Import B lines (optional) ---
    if os.path.exists(B_LINES_OBJ):
        ensure_layer(LAYER_B_LINES)
        Rhino.RhinoApp.WriteLine("Importing B_lines.obj...")
        objs_b_lines = import_obj(B_LINES_OBJ)
        if objs_b_lines:
            move_objects_x(objs_b_lines, OFFSET_X / 2.0)  # Move right
            move_objects_y(objs_b_lines, OFFSET_Y)  # Move down
            for obj in objs_b_lines:
                rs.ObjectLayer(obj, LAYER_B_LINES)
                rs.ObjectColor(obj, LINE_COLOR_B)  # Blue
            Rhino.RhinoApp.WriteLine("Imported B lines: {} objects".format(len(objs_b_lines)))

    rs.ZoomExtents()
    Rhino.RhinoApp.WriteLine("Import complete!")

import_ab_side_by_side()