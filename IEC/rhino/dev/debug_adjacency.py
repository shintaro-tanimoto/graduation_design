# -*- coding: utf-8 -*-
"""
debug_adjacency.py - 隣接関係の詳細デバッグ

共有頂点グループの構造を詳しく調べて、誤った隣接関係の原因を特定します。
"""

import os
import sys

# test_obj_parsing.pyから関数をインポート
sys.path.insert(0, '/home/shint/py_code/IEC/rhino')
from test_obj_parsing import parse_obj_file, find_shared_vertices

def analyze_shared_vertex_groups(obj_path):
    """共有頂点グループを詳細に解析"""
    print("=" * 70)
    print("Shared Vertex Groups - Detailed Analysis")
    print("=" * 70)
    print("File: {}".format(obj_path))
    print()

    # OBJを解析
    global_vertices, cell_vertex_map = parse_obj_file(obj_path)
    print("Parsed {} vertices, {} cells".format(len(global_vertices), len(cell_vertex_map)))
    print()

    # 共有頂点を検出
    shared_vertex_groups = find_shared_vertices(global_vertices, cell_vertex_map)
    print("Found {} shared vertex groups".format(len(shared_vertex_groups)))
    print()

    # グループサイズの分布
    print("[Analysis 1] Group size distribution (how many cells share each vertex):")
    size_distribution = {}
    for group in shared_vertex_groups:
        cells_in_group = set(cell_idx for _, cell_idx in group)
        size = len(cells_in_group)
        size_distribution[size] = size_distribution.get(size, 0) + 1

    for size in sorted(size_distribution.keys()):
        print("  {} cells: {} groups".format(size, size_distribution[size]))
    print()

    # 大きなグループのサンプルを表示（3つ以上のセルを含む）
    print("[Analysis 2] Sample groups with 3+ cells (potential issue):")
    large_groups = [g for g in shared_vertex_groups if len(set(c for _, c in g)) >= 3]

    if len(large_groups) > 0:
        print("  Found {} groups with 3+ cells".format(len(large_groups)))
        print()

        # 最初の5つのグループを詳しく表示
        for i, group in enumerate(large_groups[:5]):
            cells_in_group = sorted(set(cell_idx for _, cell_idx in group))
            print("  Group {} - {} cells: {}".format(i, len(cells_in_group), cells_in_group))

            # この頂点の座標を表示
            v_idx, _ = group[0]
            pos = global_vertices[v_idx]
            print("    Position: ({:.2f}, {:.2f}, {:.2f})".format(pos[0], pos[1], pos[2]))
            print("    Vertices in group:")
            for v_idx, cell_idx in group:
                print("      v{} from cell {}".format(v_idx, cell_idx))

            # このグループによって作られるセルペアの数
            num_pairs = len(cells_in_group) * (len(cells_in_group) - 1) // 2
            print("    This group creates {} cell pairs".format(num_pairs))
            print()
    else:
        print("  No groups with 3+ cells found")
    print()

    # 現在のアルゴリズムでの共有頂点数カウント
    print("[Analysis 3] Cell pair shared vertex counts (current algorithm):")
    shared_vertex_count = {}

    for group in shared_vertex_groups:
        cells_in_group = list(set(cell_idx for _, cell_idx in group))

        for i, cell_i in enumerate(cells_in_group):
            for j in range(i + 1, len(cells_in_group)):
                cell_j = cells_in_group[j]
                pair = tuple(sorted([cell_i, cell_j]))
                shared_vertex_count[pair] = shared_vertex_count.get(pair, 0) + 1

    # 高い共有頂点数を持つペアをいくつか表示
    high_count_pairs = sorted(shared_vertex_count.items(), key=lambda x: x[1], reverse=True)

    print("  Top 10 cell pairs by shared vertex count:")
    for (cell_i, cell_j), count in high_count_pairs[:10]:
        print("    Cells {} <-> {}: {} shared vertices".format(cell_i, cell_j, count))
    print()

    # 3個の共有頂点を持つペアをいくつか表示（ギリギリで隣接とみなされる）
    three_count_pairs = [(pair, count) for pair, count in shared_vertex_count.items() if count == 3]
    if len(three_count_pairs) > 0:
        print("  Cell pairs with EXACTLY 3 shared vertices (minimum for adjacency):")
        for (cell_i, cell_j), count in three_count_pairs[:10]:
            print("    Cells {} <-> {}".format(cell_i, cell_j))
    print()

    print("=" * 70)

if __name__ == '__main__':
    OBJ_FILE = "/home/shint/py_code/IEC/gen_log/gen0_A_inner.obj"
    analyze_shared_vertex_groups(OBJ_FILE)
