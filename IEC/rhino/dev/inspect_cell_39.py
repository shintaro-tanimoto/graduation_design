# -*- coding: utf-8 -*-
"""
inspect_cell_39.py - Cell 39の共有面を詳細に調査（gen25）
"""

import sys
sys.path.insert(0, '/home/shint/py_code/IEC/rhino')
from test_face_detection import parse_obj_with_faces

def inspect_cell_39(obj_path):
    """Cell 39の共有面を詳細に調査"""
    print("=" * 70)
    print("Cell 39 Shared Faces - Detailed Inspection (gen25)")
    print("=" * 70)

    global_vertices, cell_faces = parse_obj_with_faces(obj_path)
    print("Parsed {} vertices, {} cells".format(len(global_vertices), len(cell_faces)))
    print()

    if 39 not in cell_faces:
        print("ERROR: Cell 39 not found!")
        return

    cell_39_faces = cell_faces[39]
    print("Cell 39: {} faces".format(len(cell_39_faces)))
    print()

    # Cell 39の各面のサイズ分布
    face_sizes = [len(face) for face in cell_39_faces]
    print("Cell 39 face sizes:")
    size_dist = {}
    for size in face_sizes:
        size_dist[size] = size_dist.get(size, 0) + 1

    for size in sorted(size_dist.keys()):
        print("  {} vertices: {} faces".format(size, size_dist[size]))
    print()

    # 各面について、他のセルと共有しているか調べる
    print("Checking shared faces:")
    print()

    shared_count = {}  # {cell_idx: [(face_39_idx, face_other_idx, num_vertices)]}

    for i, face_39_vertices in enumerate(cell_39_faces):
        # この面の頂点座標セット
        coords_39 = set()
        for v_idx in face_39_vertices:
            x, y, z = global_vertices[v_idx]
            coords_39.add((round(x, 3), round(y, 3), round(z, 3)))

        # 他のセルの面と比較
        for other_cell_idx, other_faces in cell_faces.items():
            if other_cell_idx == 39:
                continue

            for j, other_face_vertices in enumerate(other_faces):
                coords_other = set()
                for v_idx in other_face_vertices:
                    x, y, z = global_vertices[v_idx]
                    coords_other.add((round(x, 3), round(y, 3), round(z, 3)))

                # 座標セットが完全一致するか？
                if coords_39 == coords_other:
                    if other_cell_idx not in shared_count:
                        shared_count[other_cell_idx] = []
                    shared_count[other_cell_idx].append((i, j, len(coords_39), len(coords_other)))

    # 結果を表示
    print("Cell 39's shared faces with other cells:")
    print("-" * 70)

    for cell_idx in sorted(shared_count.keys()):
        shared_faces = shared_count[cell_idx]
        print()
        print("  Cell 39 <-> Cell {}:  {} shared face(s)".format(cell_idx, len(shared_faces)))

        for face_39_idx, face_other_idx, size_39, size_other in shared_faces:
            print("    Cell 39 face {} ({} vertices) == Cell {} face {} ({} vertices)".format(
                face_39_idx, size_39, cell_idx, face_other_idx, size_other
            ))

            # 最初の共有面の座標を詳しく表示（サンプル）
            if face_39_idx == shared_faces[0][0]:
                face_vertices = cell_39_faces[face_39_idx]
                print("      Vertex coordinates:")
                for v_idx in face_vertices[:3]:  # 最初の3つ
                    x, y, z = global_vertices[v_idx]
                    print("        v{}: ({:.3f}, {:.3f}, {:.3f})".format(v_idx, x, y, z))

    print()
    print("=" * 70)
    print("Total adjacent cells detected: {}".format(len(shared_count)))
    print("=" * 70)

if __name__ == '__main__':
    OBJ_FILE = "/home/shint/py_code/IEC/gen_log/gen25_A_inner.obj"
    inspect_cell_39(OBJ_FILE)
