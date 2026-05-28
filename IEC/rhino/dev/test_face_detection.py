# -*- coding: utf-8 -*-
"""
test_face_detection.py - 面ベースの隣接検出テスト

OBJファイルの面データを解析して、2つのセルが実際に面を共有しているかを判定します。
"""

import os

def parse_obj_with_faces(obj_path):
    """
    OBJファイルを解析して頂点座標とセルごとの面情報を抽出

    Args:
        obj_path: OBJファイルのパス

    Returns:
        global_vertices: 頂点座標のリスト [(x, y, z), ...] (0-indexed)
        cell_faces: セルごとの面リスト {cell_idx: [face1, face2, ...]}
                    各faceは頂点インデックスのリスト [v1_idx, v2_idx, v3_idx, ...]
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

def get_face_coordinate_set(face_vertices, global_vertices, tolerance=0.001):
    """
    面の頂点座標セットを取得（座標の丸め込みでセット比較可能にする）

    Args:
        face_vertices: 面の頂点インデックスリスト
        global_vertices: 全頂点座標リスト
        tolerance: 座標の丸め込み精度

    Returns:
        frozenset: 丸め込まれた座標のタプルのセット
    """
    # 座標を丸め込んでタプルに変換
    coords = []
    for v_idx in face_vertices:
        x, y, z = global_vertices[v_idx]
        # tolerance精度で丸め込み（例: 0.001 -> 小数点3桁）
        decimals = len(str(tolerance).split('.')[-1])
        rounded = (round(x, decimals), round(y, decimals), round(z, decimals))
        coords.append(rounded)

    # ソートしてfrozensetに（頂点の順序に依存しない比較のため）
    return frozenset(coords)

def find_face_sharing_cells(global_vertices, cell_faces, min_shared_vertices=3):
    """
    面を共有しているセルのペアを検出

    Args:
        global_vertices: 頂点座標リスト
        cell_faces: セルごとの面リスト {cell_idx: [face1, face2, ...]}
        min_shared_vertices: 面とみなす最小頂点数（デフォルト: 3）

    Returns:
        adjacency: {cell_idx: set(adjacent_cell_indices)}
        shared_faces: デバッグ用の共有面情報 {(cell_i, cell_j): [共有面の頂点数リスト]}
    """
    # 各面を座標セットとして表現し、どのセルに属するかを記録
    face_coord_to_cells = {}  # {face_coordinate_set: [(cell_idx, face_idx), ...]}

    for cell_idx, faces in cell_faces.items():
        for face_idx, face_vertices in enumerate(faces):
            if len(face_vertices) >= min_shared_vertices:
                coord_set = get_face_coordinate_set(face_vertices, global_vertices)

                if coord_set not in face_coord_to_cells:
                    face_coord_to_cells[coord_set] = []

                face_coord_to_cells[coord_set].append((cell_idx, face_idx, len(face_vertices)))

    # 同じ座標セットを持つ面を見つける（= 面を共有）
    adjacency = {}
    shared_faces = {}

    for coord_set, cells_with_face in face_coord_to_cells.items():
        if len(cells_with_face) >= 2:  # 2つ以上のセルがこの面を持つ
            # このcoord_setを共有する全てのセルペアを隣接としてマーク
            cells = [(cell_idx, num_vertices) for cell_idx, _, num_vertices in cells_with_face]

            for i, (cell_i, vertices_i) in enumerate(cells):
                for j in range(i + 1, len(cells)):
                    cell_j, vertices_j = cells[j]

                    # 隣接リストに追加
                    if cell_i not in adjacency:
                        adjacency[cell_i] = set()
                    if cell_j not in adjacency:
                        adjacency[cell_j] = set()

                    adjacency[cell_i].add(cell_j)
                    adjacency[cell_j].add(cell_i)

                    # デバッグ情報を記録
                    pair = tuple(sorted([cell_i, cell_j]))
                    if pair not in shared_faces:
                        shared_faces[pair] = []
                    shared_faces[pair].append(max(vertices_i, vertices_j))

    return adjacency, shared_faces

def test_face_detection(obj_path):
    """面ベースの隣接検出をテスト"""
    print("=" * 70)
    print("Face-Based Adjacency Detection Test")
    print("=" * 70)
    print("File: {}".format(obj_path))
    print()

    if not os.path.exists(obj_path):
        print("ERROR: File not found!")
        return

    # OBJを解析（面データ込み）
    print("[Test 1] Parsing OBJ file with face data...")
    global_vertices, cell_faces = parse_obj_with_faces(obj_path)
    print("  Parsed {} vertices".format(len(global_vertices)))
    print("  Parsed {} cells".format(len(cell_faces)))

    # 面の統計
    total_faces = sum(len(faces) for faces in cell_faces.values())
    print("  Total faces: {}".format(total_faces))
    print()

    # サンプルセルの面情報
    if len(cell_faces) > 0:
        sample_cell = sorted(cell_faces.keys())[0]
        print("  Sample - Cell {}: {} faces".format(sample_cell, len(cell_faces[sample_cell])))
        if len(cell_faces[sample_cell]) > 0:
            sample_face = cell_faces[sample_cell][0]
            print("    First face: {} vertices".format(len(sample_face)))
    print()

    # 面を共有しているセルを検出
    print("[Test 2] Finding cells that share faces...")
    adjacency, shared_faces = find_face_sharing_cells(global_vertices, cell_faces)
    print("  Total cells with adjacent neighbors: {}".format(len(adjacency)))
    print()

    # ユニークな隣接ペア数を計算
    unique_pairs = set()
    for cell_i, neighbors in adjacency.items():
        for cell_j in neighbors:
            pair = tuple(sorted([cell_i, cell_j]))
            unique_pairs.add(pair)

    print("  Total unique adjacencies (face-sharing cell pairs): {}".format(len(unique_pairs)))
    print()

    # 共有面の統計
    if len(shared_faces) > 0:
        print("[Test 3] Shared face statistics:")

        # 各ペアが共有している面の数
        num_shared_faces_dist = {}
        for pair, face_vertex_counts in shared_faces.items():
            num_faces = len(face_vertex_counts)
            num_shared_faces_dist[num_faces] = num_shared_faces_dist.get(num_faces, 0) + 1

        print("  Number of shared faces per cell pair:")
        for num_faces in sorted(num_shared_faces_dist.keys()):
            print("    {} shared face(s): {} cell pairs".format(num_faces, num_shared_faces_dist[num_faces]))
        print()

        # サンプル表示
        print("  Sample cell pairs with shared faces:")
        for i, (pair, face_vertex_counts) in enumerate(list(shared_faces.items())[:5]):
            cell_i, cell_j = pair
            print("    Cells {} <-> {}: {} shared face(s) with {} vertices each".format(
                cell_i, cell_j, len(face_vertex_counts), face_vertex_counts
            ))
    print()

    # 隣接統計
    if len(adjacency) > 0:
        neighbor_counts = [len(neighbors) for neighbors in adjacency.values()]
        print("[Test 4] Adjacency statistics:")
        print("  Min neighbors per cell: {}".format(min(neighbor_counts)))
        print("  Max neighbors per cell: {}".format(max(neighbor_counts)))
        print("  Avg neighbors per cell: {:.1f}".format(sum(neighbor_counts) / len(neighbor_counts)))
        print()

        # サンプル隣接関係
        sample_cell = sorted(adjacency.keys())[0]
        print("  Sample: Cell {} is adjacent to {} cells: {}".format(
            sample_cell, len(adjacency[sample_cell]), sorted(list(adjacency[sample_cell]))
        ))
    print()

    print("=" * 70)
    print("Test COMPLETED!")
    print("=" * 70)

if __name__ == '__main__':
    OBJ_FILE = "/home/shint/py_code/IEC/gen_log/gen0_A_inner.obj"
    test_face_detection(OBJ_FILE)
