# -*- coding: utf-8 -*-
"""
test_area_filter.py - 面積フィルターの効果をテスト
"""

import sys
sys.path.insert(0, '/home/shint/py_code/IEC/rhino')
from test_face_detection import parse_obj_with_faces

def calculate_polygon_area(vertices):
    """3D多角形の面積を計算（explode_view.pyと同じ）"""
    if len(vertices) < 3:
        return 0.0

    total_area = 0.0
    v0 = vertices[0]

    for i in range(1, len(vertices) - 1):
        v1 = vertices[i]
        v2 = vertices[i + 1]

        vec1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        vec2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])

        cross = (
            vec1[1] * vec2[2] - vec1[2] * vec2[1],
            vec1[2] * vec2[0] - vec1[0] * vec2[2],
            vec1[0] * vec2[1] - vec1[1] * vec2[0]
        )

        magnitude = (cross[0]**2 + cross[1]**2 + cross[2]**2) ** 0.5
        total_area += magnitude / 2.0

    return total_area

def test_area_thresholds(obj_path):
    """異なる面積閾値で隣接検出をテスト"""
    print("=" * 70)
    print("Area-Based Filtering Test")
    print("=" * 70)
    print("File: {}".format(obj_path))
    print()

    global_vertices, cell_faces = parse_obj_with_faces(obj_path)
    print("Parsed {} vertices, {} cells".format(len(global_vertices), len(cell_faces)))
    print()

    # 全ての面の面積を計算
    print("[Step 1] Calculating all face areas...")
    all_face_areas = []

    for cell_idx, faces in cell_faces.items():
        for face_vertices in faces:
            if len(face_vertices) >= 3:
                coords = []
                for v_idx in face_vertices:
                    coords.append(global_vertices[v_idx])
                area = calculate_polygon_area(coords)
                all_face_areas.append(area)

    print("  Total faces: {}".format(len(all_face_areas)))
    print("  Face area range: {:.1f} to {:.1f} mm^2".format(
        min(all_face_areas), max(all_face_areas)
    ))
    print("  Average face area: {:.1f} mm^2".format(
        sum(all_face_areas) / len(all_face_areas)
    ))
    print("  Median face area: {:.1f} mm^2".format(
        sorted(all_face_areas)[len(all_face_areas)//2]
    ))
    print()

    # 面積の分布を表示
    print("[Step 2] Face area distribution:")
    area_bins = [0, 10, 50, 100, 500, 1000, 5000, float('inf')]
    bin_labels = ["<10", "10-50", "50-100", "100-500", "500-1000", "1000-5000", ">5000"]

    for i in range(len(area_bins) - 1):
        count = sum(1 for a in all_face_areas if area_bins[i] <= a < area_bins[i+1])
        percentage = 100.0 * count / len(all_face_areas)
        print("  {} mm^2: {} faces ({:.1f}%)".format(bin_labels[i], count, percentage))
    print()

    # 異なる閾値でテスト
    print("[Step 3] Testing different area thresholds:")
    print("=" * 70)

    thresholds = [0, 10, 50, 100, 200, 500]

    for min_area in thresholds:
        # 面積閾値を満たす共有面を数える
        face_coord_to_cells = {}
        decimals = 3

        for cell_idx, faces in cell_faces.items():
            for face_vertices in faces:
                if len(face_vertices) >= 4:  # 4頂点以上
                    coords = []
                    for v_idx in face_vertices:
                        coords.append(global_vertices[v_idx])

                    area = calculate_polygon_area(coords)

                    if area >= min_area:
                        rounded_coords = set()
                        for x, y, z in coords:
                            rounded = (round(x, decimals), round(y, decimals), round(z, decimals))
                            rounded_coords.add(rounded)

                        coord_set = frozenset(rounded_coords)

                        if coord_set not in face_coord_to_cells:
                            face_coord_to_cells[coord_set] = []

                        face_coord_to_cells[coord_set].append(cell_idx)

        # 隣接リストを構築
        adjacency = {}
        for coord_set, cells_with_face in face_coord_to_cells.items():
            if len(cells_with_face) >= 2:
                cells = list(set(cells_with_face))

                for i, cell_i in enumerate(cells):
                    for j in range(i + 1, len(cells)):
                        cell_j = cells[j]

                        if cell_i not in adjacency:
                            adjacency[cell_i] = set()
                        if cell_j not in adjacency:
                            adjacency[cell_j] = set()

                        adjacency[cell_i].add(cell_j)
                        adjacency[cell_j].add(cell_i)

        # 統計
        if len(adjacency) > 0:
            neighbor_counts = [len(neighbors) for neighbors in adjacency.values()]
            avg_neighbors = sum(neighbor_counts) / len(neighbor_counts)
            max_neighbors = max(neighbor_counts)

            unique_pairs = set()
            for cell_i, neighbors in adjacency.items():
                for cell_j in neighbors:
                    pair = tuple(sorted([cell_i, cell_j]))
                    unique_pairs.add(pair)

            print("\nMin area: {} mm^2 or more (4+ vertices)".format(min_area))
            print("  -> Total adjacencies (cell pairs): {}".format(len(unique_pairs)))
            print("  -> Cells with neighbors: {}".format(len(adjacency)))
            print("  -> Avg neighbors per cell: {:.1f}".format(avg_neighbors))
            print("  -> Max neighbors per cell: {}".format(max_neighbors))

            # Cell 39の隣接数
            if 39 in adjacency:
                print("  -> Cell 39: {} neighbors".format(len(adjacency[39])))

            # 異常に多い隣接を持つセル数（Cell 0, 1を除く）
            abnormal_count = sum(1 for idx, count in zip(adjacency.keys(), neighbor_counts)
                                if idx not in [0, 1] and count > 8)
            print("  -> Cells with >8 neighbors (excluding Cell 0,1): {}".format(abnormal_count))

        else:
            print("\nMin area: {} mm^2 or more".format(min_area))
            print("  -> No adjacencies detected")

    print()
    print("=" * 70)
    print("Recommendation: 100 mm^2 seems like a good threshold")
    print("=" * 70)

if __name__ == '__main__':
    OBJ_FILE = "/home/shint/py_code/IEC/gen_log/gen25_A_inner.obj"
    test_area_thresholds(OBJ_FILE)
