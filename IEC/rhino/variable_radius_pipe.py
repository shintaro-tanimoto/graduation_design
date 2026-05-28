# -*- coding: utf-8 -*-
"""
variable_radius_pipe.py - Variable-Radius Pipe Generator for Rhino

Laguerre VoronoiダイアグラムのエッジまたはRhino曲線から、可変半径のパイプ構造を生成します。
パイプは接続ノード（複数のエッジが交わる点）で太く、エッジ中央で細くなる有機的な形状を持ちます。

Generates pipe structures with variable radius from curves:
- Thicker at nodes (proportional to connectivity degree)
- Thinner in the middle of edges
- Smooth interpolation along curves

Usage in Rhino Python Editor:
    RunPythonScript "variable_radius_pipe.py"

Or:
    import sys
    sys.path.append('/home/shint/py_code/IEC/rhino')
    import variable_radius_pipe
    variable_radius_pipe.run()

Author: Generated for IEC project
Date: 2025-12-27
"""

import rhinoscriptsyntax as rs
import Rhino
import math


# ===== 設定 (Configuration) =====

DEFAULT_PARAMS = {
    # トポロジ (Topology)
    'endpoint_tolerance': 1.0,      # mm - 端点統合の許容誤差 (tolerance for merging endpoints)

    # 半径 (Radius)
    'base_radius': 10.0,            # mm - 基準半径（最小） (minimum pipe radius)
    'node_scaling_factor': 0.5,     # ノード半径スケール係数 (radius increase per additional edge)
    'middle_taper_ratio': 0.8,      # 中央の細さ（0.8 = 80%） (minimum radius at center as ratio)
    'interpolation_type': 'smooth', # 'linear', 'smooth', 'cosine', 'taper'

    # ジオメトリ解像度 (Geometry Resolution)
    'num_segments': 12,             # 曲線方向のセグメント数 (segments along curve length)
    'num_sides': 12,                # 円周方向の分割数 (sides in circular cross-section)

    # 出力 (Output)
    'layer_name': 'Pipes',          # 出力レイヤー (output layer for pipe meshes)
    'create_caps': True,            # 端点キャップの作成 (create end caps at open endpoints)
    'merge_meshes': False,          # 全メッシュを結合するか (merge all pipes into single mesh)

    # デバッグ (Debugging)
    'show_nodes': False,            # ノード位置に球を表示 (draw spheres at nodes)
    'show_circles': False,          # 断面円を表示 (draw cross-section circles)
    'verbose': True                 # 進捗メッセージ (print progress messages)
}

MAX_DEGREE = 10  # 警告を出す最大接続度 (max degree before warning)


# ===== データ構造 (Data Structures) =====

class Node:
    """
    ノード（接続点）を表現
    Represents a junction point where curves meet
    """
    def __init__(self, position, tolerance=0.01):
        """
        Args:
            position: (x, y, z) tuple
            tolerance: distance threshold for considering points as same
        """
        self.position = position  # (x, y, z) 座標
        self.edges = []           # 接続するEdgeオブジェクトのリスト
        self.degree = 0           # 接続度（エッジ数）
        self.radius = 0.0         # 計算された半径
        self.tolerance = tolerance

    def add_edge(self, edge):
        """エッジを追加して接続度を更新 (Add edge and update degree)"""
        if edge not in self.edges:
            self.edges.append(edge)
            self.degree = len(self.edges)

    def calculate_radius(self, base_radius, scaling_factor):
        """
        接続度に基づいて半径を計算 (Calculate radius based on connectivity degree)

        Formula: r_node = base_radius × (1 + scaling_factor × (degree - 1))

        Args:
            base_radius: 基準半径 (minimum radius)
            scaling_factor: スケール係数 (scaling factor)

        Returns:
            計算された半径 (calculated radius)
        """
        self.radius = base_radius * (1.0 + scaling_factor * (self.degree - 1))
        return self.radius


class Edge:
    """
    エッジ（曲線）を表現
    Represents a curve with topology information
    """
    def __init__(self, curve_id):
        """
        Args:
            curve_id: Rhino GUID of the curve
        """
        self.curve_id = curve_id      # Rhino GUID
        self.start_node = None        # 始点ノード (start node)
        self.end_node = None          # 終点ノード (end node)
        self.length = 0.0             # 曲線長さ (curve length in mm)
        self.domain = None            # パラメータ領域 (curve parameter domain)


class TopologyGraph:
    """
    ノード-エッジのトポロジグラフを管理
    Manages node-edge connectivity
    """
    def __init__(self):
        self.nodes = []      # ノードリスト (list of Node objects)
        self.edges = []      # エッジリスト (list of Edge objects)
        self.node_map = {}   # 空間ハッシュマップ (spatial hash map: {grid_key: Node})

    def _position_to_key(self, position, tolerance):
        """
        座標をグリッドセルキーに変換（空間ハッシュ用）
        Convert position to grid cell key for spatial hashing

        Args:
            position: (x, y, z) tuple
            tolerance: grid cell size factor

        Returns:
            (ix, iy, iz) grid cell key
        """
        grid_size = tolerance * 2.0
        return (
            int(position[0] / grid_size),
            int(position[1] / grid_size),
            int(position[2] / grid_size)
        )

    def find_or_create_node(self, position, tolerance):
        """
        許容誤差内の既存ノードを探すか、新規作成
        Find existing node within tolerance or create new one

        Args:
            position: (x, y, z) tuple
            tolerance: distance threshold

        Returns:
            Node object (existing or new)
        """
        key = self._position_to_key(position, tolerance)

        # 近傍グリッドセルを探索（3×3×3 = 27セル）
        # Check neighboring grid cells (3x3x3 = 27 cells)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    neighbor_key = (key[0] + dx, key[1] + dy, key[2] + dz)
                    if neighbor_key in self.node_map:
                        node = self.node_map[neighbor_key]
                        dist = rs.Distance(position, node.position)
                        if dist <= tolerance:
                            return node  # 既存ノードを返す (return existing node)

        # 新規ノード作成 (create new node)
        new_node = Node(position, tolerance)
        self.node_map[key] = new_node
        self.nodes.append(new_node)
        return new_node

    def add_edge(self, edge):
        """エッジを追加 (Add edge to graph)"""
        if edge not in self.edges:
            self.edges.append(edge)

    def get_statistics(self):
        """
        トポロジ統計情報を取得（デバッグ用）
        Get topology statistics for debugging

        Returns:
            dict with statistics
        """
        if not self.nodes:
            return {'num_nodes': 0, 'num_edges': 0, 'max_degree': 0}

        degrees = [node.degree for node in self.nodes]
        return {
            'num_nodes': len(self.nodes),
            'num_edges': len(self.edges),
            'max_degree': max(degrees) if degrees else 0,
            'avg_degree': sum(degrees) / len(degrees) if degrees else 0
        }


# ===== ユーティリティ関数 (Utility Functions) =====

def ensure_layer(name):
    """レイヤーが存在しない場合は作成 (Create layer if it doesn't exist)"""
    if not rs.IsLayer(name):
        rs.AddLayer(name)
        Rhino.RhinoApp.WriteLine("Created layer: {}".format(name))


def clear_layer(layer_name):
    """レイヤー内のオブジェクトを全削除 (Delete all objects in layer)"""
    if rs.IsLayer(layer_name):
        objs = rs.ObjectsByLayer(layer_name, select=False) or []
        if objs:
            rs.DeleteObjects(objs)
            Rhino.RhinoApp.WriteLine("Cleared layer: {} ({} objects)".format(layer_name, len(objs)))


def validate_curve(curve_id, min_length=1.0):
    """
    曲線が有効かチェック
    Check if curve is valid for pipe generation

    Args:
        curve_id: Rhino GUID
        min_length: minimum acceptable length (mm)

    Returns:
        (valid, message) tuple
    """
    if not rs.IsCurve(curve_id):
        return False, "Not a curve"

    length = rs.CurveLength(curve_id)
    if length < min_length:
        return False, "Curve too short ({}mm < {}mm)".format(length, min_length)

    return True, "OK"


# ===== トポロジ解析 (Topology Analysis) =====

def build_topology_graph(curve_ids, tolerance=0.1):
    """
    曲線から端点を抽出し、トポロジグラフを構築
    Build topology graph from curves by merging endpoints within tolerance

    Args:
        curve_ids: list of Rhino curve GUIDs
        tolerance: distance threshold for merging endpoints (mm)

    Returns:
        TopologyGraph object
    """
    graph = TopologyGraph()

    for curve_id in curve_ids:
        # 曲線の検証 (validate curve)
        valid, msg = validate_curve(curve_id)
        if not valid:
            Rhino.RhinoApp.WriteLine("  Skipping curve {}: {}".format(curve_id, msg))
            continue

        # 曲線の端点を取得 (get curve endpoints)
        domain = rs.CurveDomain(curve_id)
        start_pt = rs.EvaluateCurve(curve_id, domain[0])
        end_pt = rs.EvaluateCurve(curve_id, domain[1])

        # ノードを検索または作成 (find or create nodes)
        start_node = graph.find_or_create_node(start_pt, tolerance)
        end_node = graph.find_or_create_node(end_pt, tolerance)

        # エッジを作成 (create edge)
        edge = Edge(curve_id)
        edge.start_node = start_node
        edge.end_node = end_node
        edge.length = rs.CurveLength(curve_id)
        edge.domain = domain

        # ノードとエッジを接続 (link nodes and edges)
        start_node.add_edge(edge)
        end_node.add_edge(edge)
        graph.add_edge(edge)

    return graph


# ===== 半径計算 (Radius Calculation) =====

def calculate_node_radius(degree, base_radius, scaling_factor):
    """
    接続度に基づいてノード半径を計算
    Calculate radius at node based on connectivity degree

    Formula: r_node = base_radius × (1 + scaling_factor × (degree - 1))

    Args:
        degree: 接続度（エッジ数） (number of edges meeting at node)
        base_radius: 基準半径 (minimum pipe radius in mm)
        scaling_factor: スケール係数 (how much radius increases per additional edge)

    Returns:
        Node radius in mm

    Examples:
        degree=1 (endpoint):   r = 10 × (1 + 0.3 × 0) = 10mm
        degree=2 (passthrough): r = 10 × (1 + 0.3 × 1) = 13mm
        degree=3 (T-junction):  r = 10 × (1 + 0.3 × 2) = 16mm
        degree=4 (cross):       r = 10 × (1 + 0.3 × 3) = 19mm
    """
    return base_radius * (1.0 + scaling_factor * (degree - 1))


def interpolate_radius(t, r_start, r_end, interpolation_type='smooth'):
    """
    曲線パラメータに沿った半径補間
    Interpolate radius along curve parameter

    Args:
        t: 正規化パラメータ ∈ [0, 1] (normalized curve parameter)
        r_start: 始点半径 (radius at start node)
        r_end: 終点半径 (radius at end node)
        interpolation_type: 補間タイプ (interpolation type: 'linear', 'smooth', 'cosine')

    Returns:
        Radius at parameter t
    """
    if interpolation_type == 'linear':
        # 線形補間 (simple linear interpolation)
        return r_start + t * (r_end - r_start)

    elif interpolation_type == 'smooth':
        # スムーズなHermite補間（端点での微分=0）
        # Smooth Hermite interpolation (C1 continuous, zero derivative at endpoints)
        h00 = 2*t**3 - 3*t**2 + 1
        h01 = -2*t**3 + 3*t**2
        return h00 * r_start + h01 * r_end

    elif interpolation_type == 'cosine':
        # コサイン補間（線形より滑らか）
        # Cosine interpolation (smoother than linear)
        mu2 = (1 - math.cos(t * math.pi)) / 2.0
        return r_start * (1 - mu2) + r_end * mu2

    else:
        # デフォルトは線形 (default to linear)
        return r_start + t * (r_end - r_start)


def interpolate_radius_with_taper(t, r_start, r_end, min_ratio=0.8):
    """
    中央を細くするテーパー補間
    Radius tapers to min_ratio of endpoint radius at midpoint

    Args:
        t: 正規化パラメータ ∈ [0, 1] (normalized parameter)
        r_start, r_end: 端点半径 (endpoint radii)
        min_ratio: 中央での最小半径比 (minimum radius at center as ratio of average)

    Returns:
        Radius at t
    """
    # 平均端点半径 (average endpoint radius)
    r_avg = (r_start + r_end) / 2.0
    r_min = r_avg * min_ratio

    # 放物線プロファイル: t=0.5で最小
    # Parabolic profile: minimum at t=0.5
    deviation = 4 * (t - 0.5)**2  # 0 at t=0.5, 1 at t=0 or t=1

    r_base = r_min + (r_avg - r_min) * (1 - deviation)

    # 非対称端点の補正 (offset by endpoint asymmetry)
    r_linear = r_start + t * (r_end - r_start)

    return r_base + (r_linear - r_avg)


# ===== ジオメトリ生成 (Geometry Generation) =====

def create_perpendicular_circle(curve_id, parameter, radius, num_sides=12):
    """
    曲線の接線に垂直な円を生成
    Create circle perpendicular to curve at given parameter

    Args:
        curve_id: Rhino curve GUID
        parameter: curve parameter value
        radius: circle radius
        num_sides: number of vertices in circle

    Returns:
        List of points [(x,y,z), ...] for circle vertices
    """
    # 曲線上の点と接線を取得 (get point and tangent on curve)
    point = rs.EvaluateCurve(curve_id, parameter)
    tangent = rs.CurveTangent(curve_id, parameter)

    # 接線を正規化 (normalize tangent)
    tangent = rs.VectorUnitize(tangent)

    # 垂直フレームを構築 (create perpendicular frame)
    # 任意の垂直ベクトルを選択 (choose arbitrary perpendicular vector)
    if abs(tangent[2]) < 0.9:
        up = (0, 0, 1)  # World Z-up
    else:
        up = (1, 0, 0)  # 垂直の場合はX軸使用 (use X if tangent is nearly vertical)

    # 2つの垂直軸を計算 (compute two perpendicular axes)
    perp1 = rs.VectorCrossProduct(tangent, up)
    perp1 = rs.VectorUnitize(perp1)

    perp2 = rs.VectorCrossProduct(tangent, perp1)
    perp2 = rs.VectorUnitize(perp2)

    # 円周上の頂点を生成 (generate circle points)
    vertices = []

    for i in range(num_sides):
        angle = 2.0 * math.pi * i / num_sides
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # 垂直平面上の円周上の点 (point on circle in perpendicular plane)
        v = (
            point[0] + radius * (cos_a * perp1[0] + sin_a * perp2[0]),
            point[1] + radius * (cos_a * perp1[1] + sin_a * perp2[1]),
            point[2] + radius * (cos_a * perp1[2] + sin_a * perp2[2])
        )
        vertices.append(v)

    return vertices


def generate_pipe_mesh_for_edge(edge, graph, params, debug_index=None):
    """
    1つのエッジに対してパイプメッシュを生成
    Generate pipe mesh for one edge (curve)

    Args:
        edge: Edge object
        graph: TopologyGraph
        params: parameter dictionary
        debug_index: edge index for debug output (optional)

    Returns:
        Rhino mesh GUID or None
    """
    curve_id = edge.curve_id
    domain = edge.domain
    num_segments = params['num_segments']
    num_sides = params['num_sides']

    # 端点半径を取得 (get endpoint radii from nodes)
    r_start = edge.start_node.radius
    r_end = edge.end_node.radius

    # デバッグ: 最初のエッジの半径補間を詳細に出力
    if debug_index is not None and debug_index < 2 and params.get('verbose', False):
        Rhino.RhinoApp.WriteLine("    Edge {} detail: start_r={:.2f}, end_r={:.2f}".format(
            debug_index, r_start, r_end
        ))

    # 曲線に沿って断面円を生成 (generate cross-section circles along curve)
    circles = []

    for i in range(num_segments + 1):
        t_normalized = i / float(num_segments)  # 0 to 1
        t_curve = domain[0] + t_normalized * (domain[1] - domain[0])

        # この位置での半径を補間 (interpolate radius at this position)
        if params['interpolation_type'] == 'taper':
            radius = interpolate_radius_with_taper(
                t_normalized, r_start, r_end,
                params['middle_taper_ratio']
            )
        else:
            radius = interpolate_radius(
                t_normalized, r_start, r_end,
                params['interpolation_type']
            )

        # 円頂点を作成 (create circle vertices)
        circle_pts = create_perpendicular_circle(curve_id, t_curve, radius, num_sides)
        circles.append(circle_pts)

    # 頂点とフェースを構築 (build vertices and faces)
    vertices = []
    faces = []

    # 全ての円の頂点を平坦化 (flatten all circle vertices)
    for circle in circles:
        vertices.extend(circle)

    # 連続する円間に四辺形フェースを作成 (create quad faces between consecutive circles)
    for i in range(num_segments):
        for j in range(num_sides):
            # 現在のリングのインデックス (current ring indices)
            v0 = i * num_sides + j
            v1 = i * num_sides + (j + 1) % num_sides

            # 次のリングのインデックス (next ring indices)
            v2 = (i + 1) * num_sides + (j + 1) % num_sides
            v3 = (i + 1) * num_sides + j

            # 四辺形フェース (quad face)
            faces.append([v0, v1, v2, v3])

    # 端点キャップを追加（オプション）(add end caps if enabled)
    if params['create_caps']:
        # 始点キャップ (start cap)
        start_center_idx = len(vertices)
        start_center = _calculate_center(circles[0])
        vertices.append(start_center)

        for j in range(num_sides):
            v0 = j
            v1 = (j + 1) % num_sides
            faces.append([start_center_idx, v1, v0])  # 内向き法線 (inward normal)

        # 終点キャップ (end cap)
        end_center_idx = len(vertices)
        end_center = _calculate_center(circles[-1])
        vertices.append(end_center)

        last_ring_start = num_segments * num_sides
        for j in range(num_sides):
            v0 = last_ring_start + j
            v1 = last_ring_start + (j + 1) % num_sides
            faces.append([end_center_idx, v0, v1])  # 外向き法線 (outward normal)

    # Rhinoメッシュを作成 (create Rhino mesh)
    try:
        mesh = rs.AddMesh(vertices, faces)
        return mesh
    except Exception as e:
        Rhino.RhinoApp.WriteLine("  ERROR creating mesh for curve {}: {}".format(curve_id, e))
        return None


def _calculate_center(points):
    """
    点群の中心を計算
    Calculate center point of a list of points

    Args:
        points: list of (x, y, z) tuples

    Returns:
        (x, y, z) center point
    """
    n = len(points)
    if n == 0:
        return (0, 0, 0)

    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    cz = sum(p[2] for p in points) / n

    return (cx, cy, cz)


# ===== メイン関数 (Main Functions) =====

def generate_pipes(curve_ids, params=None):
    """
    曲線からパイプを生成（プログラマティックAPI）
    Generate pipes from curves (programmatic API)

    Args:
        curve_ids: list of Rhino curve GUIDs
        params: parameter dictionary (optional, uses defaults if None)

    Returns:
        list of created mesh GUIDs
    """
    if params is None:
        params = DEFAULT_PARAMS.copy()

    # ステップ1: トポロジ解析 (Step 1: Analyze topology)
    if params['verbose']:
        Rhino.RhinoApp.WriteLine("\n[Step 1] Analyzing topology...")

    graph = build_topology_graph(curve_ids, params['endpoint_tolerance'])

    stats = graph.get_statistics()
    if params['verbose']:
        Rhino.RhinoApp.WriteLine("  Nodes: {}".format(stats['num_nodes']))
        Rhino.RhinoApp.WriteLine("  Edges: {}".format(stats['num_edges']))
        Rhino.RhinoApp.WriteLine("  Max degree: {}".format(stats['max_degree']))
        Rhino.RhinoApp.WriteLine("  Avg degree: {:.1f}".format(stats['avg_degree']))

    # ステップ2: ノード半径計算 (Step 2: Calculate node radii)
    if params['verbose']:
        Rhino.RhinoApp.WriteLine("\n[Step 2] Calculating node radii...")

    # デバッグ: 接続度の分布を表示
    degree_count = {}
    for node in graph.nodes:
        node.calculate_radius(
            params['base_radius'],
            params['node_scaling_factor']
        )

        # 接続度をカウント
        if node.degree not in degree_count:
            degree_count[node.degree] = 0
        degree_count[node.degree] += 1

        # 高接続度の警告 (warn for high degree nodes)
        if node.degree > MAX_DEGREE and params['verbose']:
            Rhino.RhinoApp.WriteLine(
                "  WARNING: Node at {} has degree {} (very high connectivity)".format(
                    node.position, node.degree
                )
            )

    # 接続度の分布を出力
    if params['verbose']:
        Rhino.RhinoApp.WriteLine("  Degree distribution:")
        for degree in sorted(degree_count.keys()):
            radius = calculate_node_radius(degree, params['base_radius'], params['node_scaling_factor'])
            Rhino.RhinoApp.WriteLine("    Degree {}: {} nodes (radius = {:.2f}mm)".format(
                degree, degree_count[degree], radius
            ))

    # デバッグ: 最初の数ノードの詳細情報
    if params['verbose'] and len(graph.nodes) > 0:
        Rhino.RhinoApp.WriteLine("\n  Sample nodes (first 5):")
        for i, node in enumerate(graph.nodes[:5]):
            Rhino.RhinoApp.WriteLine("    Node {}: pos={}, degree={}, radius={:.2f}mm".format(
                i,
                tuple(round(x, 2) for x in node.position),
                node.degree,
                node.radius
            ))

    # デバッグ: ノード球を表示（オプション）(Debug: show node spheres if enabled)
    if params['show_nodes']:
        for node in graph.nodes:
            sphere = rs.AddSphere(node.position, node.radius)
            if sphere:
                rs.ObjectLayer(sphere, params['layer_name'] + "_Debug")
                rs.ObjectColor(sphere, (255, 100, 100))  # 赤 (red)

    # ステップ3: パイプジオメトリ生成 (Step 3: Generate pipe geometry)
    if params['verbose']:
        Rhino.RhinoApp.WriteLine("\n[Step 3] Generating pipe geometry...")

    pipe_meshes = []

    # デバッグ: 最初の数エッジの半径情報を出力
    if params['verbose'] and len(graph.edges) > 0:
        Rhino.RhinoApp.WriteLine("  Sample edges (first 3):")
        for i, edge in enumerate(graph.edges[:3]):
            Rhino.RhinoApp.WriteLine("    Edge {}: start_r={:.2f}mm, end_r={:.2f}mm, length={:.1f}mm".format(
                i,
                edge.start_node.radius if edge.start_node else 0,
                edge.end_node.radius if edge.end_node else 0,
                edge.length
            ))

    for i, edge in enumerate(graph.edges):
        if params['verbose'] and (i % 10 == 0 or i == len(graph.edges) - 1):
            Rhino.RhinoApp.WriteLine("  Progress: {}/{}".format(i + 1, len(graph.edges)))

        mesh = generate_pipe_mesh_for_edge(edge, graph, params, debug_index=i)
        if mesh:
            pipe_meshes.append(mesh)

    # ステップ4: レイヤー整理 (Step 4: Organize output)
    if params['verbose']:
        Rhino.RhinoApp.WriteLine("\n[Step 4] Organizing output...")

    # レイヤーを作成 (create layer)
    ensure_layer(params['layer_name'])

    for mesh in pipe_meshes:
        rs.ObjectLayer(mesh, params['layer_name'])

    # オプション: メッシュを結合 (optional: merge meshes)
    if params['merge_meshes'] and len(pipe_meshes) > 1:
        if params['verbose']:
            Rhino.RhinoApp.WriteLine("  Merging {} meshes...".format(len(pipe_meshes)))

        merged = rs.JoinMeshes(pipe_meshes, delete_input=True)
        if merged:
            pipe_meshes = [merged]

    # 表示を更新 (update display)
    rs.ZoomExtents()
    rs.Redraw()

    return pipe_meshes


def run():
    """
    メインエントリーポイント（対話的UI）
    Main entry point for script (interactive UI)
    """
    Rhino.RhinoApp.WriteLine("\n" + "="*70)
    Rhino.RhinoApp.WriteLine("Variable-Radius Pipe Generator - 可変半径パイプ生成")
    Rhino.RhinoApp.WriteLine("="*70)

    # ステップ0: 曲線選択 (Step 0: Select curves)
    Rhino.RhinoApp.WriteLine("\n[Step 0] Select curves for pipe generation")
    curve_ids = rs.GetObjects(
        "Select curves for pipe generation",
        filter=4,  # Curve filter
        preselect=True
    )

    if not curve_ids:
        Rhino.RhinoApp.WriteLine("No curves selected. Exiting.")
        return

    Rhino.RhinoApp.WriteLine("  Selected {} curves".format(len(curve_ids)))

    # パラメータ設定（デフォルトを使用）(use default parameters)
    params = DEFAULT_PARAMS.copy()

    # パイプを生成 (generate pipes)
    pipe_meshes = generate_pipes(curve_ids, params)

    # サマリー (summary)
    Rhino.RhinoApp.WriteLine("\n" + "="*70)
    Rhino.RhinoApp.WriteLine("Pipe generation COMPLETE!")
    Rhino.RhinoApp.WriteLine("="*70)
    Rhino.RhinoApp.WriteLine("  Pipes created: {}".format(len(pipe_meshes)))
    Rhino.RhinoApp.WriteLine("  Layer: {}".format(params['layer_name']))
    Rhino.RhinoApp.WriteLine("  Base radius: {}mm".format(params['base_radius']))
    Rhino.RhinoApp.WriteLine("  Node scaling: {}".format(params['node_scaling_factor']))
    Rhino.RhinoApp.WriteLine("  Interpolation: {}".format(params['interpolation_type']))
    Rhino.RhinoApp.WriteLine("="*70)


# ===== 実行 (Execution) =====

if __name__ == '__main__':
    run()
