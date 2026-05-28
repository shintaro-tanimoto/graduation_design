# -*- coding: utf-8 -*-
"""
explode_view.py - 分解図作成スクリプト (Exploded View Generator)

複数のメッシュからなるOBJファイルをインポートし、各メッシュを原点から放射状に
配置して分解図（exploded view）を作成します。

Usage in Rhino Python Editor:
    RunPythonScript "explode_view.py"
"""

import rhinoscriptsyntax as rs
import Rhino
import os

# ===== 設定 (Configuration) =====
# この部分を編集してスケール比や対象ファイルを変更できます

# 対象ファイル
GEN_LOG_DIR = r"\\wsl$\Ubuntu\home\shint\py_code\IEC\gen_history\gen_018\population\cand_00"
OBJ_FILE = "mesh_inner.obj"
OBJ_FILE_PATH = os.path.join(GEN_LOG_DIR, OBJ_FILE)

# XYZ方向の倍率（直接指定）
SCALE_X = 4.0  # X軸方向の拡大率（1.0 = 変化なし、2.0 = 2倍）
SCALE_Y = 4.0  # Y軸方向の拡大率
SCALE_Z = 4.0  # Z軸方向の拡大率

# レイヤー名
LAYER_EXPLODED = "ExplodedView"
LAYER_GUIDES = "ExplodedView_Guides"

# オプション
CREATE_GUIDES = True  # 移動経路の可視化ガイドを作成するか

# ===== ユーティリティ関数 (Utility Functions) =====
def ensure_layer(name):
    """レイヤーが存在しない場合は作成"""
    if not rs.IsLayer(name):
        rs.AddLayer(name)
        Rhino.RhinoApp.WriteLine("Created layer: {}".format(name))

def clear_layer(layer_name):
    """レイヤー内のオブジェクトを全削除"""
    if rs.IsLayer(layer_name):
        objs = rs.ObjectsByLayer(layer_name, select=False) or []
        if objs:
            rs.DeleteObjects(objs)
            Rhino.RhinoApp.WriteLine("Cleared layer: {} ({} objects)".format(layer_name, len(objs)))

def import_obj(path):
    """
    OBJファイルをインポートして新しく追加されたオブジェクトのリストを返す

    Args:
        path: OBJファイルのパス

    Returns:
        新しくインポートされたオブジェクトのGUIDリスト
    """
    if not os.path.exists(path):
        Rhino.RhinoApp.WriteLine("ERROR: File not found - {}".format(path))
        return []

    # インポート前のオブジェクト状態を取得
    before = set(rs.AllObjects(select=False) or [])

    # OBJファイルをインポート
    cmd = '_-Import "{}" _Enter'.format(path)
    rs.Command(cmd, echo=False)

    # インポート後のオブジェクト状態を取得
    after = set(rs.AllObjects(select=False) or [])

    # 差分＝新しくインポートされたオブジェクト
    imported = list(after - before)

    Rhino.RhinoApp.WriteLine("Imported {} objects from {}".format(len(imported), os.path.basename(path)))

    return imported

# ===== 計算関数 (Calculation Functions) =====
def calculate_centroid(obj_guid):
    """
    オブジェクトのバウンディングボックスから重心を計算

    Args:
        obj_guid: オブジェクトのGUID

    Returns:
        (cx, cy, cz) の重心座標、失敗時はNone
    """
    bbox = rs.BoundingBox(obj_guid)

    if not bbox or len(bbox) < 7:
        Rhino.RhinoApp.WriteLine("WARNING: Failed to get bounding box for object {}".format(obj_guid))
        return None

    # bbox[0] = 最小コーナー (min_x, min_y, min_z)
    # bbox[6] = 最大コーナー (max_x, max_y, max_z)
    cx = (bbox[0][0] + bbox[6][0]) / 2.0
    cy = (bbox[0][1] + bbox[6][1]) / 2.0
    cz = (bbox[0][2] + bbox[6][2]) / 2.0

    return (cx, cy, cz)

def calculate_movement(centroid, scale_x, scale_y, scale_z):
    """
    重心位置とスケール係数から移動ベクトルを計算

    原点から重心への方向ベクトルに対して、各軸ごとにスケール係数を適用

    Args:
        centroid: (cx, cy, cz) の重心座標
        scale_x, scale_y, scale_z: 各軸のスケール係数

    Returns:
        (dx, dy, dz) の移動ベクトル
    """
    cx, cy, cz = centroid

    # エッジケース: 重心が原点に非常に近い場合
    if abs(cx) < 0.001 and abs(cy) < 0.001 and abs(cz) < 0.001:
        # フォールバック: Z軸方向に移動
        fallback_distance = 100.0 * max(scale_x, scale_y, scale_z)
        Rhino.RhinoApp.WriteLine("WARNING: Centroid at origin, using fallback Z movement")
        return (0, 0, fallback_distance)

    # 各軸ごとに放射状に拡大
    # 新しい位置 = 元の位置 × スケール係数
    # 移動量 = 新しい位置 - 元の位置 = 元の位置 × (スケール係数 - 1)
    dx = cx * (scale_x - 1.0)
    dy = cy * (scale_y - 1.0)
    dz = cz * (scale_z - 1.0)

    return (dx, dy, dz)

def get_movement_stats(movements):
    """
    移動ベクトルの統計情報を計算

    Args:
        movements: {obj_guid: (centroid, movement)} の辞書

    Returns:
        統計情報の辞書
    """
    if not movements:
        return {}

    all_dx = [mv[1][0] for mv in movements.values()]
    all_dy = [mv[1][1] for mv in movements.values()]
    all_dz = [mv[1][2] for mv in movements.values()]

    return {
        'count': len(movements),
        'dx_min': min(all_dx),
        'dx_max': max(all_dx),
        'dy_min': min(all_dy),
        'dy_max': max(all_dy),
        'dz_min': min(all_dz),
        'dz_max': max(all_dz)
    }

# ===== OBJ解析関数 (OBJ Parsing Functions) =====
def parse_obj_file(obj_path):
    """
    OBJファイルを解析して頂点座標とセルごとの面情報を抽出

    Args:
        obj_path: OBJファイルのパス

    Returns:
        global_vertices: 頂点座標のリスト [(x, y, z), ...] (0-indexed)
        cell_faces: セルごとの面リスト {cell_idx: [face1, face2, ...]}
                    各faceは頂点インデックスのリスト [v1_idx, v2_idx, ...]
    """
    global_vertices = []
    cell_faces = {}
    current_cell = None

    with open(obj_path, 'r') as f:
        for line in f:
            line = line.strip()

            # 頂点を解析
            if line.startswith('v '):
                parts = line.split()
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                global_vertices.append((x, y, z))

            # グループ（セル）を解析
            elif line.startswith('g cell_'):
                cell_name = line.split()[1]  # "cell_0"
                current_cell = int(cell_name.split('_')[1])
                cell_faces[current_cell] = []

            # 面を解析
            elif line.startswith('f ') and current_cell is not None:
                parts = line.split()[1:]  # 'f' をスキップ
                face_vertices = []
                for part in parts:
                    # "v/vt/vn" 形式を処理（頂点インデックスのみ必要）
                    v_idx = int(part.split('/')[0])
                    # OBJの1-basedインデックスをPythonの0-basedに変換
                    face_vertices.append(v_idx - 1)

                if len(face_vertices) >= 3:  # 有効な面（3頂点以上）
                    cell_faces[current_cell].append(face_vertices)

    return global_vertices, cell_faces

def find_shared_vertices(global_vertices, cell_vertex_map, tolerance=0.001):
    """
    複数のセル間で共有される頂点を座標で検出

    注: OBJファイルは境界で頂点を重複させるため、同じ座標を持つ頂点を検出する

    Args:
        global_vertices: 頂点座標のリスト [(x, y, z), ...]
        cell_vertex_map: {cell_idx: [vertex_indices]} の辞書
        tolerance: 座標比較の許容誤差（mm）

    Returns:
        shared_vertex_groups: 同じ位置を共有する頂点グループのリスト
            [[(vertex_idx, cell_idx), ...], ...]
    """
    # 各セルの頂点を (vertex_idx, cell_idx) のペアとして収集
    all_cell_vertices = []
    for cell_idx, vertex_indices in cell_vertex_map.items():
        for v_idx in vertex_indices:
            all_cell_vertices.append((v_idx, cell_idx))

    # 座標でグループ化（同じ座標を持つ頂点を見つける）
    shared_groups = []
    used_vertices = set()

    for i, (v_idx_i, cell_i) in enumerate(all_cell_vertices):
        if v_idx_i in used_vertices:
            continue

        pos_i = global_vertices[v_idx_i]
        group = [(v_idx_i, cell_i)]
        used_vertices.add(v_idx_i)

        # この頂点と同じ座標を持つ他の頂点を探す
        for j in range(i + 1, len(all_cell_vertices)):
            v_idx_j, cell_j = all_cell_vertices[j]

            if v_idx_j in used_vertices:
                continue

            pos_j = global_vertices[v_idx_j]

            # 距離を計算
            dx = pos_i[0] - pos_j[0]
            dy = pos_i[1] - pos_j[1]
            dz = pos_i[2] - pos_j[2]
            dist = (dx*dx + dy*dy + dz*dz) ** 0.5

            if dist < tolerance:
                group.append((v_idx_j, cell_j))
                used_vertices.add(v_idx_j)

        # 2つ以上の頂点を含むグループのみ保存
        if len(group) >= 2:
            shared_groups.append(group)

    return shared_groups

def build_guid_to_cell_map(imported_objs, cell_data):
    """
    インポートされたオブジェクトのGUIDをセルインデックスにマッピング

    前提: RhinoはOBJファイル内のグループ順にインポートする

    Args:
        imported_objs: インポートされたオブジェクトのGUIDリスト
        cell_data: セルインデックスをキーとする辞書（cell_facesまたはcell_vertex_map）

    Returns:
        guid_to_cell: {guid: cell_idx} の辞書
    """
    # セルインデックスをソート（OBJファイル内の順序を保持）
    sorted_cells = sorted(cell_data.keys())

    if len(imported_objs) != len(sorted_cells):
        Rhino.RhinoApp.WriteLine(
            "WARNING: インポートオブジェクト数 ({}) と解析セル数 ({}) が不一致".format(
                len(imported_objs), len(sorted_cells)
            )
        )

    guid_to_cell = {}
    for i, obj_guid in enumerate(imported_objs):
        if i < len(sorted_cells):
            guid_to_cell[obj_guid] = sorted_cells[i]

    return guid_to_cell

def calculate_polygon_area(vertices):
    """
    3D多角形の面積を計算（三角形分割法）

    Args:
        vertices: 頂点座標のリスト [(x, y, z), ...]

    Returns:
        面積 (mm^2)
    """
    if len(vertices) < 3:
        return 0.0

    # 最初の頂点を基準に三角形分割
    total_area = 0.0
    v0 = vertices[0]

    for i in range(1, len(vertices) - 1):
        v1 = vertices[i]
        v2 = vertices[i + 1]

        # 2つのベクトルを計算
        vec1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        vec2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])

        # 外積を計算
        cross = (
            vec1[1] * vec2[2] - vec1[2] * vec2[1],
            vec1[2] * vec2[0] - vec1[0] * vec2[2],
            vec1[0] * vec2[1] - vec1[1] * vec2[0]
        )

        # 外積の大きさ = 平行四辺形の面積、三角形の面積はその半分
        magnitude = (cross[0]**2 + cross[1]**2 + cross[2]**2) ** 0.5
        total_area += magnitude / 2.0

    return total_area

def build_adjacency_list_from_faces(global_vertices, cell_faces, min_face_vertices=4,
                                     min_face_area=100.0, tolerance=0.001):
    """
    面データから隣接リストを構築（面ベースの検出 + 面積フィルター）

    2つのセルが同じ頂点座標セットを持つ面を共有し、かつ面積が十分大きい場合のみ隣接とみなす

    Args:
        global_vertices: 頂点座標のリスト [(x, y, z), ...]
        cell_faces: セルごとの面リスト {cell_idx: [[v1, v2, ...], ...]}
        min_face_vertices: 共有面とみなす最小頂点数（デフォルト: 4、四角形以上）
        min_face_area: 共有面とみなす最小面積（デフォルト: 100.0 mm^2）
        tolerance: 座標比較の許容誤差（mm）

    Returns:
        adjacency: {cell_idx: set(adjacent_cell_indices)}
    """
    # 各面を座標セットとして表現し、どのセルに属するかを記録
    face_coord_to_cells = {}  # {frozenset(coords): [(cell_idx, face_vertices), ...]}

    decimals = max(0, len(str(tolerance).split('.')[-1]) if '.' in str(tolerance) else 0)

    for cell_idx, faces in cell_faces.items():
        for face_vertices in faces:
            if len(face_vertices) >= min_face_vertices:  # 最小頂点数チェック
                # 面の頂点座標を取得
                coords = []
                for v_idx in face_vertices:
                    x, y, z = global_vertices[v_idx]
                    coords.append((x, y, z))

                # 面積を計算
                area = calculate_polygon_area(coords)

                # 面積チェック
                if area >= min_face_area:
                    # 座標を丸め込んでセット化（共有面検出用）
                    rounded_coords = set()
                    for x, y, z in coords:
                        rounded = (round(x, decimals), round(y, decimals), round(z, decimals))
                        rounded_coords.add(rounded)

                    coord_set = frozenset(rounded_coords)

                    if coord_set not in face_coord_to_cells:
                        face_coord_to_cells[coord_set] = []

                    face_coord_to_cells[coord_set].append((cell_idx, area))

    # 同じ座標セットを持つ面を見つけて隣接リストを構築
    adjacency = {}
    shared_face_areas = []  # 共有面の面積リスト（統計用）

    for coord_set, cells_with_face in face_coord_to_cells.items():
        if len(cells_with_face) >= 2:  # 2つ以上のセルがこの面を持つ
            cells = list(set(cell_idx for cell_idx, _ in cells_with_face))

            # この共有面の面積を記録（統計用）
            face_area = cells_with_face[0][1]  # どのセルでも面積は同じ
            shared_face_areas.append(face_area)

            for i, cell_i in enumerate(cells):
                for j in range(i + 1, len(cells)):
                    cell_j = cells[j]

                    if cell_i not in adjacency:
                        adjacency[cell_i] = set()
                    if cell_j not in adjacency:
                        adjacency[cell_j] = set()

                    adjacency[cell_i].add(cell_j)
                    adjacency[cell_j].add(cell_i)

    # デバッグ情報：統計をログ出力
    if len(adjacency) > 0:
        neighbor_counts = [len(neighbors) for neighbors in adjacency.values()]
        Rhino.RhinoApp.WriteLine("  Face-based adjacency (min {} vertices, min {:.1f} mm^2):".format(
            min_face_vertices, min_face_area
        ))
        Rhino.RhinoApp.WriteLine("    Cells with neighbors: {}".format(len(adjacency)))
        Rhino.RhinoApp.WriteLine("    Avg neighbors per cell: {:.1f}".format(sum(neighbor_counts) / len(neighbor_counts)))
        Rhino.RhinoApp.WriteLine("    Max neighbors per cell: {}".format(max(neighbor_counts)))

        # ユニークペア数
        unique_pairs = set()
        for cell_i, neighbors in adjacency.items():
            for cell_j in neighbors:
                pair = tuple(sorted([cell_i, cell_j]))
                unique_pairs.add(pair)

        Rhino.RhinoApp.WriteLine("    Total adjacencies (cell pairs): {}".format(len(unique_pairs)))

        # 共有面の面積統計
        if len(shared_face_areas) > 0:
            Rhino.RhinoApp.WriteLine("    Shared face area range: {:.1f} to {:.1f} mm^2".format(
                min(shared_face_areas), max(shared_face_areas)
            ))
            Rhino.RhinoApp.WriteLine("    Avg shared face area: {:.1f} mm^2".format(
                sum(shared_face_areas) / len(shared_face_areas)
            ))

    return adjacency

# ===== 可視化関数 (Visualization Functions) =====
def create_centroid_connection_guides(global_vertices, cell_faces, movements,
                                        guid_to_cell, layer_name, min_face_vertices=4,
                                        min_face_area=100.0):
    """
    隣接セルの重心同士を結ぶガイドラインを作成（面ベースの隣接検出 + 面積フィルター）

    Args:
        global_vertices: 頂点座標のリスト [(x, y, z), ...]
        cell_faces: セルごとの面リスト {cell_idx: [[v1, v2, ...], ...]}
        movements: 移動情報 {obj_guid: (centroid, movement)}
        guid_to_cell: GUIDからセルインデックスへのマッピング {obj_guid: cell_idx}
        layer_name: ガイドラインを配置するレイヤー名
        min_face_vertices: 共有面とみなす最小頂点数（デフォルト: 4、四角形以上）
        min_face_area: 共有面とみなす最小面積（デフォルト: 100.0 mm^2）

    Returns:
        guides: 作成されたガイドラインのGUIDリスト
    """
    guides = []

    # 隣接リストを構築（面ベースの検出 + 面積フィルター）
    adjacency = build_adjacency_list_from_faces(global_vertices, cell_faces,
                                                 min_face_vertices, min_face_area)

    # 逆マッピングを作成: cell_idx -> guid
    cell_to_guid = {cell_idx: guid for guid, cell_idx in guid_to_cell.items()}

    # 処理済みペアを追跡（重複を避ける）
    processed_pairs = set()

    for cell_i, neighbors in adjacency.items():
        # セルがインポートされていない場合はスキップ
        if cell_i not in cell_to_guid:
            continue

        guid_i = cell_to_guid[cell_i]
        if guid_i not in movements:
            continue

        # cell_iの分解後の重心を取得
        centroid_i, (dx_i, dy_i, dz_i) = movements[guid_i]
        exploded_centroid_i = (
            centroid_i[0] + dx_i,
            centroid_i[1] + dy_i,
            centroid_i[2] + dz_i
        )

        for cell_j in neighbors:
            # 正規化されたペア（小さいインデックスが先）を作成して重複を避ける
            pair = tuple(sorted([cell_i, cell_j]))
            if pair in processed_pairs:
                continue
            processed_pairs.add(pair)

            # 隣接セルがインポートされていない場合はスキップ
            if cell_j not in cell_to_guid:
                continue

            guid_j = cell_to_guid[cell_j]
            if guid_j not in movements:
                continue

            # cell_jの分解後の重心を取得
            centroid_j, (dx_j, dy_j, dz_j) = movements[guid_j]
            exploded_centroid_j = (
                centroid_j[0] + dx_j,
                centroid_j[1] + dy_j,
                centroid_j[2] + dz_j
            )

            # 分解後の重心同士を結ぶ線を作成
            line = rs.AddLine(exploded_centroid_i, exploded_centroid_j)
            if line:
                rs.ObjectLayer(line, layer_name)
                rs.ObjectColor(line, (100, 200, 255))  # ライトブルー
                guides.append(line)

    Rhino.RhinoApp.WriteLine(
        "Created {} centroid connection lines ({} unique adjacencies)".format(
            len(guides), len(processed_pairs)
        )
    )

    return guides

def create_movement_guides_OLD(movements, layer_name):
    """
    各メッシュの移動経路を示すガイドラインを作成

    Args:
        movements: {obj_guid: (centroid, movement)} の辞書
        layer_name: ガイドを配置するレイヤー名

    Returns:
        作成されたガイドラインのGUIDリスト
    """
    guides = []

    for obj_guid, (centroid, movement) in movements.items():
        cx, cy, cz = centroid
        dx, dy, dz = movement

        # 元の位置から新しい位置へのライン
        start_pt = (cx, cy, cz)
        end_pt = (cx + dx, cy + dy, cz + dz)

        line = rs.AddLine(start_pt, end_pt)
        if line:
            rs.ObjectLayer(line, layer_name)
            rs.ObjectColor(line, (150, 150, 150))  # グレー
            guides.append(line)

    Rhino.RhinoApp.WriteLine("Created {} movement guide lines".format(len(guides)))

    return guides

# ===== メイン関数 (Main Functions) =====
def create_exploded_view():
    """
    分解図を作成するメイン関数

    1. OBJファイルをインポート
    2. 各メッシュの重心を計算
    3. スケール係数に基づいて移動ベクトルを計算
    4. オプションでガイドラインを作成
    5. 各メッシュを新しい位置に移動
    """
    Rhino.RhinoApp.WriteLine("=" * 70)
    Rhino.RhinoApp.WriteLine("Exploded View Generator - 分解図作成")
    Rhino.RhinoApp.WriteLine("=" * 70)

    # 1. Setup - レイヤー準備
    Rhino.RhinoApp.WriteLine("\n[Step 1] Setting up layers...")
    ensure_layer(LAYER_EXPLODED)
    ensure_layer(LAYER_GUIDES)
    clear_layer(LAYER_EXPLODED)
    clear_layer(LAYER_GUIDES)

    # 2. Use configured scale factors - スケール係数を取得
    Rhino.RhinoApp.WriteLine("\n[Step 2] Using scale factors from configuration...")
    scale_x = SCALE_X
    scale_y = SCALE_Y
    scale_z = SCALE_Z
    Rhino.RhinoApp.WriteLine("  Scale factors: X={:.2f}, Y={:.2f}, Z={:.2f}".format(
        scale_x, scale_y, scale_z
    ))

    # Validate scale factors (must be >= 1.0)
    if scale_x < 1.0 or scale_y < 1.0 or scale_z < 1.0:
        Rhino.RhinoApp.WriteLine("  WARNING: Scale factors should be >= 1.0")
        Rhino.RhinoApp.WriteLine("  Adjusting invalid values to 1.0...")
        scale_x = max(1.0, scale_x)
        scale_y = max(1.0, scale_y)
        scale_z = max(1.0, scale_z)
        Rhino.RhinoApp.WriteLine("  Adjusted: X={:.2f}, Y={:.2f}, Z={:.2f}".format(
            scale_x, scale_y, scale_z
        ))

    # 3. Import OBJ - OBJファイルをインポート
    Rhino.RhinoApp.WriteLine("\n[Step 3] Importing OBJ file...")
    Rhino.RhinoApp.WriteLine("  File: {}".format(OBJ_FILE_PATH))

    if not os.path.exists(OBJ_FILE_PATH):
        Rhino.RhinoApp.WriteLine("ERROR: File not found!")
        Rhino.RhinoApp.WriteLine("=" * 70)
        return

    # 3b. Parse OBJ file structure - OBJファイル構造を解析
    Rhino.RhinoApp.WriteLine("\n[Step 3b] Parsing OBJ file structure (with face data)...")
    global_vertices, cell_faces = parse_obj_file(OBJ_FILE_PATH)

    # 面の統計
    total_faces = sum(len(faces) for faces in cell_faces.values())
    Rhino.RhinoApp.WriteLine("  Parsed {} vertices, {} cells, {} faces".format(
        len(global_vertices), len(cell_faces), total_faces
    ))

    # Diagnostic: Log Z coordinate range - 診断：Z座標範囲をログ出力
    if len(global_vertices) > 0:
        z_values = [v[2] for v in global_vertices]
        Rhino.RhinoApp.WriteLine("  Vertex Z range: {:.1f} to {:.1f} mm".format(
            min(z_values), max(z_values)
        ))

    imported_objs = import_obj(OBJ_FILE_PATH)

    if not imported_objs:
        Rhino.RhinoApp.WriteLine("ERROR: No objects were imported")
        Rhino.RhinoApp.WriteLine("=" * 70)
        return

    # インポートしたオブジェクトをレイヤーに配置
    for obj in imported_objs:
        rs.ObjectLayer(obj, LAYER_EXPLODED)

    # 3c. Map GUIDs to cell indices - GUIDとセルインデックスをマッピング
    guid_to_cell = build_guid_to_cell_map(imported_objs, cell_faces)

    # Verify mapping (optional, for debugging) - マッピングを検証（デバッグ用）
    if len(guid_to_cell) > 0:
        sample_guid = list(guid_to_cell.keys())[0]
        sample_cell = guid_to_cell[sample_guid]
        num_faces = len(cell_faces[sample_cell])
        actual_verts = rs.MeshVertexCount(sample_guid)
        Rhino.RhinoApp.WriteLine(
            "  Verification: Cell {} has {} parsed faces, {} Rhino vertices".format(
                sample_cell, num_faces, actual_verts
            )
        )

    # 4. Calculate movements - 移動ベクトルを計算
    Rhino.RhinoApp.WriteLine("\n[Step 4] Calculating movement vectors...")
    movements = {}
    failed_count = 0

    for obj_guid in imported_objs:
        centroid = calculate_centroid(obj_guid)

        if centroid is None:
            failed_count += 1
            continue

        movement = calculate_movement(centroid, scale_x, scale_y, scale_z)
        movements[obj_guid] = (centroid, movement)

    Rhino.RhinoApp.WriteLine("  Successfully calculated {} movements".format(len(movements)))
    if failed_count > 0:
        Rhino.RhinoApp.WriteLine("  WARNING: {} objects failed centroid calculation".format(failed_count))

    # 統計情報
    stats = get_movement_stats(movements)
    if stats:
        Rhino.RhinoApp.WriteLine("  Movement range:")
        Rhino.RhinoApp.WriteLine("    dX: {:.1f} to {:.1f} mm".format(stats['dx_min'], stats['dx_max']))
        Rhino.RhinoApp.WriteLine("    dY: {:.1f} to {:.1f} mm".format(stats['dy_min'], stats['dy_max']))
        Rhino.RhinoApp.WriteLine("    dZ: {:.1f} to {:.1f} mm".format(stats['dz_min'], stats['dz_max']))

    # 5. Create visualization guides - ガイドライン作成（オプション）
    if CREATE_GUIDES:
        Rhino.RhinoApp.WriteLine("\n[Step 5] Creating centroid connection guides (face-based + area filter)...")
        create_centroid_connection_guides(
            global_vertices,
            cell_faces,
            movements,
            guid_to_cell,
            LAYER_GUIDES,
            min_face_vertices=4,  # 4頂点以上の面のみを共有面とみなす（四角形以上、三角形を除外）
            min_face_area=100.0   # 100 mm^2以上の面のみを共有面とみなす
        )
    else:
        Rhino.RhinoApp.WriteLine("\n[Step 5] Skipping movement guides (CREATE_GUIDES=False)")

    # 6. Apply movements - メッシュを移動
    Rhino.RhinoApp.WriteLine("\n[Step 6] Applying movements to objects...")

    for i, (obj_guid, (centroid, movement)) in enumerate(movements.items(), 1):
        # rs.MoveObject(object_id, translation_vector)
        rs.MoveObject(obj_guid, movement)

        # 進捗表示（10個ごと）
        if i % 10 == 0 or i == len(movements):
            Rhino.RhinoApp.WriteLine("  Moved {}/{} objects...".format(i, len(movements)))

    # 7. Finalize - 表示を更新
    Rhino.RhinoApp.WriteLine("\n[Step 7] Finalizing...")
    rs.UnselectAllObjects()
    rs.Redraw()
    rs.ZoomExtents()

    # 8. Summary - サマリー表示
    Rhino.RhinoApp.WriteLine("\n" + "=" * 70)
    Rhino.RhinoApp.WriteLine("Exploded View Creation COMPLETED!")
    Rhino.RhinoApp.WriteLine("=" * 70)
    Rhino.RhinoApp.WriteLine("  Total objects:    {}".format(len(imported_objs)))
    Rhino.RhinoApp.WriteLine("  Objects moved:    {}".format(len(movements)))
    Rhino.RhinoApp.WriteLine("  Scale factors:    X={:.2f}, Y={:.2f}, Z={:.2f}".format(
        scale_x, scale_y, scale_z
    ))
    Rhino.RhinoApp.WriteLine("  Layer (meshes):   {}".format(LAYER_EXPLODED))
    if CREATE_GUIDES:
        Rhino.RhinoApp.WriteLine("  Layer (guides):   {}".format(LAYER_GUIDES))
    Rhino.RhinoApp.WriteLine("=" * 70)

# ===== 実行 (Execution) =====
if __name__ == '__main__':
    create_exploded_view()
