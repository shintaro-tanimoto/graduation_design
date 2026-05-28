# -*- coding: utf-8 -*-
"""
test_obj_parsing.py - OBJ解析機能のテストスクリプト

explode_view.pyの解析ロジックを独立してテストします。
"""

import os

# OBJ解析関数（explode_view.pyから抽出）
def parse_obj_file(obj_path):
    """
    OBJファイルを解析して頂点座標とセル-頂点関係を抽出

    Args:
        obj_path: OBJファイルのパス

    Returns:
        global_vertices: 頂点座標のリスト [(x, y, z), ...] (0-indexed)
        cell_vertex_map: セルごとの頂点インデックスの辞書 {cell_idx: [vertex_indices]}
    """
    global_vertices = []
    cell_vertex_map = {}
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
                cell_vertex_map[current_cell] = set()

            # 面を解析
            elif line.startswith('f ') and current_cell is not None:
                parts = line.split()[1:]  # 'f' をスキップ
                for part in parts:
                    # "v/vt/vn" 形式を処理（頂点インデックスのみ必要）
                    v_idx = int(part.split('/')[0])
                    # OBJの1-basedインデックスをPythonの0-basedに変換
                    cell_vertex_map[current_cell].add(v_idx - 1)

    # セットをソート済みリストに変換（一貫性のため）
    for cell_idx in cell_vertex_map:
        cell_vertex_map[cell_idx] = sorted(list(cell_vertex_map[cell_idx]))

    return global_vertices, cell_vertex_map

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

def build_adjacency_list(shared_vertex_groups, min_shared_vertices=3):
    """
    共有頂点グループから隣接リストを構築

    2つのセルは面を共有している場合のみ隣接しているとみなす（3個以上の頂点を共有）

    Args:
        shared_vertex_groups: 共有頂点グループ [[(v_idx, cell_idx), ...], ...]
        min_shared_vertices: 隣接とみなす最小共有頂点数（デフォルト: 3、面共有）

    Returns:
        adjacency: セルインデックスから隣接セルインデックスのセットへのマッピング
                   {cell_idx: set(adjacent_cell_indices)}
        shared_vertex_count: デバッグ用の共有頂点数辞書 {(cell_i, cell_j): count}
    """
    # セルペア間の共有頂点数をカウント
    shared_vertex_count = {}  # {(cell_i, cell_j): count}

    for group in shared_vertex_groups:
        # このグループ内の一意なセルインデックスを抽出
        cells_in_group = list(set(cell_idx for _, cell_idx in group))

        # 全てのペアの共有頂点数を増やす
        for i, cell_i in enumerate(cells_in_group):
            for j in range(i + 1, len(cells_in_group)):
                cell_j = cells_in_group[j]
                pair = tuple(sorted([cell_i, cell_j]))
                shared_vertex_count[pair] = shared_vertex_count.get(pair, 0) + 1

    # 隣接リストを構築 - 十分な共有頂点を持つペアのみ含める
    adjacency = {}

    for (cell_i, cell_j), count in shared_vertex_count.items():
        if count >= min_shared_vertices:  # 面を共有している場合のみ（3個以上の頂点）
            if cell_i not in adjacency:
                adjacency[cell_i] = set()
            if cell_j not in adjacency:
                adjacency[cell_j] = set()

            adjacency[cell_i].add(cell_j)
            adjacency[cell_j].add(cell_i)

    return adjacency, shared_vertex_count

def test_parsing(obj_path):
    """OBJ解析機能をテスト"""
    print("=" * 70)
    print("OBJ Parsing Test - OBJ解析テスト")
    print("=" * 70)
    print("File: {}".format(obj_path))
    print()

    if not os.path.exists(obj_path):
        print("ERROR: File not found!")
        return

    # OBJを解析
    print("[Test 1] Parsing OBJ file...")
    global_vertices, cell_vertex_map = parse_obj_file(obj_path)
    print("  Parsed {} vertices".format(len(global_vertices)))
    print("  Parsed {} cells".format(len(cell_vertex_map)))
    print()

    # サンプル情報を表示
    print("[Test 2] Sample data:")
    if len(global_vertices) > 0:
        print("  First vertex: {}".format(global_vertices[0]))
        print("  Last vertex: {}".format(global_vertices[-1]))
    print()

    if len(cell_vertex_map) > 0:
        sample_cell = sorted(cell_vertex_map.keys())[0]
        print("  Cell {}: {} vertices".format(sample_cell, len(cell_vertex_map[sample_cell])))
        print("  First 5 vertex indices: {}".format(cell_vertex_map[sample_cell][:5]))
    print()

    # 共有頂点を検出（座標で比較）
    print("[Test 3] Finding shared vertices by coordinates...")
    shared_vertex_groups = find_shared_vertices(global_vertices, cell_vertex_map)
    print("  Found {} shared vertex groups".format(len(shared_vertex_groups)))
    print()

    # 共有頂点グループの統計
    if len(shared_vertex_groups) > 0:
        group_sizes = [len(group) for group in shared_vertex_groups]
        print("  Shared vertex group statistics:")
        print("    Min vertices per group: {}".format(min(group_sizes)))
        print("    Max vertices per group: {}".format(max(group_sizes)))
        print("    Avg vertices per group: {:.2f}".format(sum(group_sizes) / len(group_sizes)))
        print()

        # サンプル共有頂点グループを表示
        sample_group = shared_vertex_groups[0]
        print("  Sample shared vertex group (first group):")
        for v_idx, cell_idx in sample_group:
            print("    Vertex {} (cell {}): {}".format(v_idx, cell_idx, global_vertices[v_idx]))
    print()

    # 隣接リストを構築（重心接続のため）
    print("[Test 4] Building adjacency list for centroid connections...")
    print("  Requirement: Cells must share 3+ vertices (face sharing)")
    adjacency, shared_vertex_count = build_adjacency_list(shared_vertex_groups, min_shared_vertices=3)
    print("  Total cells with neighbors: {}".format(len(adjacency)))
    print()

    # 共有頂点数の分布を表示
    print("[Test 5] Shared vertex count distribution:")
    count_distribution = {}
    for count in shared_vertex_count.values():
        count_distribution[count] = count_distribution.get(count, 0) + 1

    total_pairs = len(shared_vertex_count)
    for count in sorted(count_distribution.keys()):
        num_pairs = count_distribution[count]
        percentage = 100.0 * num_pairs / total_pairs if total_pairs > 0 else 0
        status = "ADJACENT (face sharing)" if count >= 3 else "NOT adjacent (edge/point only)"
        print("  {} vertices: {} cell pairs ({:.1f}%) - {}".format(
            count, num_pairs, percentage, status
        ))
    print()

    # 隣接統計
    if len(adjacency) > 0:
        neighbor_counts = [len(neighbors) for neighbors in adjacency.values()]
        print("  Adjacency statistics (face-sharing only):")
        print("    Min neighbors per cell: {}".format(min(neighbor_counts)))
        print("    Max neighbors per cell: {}".format(max(neighbor_counts)))
        print("    Avg neighbors per cell: {:.1f}".format(sum(neighbor_counts) / len(neighbor_counts)))

        # ユニークな隣接ペアの数を計算
        unique_pairs = set()
        for cell_i, neighbors in adjacency.items():
            for cell_j in neighbors:
                pair = tuple(sorted([cell_i, cell_j]))
                unique_pairs.add(pair)

        print("    Total unique adjacencies (cell pairs): {}".format(len(unique_pairs)))
        print("    Expected centroid guide lines: {}".format(len(unique_pairs)))

        # サンプル隣接関係を表示
        if len(adjacency) > 0:
            sample_cell = sorted(adjacency.keys())[0]
            print("  Sample: Cell {} is adjacent to cells: {}".format(
                sample_cell, sorted(list(adjacency[sample_cell]))
            ))
    else:
        print("  WARNING: No cells marked as adjacent (no face sharing detected)")
    print()

    print("=" * 70)
    print("Test COMPLETED!")
    print("=" * 70)

if __name__ == '__main__':
    # テスト対象のOBJファイル
    OBJ_FILE = "/home/shint/py_code/IEC/gen_log/gen0_A_inner.obj"

    # 別のファイルでもテスト可能
    # OBJ_FILE = "/home/shint/py_code/IEC/gen_log/gen25_A_inner.obj"

    test_parsing(OBJ_FILE)
