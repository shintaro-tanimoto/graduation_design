# -*- coding: utf-8 -*-
"""
test_tolerance.py - 許容誤差による隣接検出の違いをテスト
"""

import sys
sys.path.insert(0, '/home/shint/py_code/IEC/rhino')
from test_face_detection import parse_obj_with_faces, get_face_coordinate_set

def test_different_tolerances(obj_path):
    """異なる許容誤差で隣接検出をテスト"""
    print("=" * 70)
    print("Tolerance Impact Test - 許容誤差の影響テスト")
    print("=" * 70)

    global_vertices, cell_faces = parse_obj_with_faces(obj_path)
    print("Parsed {} vertices, {} cells".format(len(global_vertices), len(cell_faces)))
    print()

    # 異なる許容誤差でテスト
    tolerances = [0.001, 0.0001, 0.00001, 0.000001, 0]

    for tolerance in tolerances:
        print("Testing with tolerance = {} mm:".format(tolerance if tolerance > 0 else "0 (exact match)"))

        # 各面を座標セットとして表現
        face_coord_to_cells = {}

        for cell_idx, faces in cell_faces.items():
            for face_idx, face_vertices in enumerate(faces):
                if len(face_vertices) >= 3:
                    # 座標を取得して丸め込み
                    coords = []
                    for v_idx in face_vertices:
                        x, y, z = global_vertices[v_idx]

                        if tolerance > 0:
                            # 許容誤差で丸め込み
                            decimals = max(0, len(str(tolerance).split('.')[-1]) if '.' in str(tolerance) else 0)
                            rounded = (round(x, decimals), round(y, decimals), round(z, decimals))
                        else:
                            # 完全一致（丸め込みなし）
                            rounded = (x, y, z)

                        coords.append(rounded)

                    coord_set = frozenset(coords)

                    if coord_set not in face_coord_to_cells:
                        face_coord_to_cells[coord_set] = []

                    face_coord_to_cells[coord_set].append((cell_idx, len(face_vertices)))

        # 共有面のペアを数える
        num_pairs = 0
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

        # ユニークペアを数える
        unique_pairs = set()
        for cell_i, neighbors in adjacency.items():
            for cell_j in neighbors:
                pair = tuple(sorted([cell_i, cell_j]))
                unique_pairs.add(pair)

        num_pairs = len(unique_pairs)

        # 統計
        if len(adjacency) > 0:
            neighbor_counts = [len(neighbors) for neighbors in adjacency.values()]
            avg_neighbors = sum(neighbor_counts) / len(neighbor_counts)
            max_neighbors = max(neighbor_counts)

            print("  -> {} unique adjacencies (cell pairs)".format(num_pairs))
            print("  -> Avg neighbors per cell: {:.1f}".format(avg_neighbors))
            print("  -> Max neighbors per cell: {}".format(max_neighbors))

            # Cell 0の隣接数を表示
            if 0 in adjacency:
                print("  -> Cell 0: {} neighbors".format(len(adjacency[0])))
        else:
            print("  -> 0 adjacencies detected")

        print()

    print("=" * 70)

if __name__ == '__main__':
    OBJ_FILE = "/home/shint/py_code/IEC/gen_log/gen0_A_inner.obj"
    test_different_tolerances(OBJ_FILE)
