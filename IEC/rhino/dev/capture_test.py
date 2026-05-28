# -*- coding: utf-8 -*-
"""
capture_test.py - Test script to capture a single screenshot with transparent background

Usage in Rhino Python Editor:
    1. Run: RunPythonScript "capture_test.py"
    2. Check output in gen_log/screenshots/gen0_A_inner.png
"""

import rhinoscriptsyntax as rs
import Rhino
import scriptcontext as sc
import System
import os

# ===== 設定 =====
# パス設定
GEN_LOG_DIR = r"\\wsl$\Ubuntu\home\shint\py_code\IEC\gen_log"
SCREENSHOTS_DIR = os.path.join(GEN_LOG_DIR, "screenshots")

# テスト用ファイル
TEST_OBJ = os.path.join(GEN_LOG_DIR, "gen0_A_inner.obj")
OUTPUT_PNG = os.path.join(SCREENSHOTS_DIR, "gen0_A_inner.png")

# レイヤー名
LAYER_NAME = "Screenshot_Temp"

# 画像サイズ
IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080

# ===== ユーティリティ =====
def ensure_layer(name):
    """レイヤーが存在しない場合は作成"""
    if not rs.IsLayer(name):
        rs.AddLayer(name)

def clear_layer(layer_name):
    """レイヤー内のオブジェクトを全削除"""
    if rs.IsLayer(layer_name):
        objs = rs.ObjectsByLayer(layer_name, select=False) or []
        if objs:
            rs.DeleteObjects(objs)

def import_obj(path, layer_name):
    """OBJファイルをインポートしてレイヤーに配置"""
    if not os.path.exists(path):
        Rhino.RhinoApp.WriteLine("ERROR: File not found - {}".format(path))
        return []

    before = set(rs.AllObjects(select=False) or [])
    cmd = '_-Import "{}" _Enter'.format(path)
    rs.Command(cmd, echo=False)
    after = set(rs.AllObjects(select=False) or [])
    imported = list(after - before)

    # インポートしたオブジェクトをレイヤーに配置
    for obj in imported:
        rs.ObjectLayer(obj, layer_name)

    return imported

def set_perspective_view():
    """ビューをPerspective（透視投影）に設定"""
    # RhinoScriptSyntaxを使ってPerspectiveビューに設定
    # mode: 1=Parallel, 2=Perspective
    current_mode = rs.ViewProjection()

    if current_mode != 2:
        rs.ViewProjection(mode=2)
        Rhino.RhinoApp.WriteLine("Set to Perspective view")
    else:
        Rhino.RhinoApp.WriteLine("Already in Perspective view")

    return True

def capture_viewport_to_file(output_path, width=1920, height=1080, transparent=True):
    """
    ビューポートを画像ファイルにキャプチャ

    Args:
        output_path: 出力PNGファイルのパス
        width: 画像幅（ピクセル）
        height: 画像高さ（ピクセル）
        transparent: 背景を透過するか（PNG形式のみ有効）

    Returns:
        成功時True、失敗時False
    """
    try:
        view = sc.doc.Views.ActiveView
        if not view:
            Rhino.RhinoApp.WriteLine("ERROR: No active view found")
            return False

        # ViewCaptureの設定
        view_capture = Rhino.Display.ViewCapture()
        view_capture.Width = width
        view_capture.Height = height
        view_capture.TransparentBackground = transparent
        view_capture.ScaleScreenItems = False
        view_capture.DrawAxes = False
        view_capture.DrawGrid = False
        view_capture.DrawGridAxes = False

        Rhino.RhinoApp.WriteLine("Capturing viewport ({} x {})...".format(width, height))

        # ビットマップにキャプチャ
        bitmap = view_capture.CaptureToBitmap(view)
        if not bitmap:
            Rhino.RhinoApp.WriteLine("ERROR: Failed to capture bitmap")
            return False

        # PNG形式で保存
        bitmap.Save(output_path, System.Drawing.Imaging.ImageFormat.Png)
        Rhino.RhinoApp.WriteLine("SUCCESS: Saved to {}".format(output_path))
        return True

    except Exception as e:
        Rhino.RhinoApp.WriteLine("ERROR: {}".format(str(e)))
        return False

# ===== メイン =====
def main():
    """メイン処理"""
    Rhino.RhinoApp.WriteLine("=" * 60)
    Rhino.RhinoApp.WriteLine("Screenshot Test - Capturing gen0_A_inner.obj")
    Rhino.RhinoApp.WriteLine("=" * 60)

    # 出力ディレクトリの作成
    if not os.path.exists(SCREENSHOTS_DIR):
        os.makedirs(SCREENSHOTS_DIR)
        Rhino.RhinoApp.WriteLine("Created directory: {}".format(SCREENSHOTS_DIR))

    # テストファイルの存在確認
    if not os.path.exists(TEST_OBJ):
        Rhino.RhinoApp.WriteLine("ERROR: Test file not found")
        Rhino.RhinoApp.WriteLine("  Expected: {}".format(TEST_OBJ))
        return

    # レイヤー準備
    ensure_layer(LAYER_NAME)
    clear_layer(LAYER_NAME)

    # OBJファイルをインポート
    Rhino.RhinoApp.WriteLine("Importing {}...".format(TEST_OBJ))
    imported = import_obj(TEST_OBJ, LAYER_NAME)

    if not imported:
        Rhino.RhinoApp.WriteLine("ERROR: No objects were imported")
        return

    Rhino.RhinoApp.WriteLine("  Imported {} objects".format(len(imported)))

    # ビューをズーム
    Rhino.RhinoApp.WriteLine("Zooming to extents...")
    rs.ZoomExtents()
    rs.Redraw()

    # Perspectiveビューに設定
    set_perspective_view()

    # オブジェクトの選択を解除
    Rhino.RhinoApp.WriteLine("Deselecting all objects...")
    rs.UnselectAllObjects()

    # 少し待機（ビューが安定するのを待つ）
    rs.Redraw()

    # キャプチャ実行
    Rhino.RhinoApp.WriteLine("-" * 60)
    success = capture_viewport_to_file(OUTPUT_PNG, IMAGE_WIDTH, IMAGE_HEIGHT, transparent=True)

    if success:
        Rhino.RhinoApp.WriteLine("-" * 60)
        Rhino.RhinoApp.WriteLine("Test completed successfully!")
        Rhino.RhinoApp.WriteLine("Output file: {}".format(OUTPUT_PNG))
        Rhino.RhinoApp.WriteLine("Image size: {} x {}".format(IMAGE_WIDTH, IMAGE_HEIGHT))
        Rhino.RhinoApp.WriteLine("Transparent background: Yes")
    else:
        Rhino.RhinoApp.WriteLine("-" * 60)
        Rhino.RhinoApp.WriteLine("Test FAILED - see errors above")

    Rhino.RhinoApp.WriteLine("=" * 60)

# 実行
main()
