# -*- coding: utf-8 -*-
"""
measure_vertex_distances.py - 共有面の頂点間の実際の距離を測定
"""

import sys
import math
sys.path.insert(0, '/home/shint/py_code/IEC/rhino')
from test_face_detection import parse_obj_with_faces

def distance_3d(p1, p2):
    """3D距離を計算"""
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    dz = p1[2] - p2[2]
    return math.sqrt(dx*dx + dy*dy + dz*dz)

def measure_shared_face_distances(obj_path):
    """共有面の頂点間の実際の距離を測定"""
    print("=" * 70)
    print("Shared Face Vertex Distance Measurement")
    print("=" * 70)

    global_vertices, cell_faces = parse_obj_with_faces(obj_path)

    if 0 not in cell_faces or 1 not in cell_faces:
        print("ERROR: Cells not found!")
        return

    print("Measuring distances for shared faces...")
    print()

    tolerance = 0.001

    # Cell 0とCell 1の共有面を探す
    cell_0_faces = cell_faces[0]
    cell_1_faces = cell_faces[1]

    for i, face_0_vertices in enumerate(cell_0_faces):
        # この面の頂点座標（丸め込みあり）
        coords_0_rounded = set()
        coords_0_original = []

        for v_idx in face_0_vertices:
            x, y, z = global_vertices[v_idx]
            coords_0_original.append((x, y, z, v_idx))
            decimals = 3
            coords_0_rounded.add((round(x, decimals), round(y, decimals), round(z, decimals)))

        # Cell 1の面と比較
        for j, face_1_vertices in enumerate(cell_1_faces):
            coords_1_rounded = set()
            coords_1_original = []

            for v_idx in face_1_vertices:
                x, y, z = global_vertices[v_idx]
                coords_1_original.append((x, y, z, v_idx))
                decimals = 3
                coords_1_rounded.add((round(x, decimals), round(y, decimals), round(z, decimals)))

            # 丸め込んだ座標が一致するか？
            if coords_0_rounded == coords_1_rounded:
                print("Shared face found:")
                print("  Cell 0 face {} <-> Cell 1 face {}".format(i, j))
                print("  Number of vertices: {}".format(len(coords_0_rounded)))
                print()

                # 対応する頂点ペアを見つけて距離を測定
                print("  Vertex coordinate comparison:")
                print("  " + "-" * 66)

                for coord_rounded in coords_0_rounded:
                    # Cell 0でこの座標を持つ頂点を探す
                    v0_matches = [(x, y, z, v_idx) for x, y, z, v_idx in coords_0_original
                                  if (round(x, 3), round(y, 3), round(z, 3)) == coord_rounded]

                    # Cell 1でこの座標を持つ頂点を探す
                    v1_matches = [(x, y, z, v_idx) for x, y, z, v_idx in coords_1_original
                                  if (round(x, 3), round(y, 3), round(z, 3)) == coord_rounded]

                    if len(v0_matches) > 0 and len(v1_matches) > 0:
                        x0, y0, z0, v_idx_0 = v0_matches[0]
                        x1, y1, z1, v_idx_1 = v1_matches[0]

                        dist = distance_3d((x0, y0, z0), (x1, y1, z1))

                        print("  Cell 0 v{}: ({:.10f}, {:.10f}, {:.10f})".format(v_idx_0, x0, y0, z0))
                        print("  Cell 1 v{}: ({:.10f}, {:.10f}, {:.10f})".format(v_idx_1, x1, y1, z1))
                        print("  Distance: {:.12f} mm".format(dist))
                        print()

                print("=" * 70)
                return  # 最初の共有面のみ表示

    print("No shared faces found!")
    print("=" * 70)

if __name__ == '__main__':
    OBJ_FILE = "/home/shint/py_code/IEC/gen_log/gen0_A_inner.obj"
    measure_shared_face_distances(OBJ_FILE)
