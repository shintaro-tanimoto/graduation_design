# -*- coding: utf-8 -*-
"""
analyze_gen25.py - gen25_A_inner.objの隣接関係を解析
"""

import sys
sys.path.insert(0, '/home/shint/py_code/IEC/rhino')
from test_face_detection import parse_obj_with_faces, find_face_sharing_cells

def analyze_adjacencies(obj_path):
    """各セルの隣接数を解析して異常を検出"""
    print("=" * 70)
    print("Adjacency Analysis: {}".format(obj_path))
    print("=" * 70)

    global_vertices, cell_faces = parse_obj_with_faces(obj_path)
    print("Parsed {} vertices, {} cells".format(len(global_vertices), len(cell_faces)))
    print()

    # 面ベースの隣接検出
    adjacency, shared_faces = find_face_sharing_cells(global_vertices, cell_faces)
    print("Total cells with neighbors: {}".format(len(adjacency)))
    print()

    # 各セルの隣接数を表示（多い順）
    print("Cells sorted by number of neighbors:")
    print("-" * 70)

    neighbor_counts = []
    for cell_idx in sorted(adjacency.keys()):
        count = len(adjacency[cell_idx])
        neighbor_counts.append((cell_idx, count))

    # 多い順にソート
    neighbor_counts.sort(key=lambda x: x[1], reverse=True)

    for cell_idx, count in neighbor_counts:
        neighbors = sorted(list(adjacency[cell_idx]))

        # Cell 0, 1は多くの隣接を持つことが期待される
        if cell_idx in [0, 1]:
            status = "(expected - central cell)"
        elif count > 10:
            status = "**ABNORMAL - too many neighbors**"
        elif count > 6:
            status = "(possibly abnormal)"
        else:
            status = "(normal)"

        print("  Cell {:3d}: {:2d} neighbors {} - {}".format(
            cell_idx, count, status, neighbors if count <= 20 else str(neighbors[:10]) + "..."
        ))

    print()

    # 統計
    counts_only = [c for _, c in neighbor_counts]
    print("Statistics:")
    print("  Min neighbors: {}".format(min(counts_only)))
    print("  Max neighbors: {}".format(max(counts_only)))
    print("  Avg neighbors: {:.1f}".format(sum(counts_only) / len(counts_only)))
    print("  Median neighbors: {}".format(sorted(counts_only)[len(counts_only)//2]))
    print()

    # 異常に多い隣接を持つセルをリストアップ（Cell 0, 1を除く）
    abnormal_cells = [(idx, count) for idx, count in neighbor_counts
                      if idx not in [0, 1] and count > 8]

    if len(abnormal_cells) > 0:
        print("Cells with abnormally high neighbor counts (excluding Cell 0, 1):")
        for cell_idx, count in abnormal_cells:
            print("  Cell {}: {} neighbors".format(cell_idx, count))
    else:
        print("No abnormal neighbor counts detected!")

    print("=" * 70)

if __name__ == '__main__':
    OBJ_FILE = "/home/shint/py_code/IEC/gen_log/gen25_A_inner.obj"
    analyze_adjacencies(OBJ_FILE)
