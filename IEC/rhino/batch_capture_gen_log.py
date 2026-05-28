# -*- coding: utf-8 -*-
"""
batch_capture_gen_log.py - Batch capture screenshots of all gen_log inner OBJ files

Usage in Rhino Python Editor:
    1. Run: RunPythonScript "batch_capture_gen_log.py"
    2. Confirm when prompted
    3. Wait for all 52 images to be captured (gen0-25, A_inner and B_inner)
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

# レイヤー名
LAYER_NAME = "Screenshot_Temp"

# 画像サイズ
IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080

# 世代数（gen0 から gen25 まで）
NUM_GENERATIONS = 26

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

        # ビットマップにキャプチャ
        bitmap = view_capture.CaptureToBitmap(view)
        if not bitmap:
            return False

        # PNG形式で保存
        bitmap.Save(output_path, System.Drawing.Imaging.ImageFormat.Png)
        return True

    except Exception as e:
        Rhino.RhinoApp.WriteLine("ERROR: {}".format(str(e)))
        return False

def capture_obj_file(obj_path, output_path):
    """
    OBJファイルを読み込んでキャプチャ

    Args:
        obj_path: インポートするOBJファイルのパス
        output_path: 出力PNGファイルのパス

    Returns:
        成功時True、失敗時False
    """
    # レイヤーをクリア
    clear_layer(LAYER_NAME)

    # OBJファイルをインポート
    imported = import_obj(obj_path, LAYER_NAME)

    if not imported:
        return False

    # ビューをズーム
    rs.ZoomExtents()
    rs.Redraw()

    # Perspectiveビューに設定
    set_perspective_view()

    # オブジェクトの選択を解除
    rs.UnselectAllObjects()

    # ビューを更新
    rs.Redraw()

    # キャプチャ実行
    success = capture_viewport_to_file(output_path, IMAGE_WIDTH, IMAGE_HEIGHT, transparent=True)

    return success

# ===== メイン =====
def main():
    """メイン処理"""
    Rhino.RhinoApp.WriteLine("=" * 70)
    Rhino.RhinoApp.WriteLine("Batch Screenshot Capture - gen_log A_inner and B_inner")
    Rhino.RhinoApp.WriteLine("=" * 70)
    Rhino.RhinoApp.WriteLine("This will capture {} generations (gen0-gen{})".format(NUM_GENERATIONS, NUM_GENERATIONS - 1))
    Rhino.RhinoApp.WriteLine("Total images: {} (A_inner and B_inner for each generation)".format(NUM_GENERATIONS * 2))
    Rhino.RhinoApp.WriteLine("Output directory: {}".format(SCREENSHOTS_DIR))
    Rhino.RhinoApp.WriteLine("=" * 70)

    # 確認プロンプト
    confirm = rs.GetString("Start batch capture?", "Yes", ["Yes", "No"])
    if confirm != "Yes":
        Rhino.RhinoApp.WriteLine("Cancelled by user")
        return

    # 出力ディレクトリの作成
    if not os.path.exists(SCREENSHOTS_DIR):
        os.makedirs(SCREENSHOTS_DIR)
        Rhino.RhinoApp.WriteLine("Created directory: {}".format(SCREENSHOTS_DIR))

    # レイヤー準備
    ensure_layer(LAYER_NAME)

    # カウンター
    success_count = 0
    skip_count = 0
    error_count = 0

    # gen0 から gen25 まで処理
    for gen_num in range(NUM_GENERATIONS):
        Rhino.RhinoApp.WriteLine("-" * 70)
        Rhino.RhinoApp.WriteLine("Processing generation {} / {}...".format(gen_num, NUM_GENERATIONS - 1))

        # A_inner を処理
        a_inner_obj = os.path.join(GEN_LOG_DIR, "gen{}_A_inner.obj".format(gen_num))
        a_inner_png = os.path.join(SCREENSHOTS_DIR, "gen{}_A_inner.png".format(gen_num))

        if os.path.exists(a_inner_obj):
            Rhino.RhinoApp.WriteLine("  Capturing gen{}_A_inner.obj...".format(gen_num))
            if capture_obj_file(a_inner_obj, a_inner_png):
                Rhino.RhinoApp.WriteLine("    SUCCESS: {}".format(a_inner_png))
                success_count += 1
            else:
                Rhino.RhinoApp.WriteLine("    ERROR: Failed to capture")
                error_count += 1
        else:
            Rhino.RhinoApp.WriteLine("  SKIP: gen{}_A_inner.obj not found".format(gen_num))
            skip_count += 1

        # B_inner を処理
        b_inner_obj = os.path.join(GEN_LOG_DIR, "gen{}_B_inner.obj".format(gen_num))
        b_inner_png = os.path.join(SCREENSHOTS_DIR, "gen{}_B_inner.png".format(gen_num))

        if os.path.exists(b_inner_obj):
            Rhino.RhinoApp.WriteLine("  Capturing gen{}_B_inner.obj...".format(gen_num))
            if capture_obj_file(b_inner_obj, b_inner_png):
                Rhino.RhinoApp.WriteLine("    SUCCESS: {}".format(b_inner_png))
                success_count += 1
            else:
                Rhino.RhinoApp.WriteLine("    ERROR: Failed to capture")
                error_count += 1
        else:
            Rhino.RhinoApp.WriteLine("  SKIP: gen{}_B_inner.obj not found".format(gen_num))
            skip_count += 1

    # 最後にレイヤーをクリア
    clear_layer(LAYER_NAME)

    # サマリー表示
    Rhino.RhinoApp.WriteLine("=" * 70)
    Rhino.RhinoApp.WriteLine("Batch capture completed!")
    Rhino.RhinoApp.WriteLine("=" * 70)
    Rhino.RhinoApp.WriteLine("  SUCCESS: {} images captured".format(success_count))
    Rhino.RhinoApp.WriteLine("  SKIPPED: {} files not found".format(skip_count))
    Rhino.RhinoApp.WriteLine("  ERRORS:  {} failures".format(error_count))
    Rhino.RhinoApp.WriteLine("  TOTAL:   {} files processed".format(success_count + skip_count + error_count))
    Rhino.RhinoApp.WriteLine("=" * 70)
    Rhino.RhinoApp.WriteLine("Output directory: {}".format(SCREENSHOTS_DIR))
    Rhino.RhinoApp.WriteLine("=" * 70)

# 実行
main()
