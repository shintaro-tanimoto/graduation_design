# -*- coding: utf-8 -*-
"""
import_gen_log.py - Import A and B from a specific generation in gen_log

Usage in Rhino Python Editor:
    1. Run: RunPythonScript "import_gen_log.py"
    2. Enter generation number when prompted (e.g., 0, 5, 10, 15)
"""

import rhinoscriptsyntax as rs
import Rhino
import os

# ===== 設定 =====
# パス設定
GEN_LOG_DIR = r"\\wsl$\Ubuntu\home\shint\py_code\IEC\gen_log"

# レイヤー名
LAYER_A = "GenLog_A"
LAYER_B = "GenLog_B"
LAYER_A_INNER = "GenLog_A_Inner"
LAYER_B_INNER = "GenLog_B_Inner"
LAYER_A_LINES = "GenLog_A_Lines"
LAYER_B_LINES = "GenLog_B_Lines"

# 横並び距離（mm）
OFFSET_X = 1000.0

# Inner版のY方向オフセット（mm）
OFFSET_Y = 1000.0

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
def import_gen_log():
    """Import generation A and B from gen_log."""

    # Rhino上で世代番号を入力
    gen_number = rs.GetInteger("Enter generation number to import (e.g., 0, 5, 10, 15)", 0, 0, 100)

    if gen_number is None:
        Rhino.RhinoApp.WriteLine("Import cancelled by user")
        return

    # レイヤー作成
    ensure_layer(LAYER_A)
    ensure_layer(LAYER_B)
    ensure_layer(LAYER_A_INNER)
    ensure_layer(LAYER_B_INNER)
    ensure_layer(LAYER_A_LINES)
    ensure_layer(LAYER_B_LINES)

    # 既存を削除
    delete_layer_objects(LAYER_A)
    delete_layer_objects(LAYER_B)
    delete_layer_objects(LAYER_A_INNER)
    delete_layer_objects(LAYER_B_INNER)
    delete_layer_objects(LAYER_A_LINES)
    delete_layer_objects(LAYER_B_LINES)

    Rhino.RhinoApp.WriteLine("=" * 60)
    Rhino.RhinoApp.WriteLine("Importing generation {} from gen_log".format(gen_number))
    Rhino.RhinoApp.WriteLine("=" * 60)

    # ファイルパス
    A_OBJ = os.path.join(GEN_LOG_DIR, "gen{}_A.obj".format(gen_number))
    B_OBJ = os.path.join(GEN_LOG_DIR, "gen{}_B.obj".format(gen_number))
    A_INNER_OBJ = os.path.join(GEN_LOG_DIR, "gen{}_A_inner.obj".format(gen_number))
    B_INNER_OBJ = os.path.join(GEN_LOG_DIR, "gen{}_B_inner.obj".format(gen_number))
    A_LINES_OBJ = os.path.join(GEN_LOG_DIR, "gen{}_A_xy_lines.obj".format(gen_number))
    B_LINES_OBJ = os.path.join(GEN_LOG_DIR, "gen{}_B_xy_lines.obj".format(gen_number))

    # A をインポート（通常版）
    if os.path.exists(A_OBJ):
        Rhino.RhinoApp.WriteLine("Importing gen{}_A.obj...".format(gen_number))
        objs_A = import_obj(A_OBJ)
        for o in objs_A:
            rs.ObjectLayer(o, LAYER_A)
    else:
        Rhino.RhinoApp.WriteLine("ERROR: {} not found".format(A_OBJ))
        return

    # B をインポート（通常版）
    if os.path.exists(B_OBJ):
        Rhino.RhinoApp.WriteLine("Importing gen{}_B.obj...".format(gen_number))
        objs_B = import_obj(B_OBJ)
        for o in objs_B:
            rs.ObjectLayer(o, LAYER_B)
        move_objects_x(objs_B, OFFSET_X)
    else:
        Rhino.RhinoApp.WriteLine("ERROR: {} not found".format(B_OBJ))
        return

    # A_inner をインポート（存在する場合）
    if os.path.exists(A_INNER_OBJ):
        Rhino.RhinoApp.WriteLine("Importing gen{}_A_inner.obj...".format(gen_number))
        objs_A_inner = import_obj(A_INNER_OBJ)
        for o in objs_A_inner:
            rs.ObjectLayer(o, LAYER_A_INNER)
        move_objects_y(objs_A_inner, OFFSET_Y)
    else:
        Rhino.RhinoApp.WriteLine("gen{}_A_inner.obj not found (skipping)".format(gen_number))

    # B_inner をインポート（存在する場合）
    if os.path.exists(B_INNER_OBJ):
        Rhino.RhinoApp.WriteLine("Importing gen{}_B_inner.obj...".format(gen_number))
        objs_B_inner = import_obj(B_INNER_OBJ)
        for o in objs_B_inner:
            rs.ObjectLayer(o, LAYER_B_INNER)
        move_objects_x(objs_B_inner, OFFSET_X)
        move_objects_y(objs_B_inner, OFFSET_Y)
    else:
        Rhino.RhinoApp.WriteLine("gen{}_B_inner.obj not found (skipping)".format(gen_number))

    # XYペア線をインポート（A）
    if os.path.exists(A_LINES_OBJ):
        Rhino.RhinoApp.WriteLine("Importing XY-pair lines for A (standard position)...")
        objs_A_lines = import_obj(A_LINES_OBJ)
        for o in objs_A_lines:
            rs.ObjectLayer(o, LAYER_A_LINES)
            rs.ObjectColor(o, LINE_COLOR_A)

        if os.path.exists(A_INNER_OBJ):
            Rhino.RhinoApp.WriteLine("Importing XY-pair lines for A_inner (offset position)...")
            objs_A_lines_inner = import_obj(A_LINES_OBJ)
            for o in objs_A_lines_inner:
                rs.ObjectLayer(o, LAYER_A_LINES)
                rs.ObjectColor(o, LINE_COLOR_A)
            move_objects_y(objs_A_lines_inner, OFFSET_Y)
    else:
        Rhino.RhinoApp.WriteLine("gen{}_A_xy_lines.obj not found (skipping)".format(gen_number))

    # XYペア線をインポート（B）
    if os.path.exists(B_LINES_OBJ):
        Rhino.RhinoApp.WriteLine("Importing XY-pair lines for B (standard position)...")
        objs_B_lines = import_obj(B_LINES_OBJ)
        for o in objs_B_lines:
            rs.ObjectLayer(o, LAYER_B_LINES)
            rs.ObjectColor(o, LINE_COLOR_B)
        move_objects_x(objs_B_lines, OFFSET_X)

        if os.path.exists(B_INNER_OBJ):
            Rhino.RhinoApp.WriteLine("Importing XY-pair lines for B_inner (offset position)...")
            objs_B_lines_inner = import_obj(B_LINES_OBJ)
            for o in objs_B_lines_inner:
                rs.ObjectLayer(o, LAYER_B_LINES)
                rs.ObjectColor(o, LINE_COLOR_B)
            move_objects_x(objs_B_lines_inner, OFFSET_X)
            move_objects_y(objs_B_lines_inner, OFFSET_Y)
    else:
        Rhino.RhinoApp.WriteLine("gen{}_B_xy_lines.obj not found (skipping)".format(gen_number))

    rs.Redraw()
    Rhino.RhinoApp.WriteLine("=" * 60)
    Rhino.RhinoApp.WriteLine("Import complete!")
    Rhino.RhinoApp.WriteLine("  Generation {} - A (left) vs B (right)".format(gen_number))
    Rhino.RhinoApp.WriteLine("  Inner versions offset +{}mm in Y direction".format(OFFSET_Y))
    Rhino.RhinoApp.WriteLine("=" * 60)

# 実行
import_gen_log()
