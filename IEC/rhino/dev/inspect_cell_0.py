# -*- coding: utf-8 -*-
"""
inspect_cell_0.py - Cell 0の隣接関係を詳細に調査
"""

import sys
sys.path.insert(0, '/home/shint/py_code/IEC/rhino')
from test_face_detection import parse_obj_with_faces

def inspect_shared_faces(obj_path):
    """Cell 0と隣接セルの共有面を詳細に調査"""
    print("=" * 70)
    print("Cell 0 Shared Faces - Detailed Inspection")
    print("=" * 70)

    global_vertices, cell_faces = parse_obj_with_faces(obj_path)
    print("Parsed {} vertices, {} cells".format(len(global_vertices), len(cell_faces)))
    print()

    # Cell 0の面情報
    if 0 not in cell_faces:
        print("ERROR: Cell 0 not found!")
        return

    cell_0_faces = cell_faces[0]
    print("Cell 0: {} faces".format(len(cell_0_faces)))
    print()

    tolerance = 0.001

    # Cell 0の各面について、他のセルと共有しているか調べる
    print("Checking each face of Cell 0:")
    print()

    shared_count = {}  # {cell_idx: count}

    for i, face_0_vertices in enumerate(cell_0_faces):
        # この面の頂点座標を取得（丸め込み）
        coords_0 = set()
        for v_idx in face_0_vertices:
            x, y, z = global_vertices[v_idx]
            decimals = 3  # 0.001の精度
            coords_0.add((round(x, decimals), round(y, decimals), round(z, decimals)))

        # 他のセルの面と比較
        matching_cells = []

        for other_cell_idx, other_faces in cell_faces.items():
            if other_cell_idx == 0:
                continue

            for j, other_face_vertices in enumerate(other_faces):
                # この面の頂点座標を取得
                coords_other = set()
                for v_idx in other_face_vertices:
                    x, y, z = global_vertices[v_idx]
                    decimals = 3
                    coords_other.add((round(x, decimals), round(y, decimals), round(z, decimals)))

                # 座標セットが一致するか？
                if coords_0 == coords_other:
                    matching_cells.append((other_cell_idx, len(coords_other)))

                    if other_cell_idx not in shared_count:
                        shared_count[other_cell_idx] = 0
                    shared_count[other_cell_idx] += 1

        if len(matching_cells) > 0:
            print("  Face {} ({} vertices): shared with {}".format(
                i, len(coords_0), matching_cells
            ))
            # 座標も表示（最初の3つまで）
            coord_list = list(coords_0)[:3]
            for coord in coord_list:
                print("    Vertex: ({:.2f}, {:.2f}, {:.2f})".format(coord[0], coord[1], coord[2]))

    print()
    print("=" * 70)
    print("Summary: Cell 0's adjacent cells")
    print("=" * 70)

    if len(shared_count) > 0:
        for cell_idx in sorted(shared_count.keys()):
            count = shared_count[cell_idx]
            print("  Cell 0 <-> Cell {}: {} shared face(s)".format(cell_idx, count))

        print()
        print("Total adjacent cells: {}".format(len(shared_count)))
    else:
        print("  No shared faces detected!")

    print("=" * 70)

if __name__ == '__main__':
    OBJ_FILE = "/home/shint/py_code/IEC/gen_log/gen0_A_inner.obj"
    inspect_shared_faces(OBJ_FILE)
