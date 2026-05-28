# -*- coding: utf-8 -*-
"""
batch_capture_gen_history.py - Batch capture screenshots of all gen_history candidates

現在のgen_history構造に対応:
  gen_history/gen_XXX/population/cand_YY/mesh_inner.obj

Usage in Rhino Python Editor:
    1. Run: RunPythonScript "batch_capture_gen_history.py"
    2. Confirm when prompted
    3. Wait for all images to be captured
"""

import rhinoscriptsyntax as rs
import Rhino
import scriptcontext as sc
import System
import os
import json

# ===== 設定 =====
# パス設定
GEN_HISTORY_DIR = r"\\wsl$\Ubuntu\home\shint\py_code\IEC\gen_history"
SCREENSHOTS_DIR = os.path.join(GEN_HISTORY_DIR, "screenshots")

# レイヤー名
LAYER_NAME = "Screenshot_Temp"

# 画像サイズ
IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080

# 各世代の候補数
NUM_CANDIDATES = 6

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

def get_available_generations():
    """
    利用可能な世代ディレクトリを取得

    Returns:
        世代番号のリスト（昇順）
    """
    generations = []

    if not os.path.exists(GEN_HISTORY_DIR):
        return generations

    for item in os.listdir(GEN_HISTORY_DIR):
        if item.startswith("gen_") and os.path.isdir(os.path.join(GEN_HISTORY_DIR, item)):
            try:
                gen_num = int(item.replace("gen_", ""))
                generations.append(gen_num)
            except ValueError:
                continue

    return sorted(generations)

# ===== メイン =====
def main():
    """メイン処理"""
    Rhino.RhinoApp.WriteLine("=" * 70)
    Rhino.RhinoApp.WriteLine("Batch Screenshot Capture - gen_history")
    Rhino.RhinoApp.WriteLine("=" * 70)

    # 利用可能な世代を取得
    generations = get_available_generations()

    if not generations:
        Rhino.RhinoApp.WriteLine("ERROR: No generations found in {}".format(GEN_HISTORY_DIR))
        return

    total_images = len(generations) * NUM_CANDIDATES

    Rhino.RhinoApp.WriteLine("Found {} generations: gen_{:03d} to gen_{:03d}".format(
        len(generations), generations[0], generations[-1]
    ))
    Rhino.RhinoApp.WriteLine("Total images to capture: {} ({} generations x {} candidates)".format(
        total_images, len(generations), NUM_CANDIDATES
    ))
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

    # 各世代を処理
    for gen_num in generations:
        gen_dir = "gen_{:03d}".format(gen_num)
        population_dir = os.path.join(GEN_HISTORY_DIR, gen_dir, "population")

        Rhino.RhinoApp.WriteLine("-" * 70)
        Rhino.RhinoApp.WriteLine("Processing {} ({}/{})...".format(
            gen_dir, generations.index(gen_num) + 1, len(generations)
        ))

        if not os.path.exists(population_dir):
            Rhino.RhinoApp.WriteLine("  SKIP: Population directory not found")
            skip_count += NUM_CANDIDATES
            continue

        # 各候補を処理
        for cand_idx in range(NUM_CANDIDATES):
            cand_id = "cand_{:02d}".format(cand_idx)
            cand_dir = os.path.join(population_dir, cand_id)
            mesh_inner_obj = os.path.join(cand_dir, "mesh_inner.obj")
            output_png = os.path.join(SCREENSHOTS_DIR, "{}_{}.png".format(gen_dir, cand_id))

            if os.path.exists(mesh_inner_obj):
                Rhino.RhinoApp.WriteLine("  Capturing {} / {}...".format(cand_id, cand_id))
                if capture_obj_file(mesh_inner_obj, output_png):
                    Rhino.RhinoApp.WriteLine("    SUCCESS: {}".format(output_png))
                    success_count += 1
                else:
                    Rhino.RhinoApp.WriteLine("    ERROR: Failed to capture")
                    error_count += 1
            else:
                Rhino.RhinoApp.WriteLine("  SKIP: {} mesh_inner.obj not found".format(cand_id))
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
