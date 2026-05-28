# -*- coding: utf-8 -*-
"""
test_min_vertices.py - 最小頂点数の閾値を変えて隣接数を比較
"""

import sys
sys.path.insert(0, '/home/shint/py_code/IEC/rhino')
from test_face_detection import parse_obj_with_faces

def find_adjacencies_with_threshold(global_vertices, cell_faces, min_face_vertices=3):
    """最小頂点数の閾値を指定して隣接検出"""
    face_coord_to_cells = {}

    for cell_idx, faces in cell_faces.items():
        for face_idx, face_vertices in enumerate(faces):
            if len(face_vertices) >= min_face_vertices:  # 閾値チェック
                # 座標セットを取得
                coords = set()
                for v_idx in face_vertices:
                    x, y, z = global_vertices[v_idx]
                    coords.add((round(x, 3), round(y, 3), round(z, 3)))

                coord_set = frozenset(coords)

                if coord_set not in face_coord_to_cells:
                    face_coord_to_cells[coord_set] = []

                face_coord_to_cells[coord_set].append((cell_idx, len(face_vertices)))

    # 隣接リストを構築
    adjacency = {}

    for coord_set, cells_with_face in face_coord_to_cells.items():
        if len(cells_with_face) >= 2:
            cells = list(set(cell_idx for cell_idx, _ in cells_with_face))

            for i, cell_i in enumerate(cells):
                for j in range(i + 1, len(cells)):
                    cell_j = cells[j]

                    if cell_i not in adjacency:
                        adjacency[cell_i] = set()
                    if cell_j not in adjacency:
                        adjacency[cell_j] = set()

                    adjacency[cell_i].add(cell_j)
                    adjacency[cell_j].add(cell_i)

    return adjacency

def test_thresholds(obj_path):
    """異なる最小頂点数で隣接検出をテスト"""
    print("=" * 70)
    print("Minimum Vertices Threshold Test")
    print("=" * 70)
    print("File: {}".format(obj_path))
    print()

    global_vertices, cell_faces = parse_obj_with_faces(obj_path)
    print("Parsed {} vertices, {} cells".format(len(global_vertices), len(cell_faces)))
    print()

    thresholds = [3, 4, 5, 6, 7]

    print("Testing different minimum vertex thresholds:")
    print("=" * 70)

    for threshold in thresholds:
        adjacency = find_adjacencies_with_threshold(global_vertices, cell_faces, threshold)

        # 統計
        if len(adjacency) > 0:
            neighbor_counts = [len(neighbors) for neighbors in adjacency.values()]
            avg_neighbors = sum(neighbor_counts) / len(neighbor_counts)
            max_neighbors = max(neighbor_counts)

            # ユニークペア数
            unique_pairs = set()
            for cell_i, neighbors in adjacency.items():
                for cell_j in neighbors:
                    pair = tuple(sorted([cell_i, cell_j]))
                    unique_pairs.add(pair)

            print("\nMin vertices: {} or more".format(threshold))
            print("  -> Total adjacencies (cell pairs): {}".format(len(unique_pairs)))
            print("  -> Cells with neighbors: {}".format(len(adjacency)))
            print("  -> Avg neighbors per cell: {:.1f}".format(avg_neighbors))
            print("  -> Max neighbors per cell: {}".format(max_neighbors))

            # Cell 39の隣接数
            if 39 in adjacency:
                print("  -> Cell 39: {} neighbors (was 15 with threshold=3)".format(len(adjacency[39])))

            # 異常に多い隣接を持つセル数（Cell 0, 1を除く）
            abnormal_count = sum(1 for idx, count in zip(adjacency.keys(), neighbor_counts)
                                if idx not in [0, 1] and count > 8)
            print("  -> Cells with >8 neighbors (excluding Cell 0,1): {}".format(abnormal_count))

        else:
            print("\nMin vertices: {} or more".format(threshold))
            print("  -> No adjacencies detected")

    print()
    print("=" * 70)
    print("Recommendation: Use threshold that gives ~3-6 avg neighbors")
    print("=" * 70)

if __name__ == '__main__':
    OBJ_FILE = "/home/shint/py_code/IEC/gen_log/gen25_A_inner.obj"
    test_thresholds(OBJ_FILE)
