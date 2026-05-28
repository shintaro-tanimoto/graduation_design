# -*- coding: utf-8 -*-
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import math

# ============================================================
# Utils
# ============================================================
def unitize(v):
    v2 = Rhino.Geometry.Vector3d(v)
    if v2.IsTiny(sc.doc.ModelAbsoluteTolerance):
        return None
    v2.Unitize()
    return v2

def closed_curve_area(crv):
    if crv is None or not crv.IsClosed:
        return None
    amp = Rhino.Geometry.AreaMassProperties.Compute(crv)
    return amp.Area if amp else None

def pick_largest_brep(breps):
    if not breps:
        return None
    best = None
    best_v = -1.0
    for b in breps:
        if b is None:
            continue
        vmp = Rhino.Geometry.VolumeMassProperties.Compute(b)
        v = vmp.Volume if vmp else 0.0
        if v > best_v:
            best_v = v
            best = b
    return best

def try_repair_solid(brep, tol):
    if brep is None:
        return None
    b = brep.DuplicateBrep()
    try:
        b.RebuildEdges(tol, True, True)
    except:
        pass
    try:
        b.Compact()
    except:
        pass
    return b

def boolean_union_breps(breps, tol, batch=30):
    """小分けUnion→段階統合（grid側用）"""
    work = []
    for b in breps:
        if b is None:
            continue
        work.append(try_repair_solid(b, tol))

    if len(work) == 0:
        return None
    if len(work) == 1:
        return work[0]

    merged = []
    i = 0
    while i < len(work):
        chunk = work[i:i+batch]
        i += batch

        res = Rhino.Geometry.Brep.CreateBooleanUnion(chunk, tol)
        if res and len(res) > 0:
            merged.extend(res)
        else:
            acc = None
            for b in chunk:
                if acc is None:
                    acc = b
                    continue
                r = Rhino.Geometry.Brep.CreateBooleanUnion([acc, b], tol)
                if r and len(r) > 0:
                    acc = pick_largest_brep(r)
                else:
                    merged.append(b)
            if acc is not None:
                merged.append(acc)

    if len(merged) == 1:
        return merged[0]

    final = Rhino.Geometry.Brep.CreateBooleanUnion(merged, tol)
    if final and len(final) > 0:
        return pick_largest_brep(final)

    return pick_largest_brep(merged)

# ============================================================
# Layer helpers (NEW)
# ============================================================
def ensure_layer(name):
    idx = sc.doc.Layers.FindName(name)
    if idx >= 0:
        return idx
    layer = Rhino.DocObjects.Layer()
    layer.Name = name
    return sc.doc.Layers.Add(layer)

def ensure_sublayer(parent_name, child_name):
    """親レイヤーの下に子レイヤーを作る（存在すればそれを返す）"""
    p_idx = ensure_layer(parent_name)
    parent_id = sc.doc.Layers[p_idx].Id

    # 既存チェック：同じParentLayerId & Name
    for i in range(sc.doc.Layers.Count):
        ly = sc.doc.Layers[i]
        if ly is None or ly.IsDeleted:
            continue
        if ly.ParentLayerId == parent_id and ly.Name == child_name:
            return i

    # 新規作成
    child = Rhino.DocObjects.Layer()
    child.Name = child_name
    child.ParentLayerId = parent_id
    return sc.doc.Layers.Add(child)

def add_brep(brep, layer_idx, group_idx=None):
    """Brepをdocへ追加（Layer + Groupを付与）"""
    if brep is None:
        return None
    attr = Rhino.DocObjects.ObjectAttributes()
    attr.LayerIndex = layer_idx
    if group_idx is not None and group_idx >= 0:
        attr.AddToGroup(group_idx)
    return sc.doc.Objects.AddBrep(brep, attr)

# ============================================================
# Panel plane & boundary
# ============================================================
def build_panel_plane(brep, tol):
    """Planar Brepから、格子向きを揃えたローカル平面（Y軸=WorldZ投影）を作る"""
    if brep is None or brep.Faces.Count == 0:
        return None
    face = brep.Faces[0]

    rc, plane = face.TryGetPlane(tol)
    if not rc:
        du = face.Domain(0); dv = face.Domain(1)
        u = 0.5 * (du.T0 + du.T1)
        v = 0.5 * (dv.T0 + dv.T1)
        rc, plane = face.FrameAt(u, v)
        if not rc:
            return None

    amp = Rhino.Geometry.AreaMassProperties.Compute(brep)
    origin = amp.Centroid if amp else plane.Origin

    n = unitize(plane.Normal)
    if n is None:
        return None

    worldZ = Rhino.Geometry.Vector3d(0, 0, 1)
    vproj = worldZ - (worldZ * n) * n
    if vproj.IsTiny(tol):
        worldX = Rhino.Geometry.Vector3d(1, 0, 0)
        vproj = worldX - (worldX * n) * n

    yAxis = unitize(vproj)
    if yAxis is None:
        return None

    xAxis = unitize(Rhino.Geometry.Vector3d.CrossProduct(yAxis, n))
    if xAxis is None:
        return None

    return Rhino.Geometry.Plane(origin, xAxis, yAxis)

def get_outer_boundary(brep, tol):
    """外周閉曲線（最大の閉曲線）を取得"""
    crvs = brep.DuplicateNakedEdgeCurves(True, False)
    if not crvs or len(crvs) == 0:
        crvs = brep.DuplicateEdgeCurves()

    joined = Rhino.Geometry.Curve.JoinCurves(crvs, tol)
    if not joined:
        return None

    best = None
    best_len = -1.0
    for c in joined:
        if c and c.IsClosed:
            L = c.GetLength()
            if L > best_len:
                best_len = L
                best = c
    return best

# ============================================================
# Grid helpers (clip)
# ============================================================
def curve_contains_xy(region, pt, tol):
    pc = region.Contains(pt, Rhino.Geometry.Plane.WorldXY, tol)
    return pc != Rhino.Geometry.PointContainment.Outside

def unique_sorted_params(params, tol):
    params = sorted(params)
    uniq = []
    for t in params:
        if not uniq or abs(t - uniq[-1]) > tol:
            uniq.append(t)
    return uniq

def clip_line_to_region_xy(line, region, tol):
    """WorldXY上の直線を、閉曲線regionの内側区間だけに切り出す"""
    if line is None or region is None:
        return []

    x = Rhino.Geometry.Intersect.Intersection.CurveCurve(line, region, tol, tol)
    ts = []
    if x:
        for ev in x:
            if ev and ev.IsPoint:
                ts.append(ev.ParameterA)

    if not ts:
        mid = line.PointAtNormalizedLength(0.5)
        return [line] if curve_contains_xy(region, mid, tol) else []

    dom = line.Domain
    ts2 = []
    for t in ts:
        if dom.T0 + tol < t < dom.T1 - tol:
            ts2.append(t)
    ts2 = unique_sorted_params(ts2, tol)

    if not ts2:
        mid = line.PointAtNormalizedLength(0.5)
        return [line] if curve_contains_xy(region, mid, tol) else []

    pieces = line.Split(ts2)
    if not pieces:
        return []

    inside = []
    for seg in pieces:
        if seg is None:
            continue
        mp = seg.PointAtNormalizedLength(0.5)
        if curve_contains_xy(region, mp, tol):
            inside.append(seg)
    return inside

def projected_range_on_bbox(bb, n2):
    corners = [
        Rhino.Geometry.Point3d(bb.Min.X, bb.Min.Y, 0),
        Rhino.Geometry.Point3d(bb.Min.X, bb.Max.Y, 0),
        Rhino.Geometry.Point3d(bb.Max.X, bb.Min.Y, 0),
        Rhino.Geometry.Point3d(bb.Max.X, bb.Max.Y, 0),
    ]
    vals = [n2.X*p.X + n2.Y*p.Y for p in corners]
    return min(vals), max(vals)

def make_box_for_segment(p0, p1, panel_normal, width, depth, depth_side, tol):
    """線分に沿った角材Box（solid）"""
    v = p1 - p0
    L = v.Length
    if L < tol:
        return None

    dirv = unitize(v)
    n = unitize(panel_normal)
    if dirv is None or n is None:
        return None

    x = unitize(Rhino.Geometry.Vector3d.CrossProduct(n, dirv))  # 面内で線分に直交
    if x is None:
        return None

    mid = Rhino.Geometry.Point3d(
        0.5*(p0.X+p1.X),
        0.5*(p0.Y+p1.Y),
        0.5*(p0.Z+p1.Z)
    )

    if depth_side != 0:
        mid = mid + (0.5 * depth * float(depth_side)) * n

    box_plane = Rhino.Geometry.Plane(mid, x, n)  # X=見付, Y=法線, Z=線分方向

    ix = Rhino.Geometry.Interval(-0.5*width, 0.5*width)
    iy = Rhino.Geometry.Interval(-0.5*depth, 0.5*depth)
    iz = Rhino.Geometry.Interval(-0.5*L, 0.5*L)

    box = Rhino.Geometry.Box(box_plane, ix, iy, iz)
    return box.ToBrep() if box.IsValid else None

# ============================================================
# Frame helpers (offset + extrude + boolean diff)
# ============================================================
def offset_pick_inward(curve_xy, dist, tol):
    """両側オフセットして、面積が小さい方を採用（内側）"""
    if curve_xy is None or not curve_xy.IsClosed:
        return None
    corner = Rhino.Geometry.CurveOffsetCornerStyle.Sharp
    cands = []
    for d in (dist, -dist):
        res = curve_xy.Offset(Rhino.Geometry.Plane.WorldXY, d, tol, corner)
        if res:
            for c in res:
                if c and c.IsClosed:
                    a = closed_curve_area(c)
                    if a is not None and a > tol:
                        cands.append((a, c))
    if not cands:
        return None
    cands.sort(key=lambda x: x[0])
    return cands[0][1]

def offset_pick_outward(curve_xy, dist, tol):
    """両側オフセットして、面積が大きい方を採用（外側）"""
    if curve_xy is None or not curve_xy.IsClosed:
        return None
    corner = Rhino.Geometry.CurveOffsetCornerStyle.Sharp
    cands = []
    for d in (dist, -dist):
        res = curve_xy.Offset(Rhino.Geometry.Plane.WorldXY, d, tol, corner)
        if res:
            for c in res:
                if c and c.IsClosed:
                    a = closed_curve_area(c)
                    if a is not None and a > tol:
                        cands.append((a, c))
    if not cands:
        return None
    cands.sort(key=lambda x: x[0], reverse=True)
    return cands[0][1]

def extrude_xy_curve_solid(crv_xy, height, tol):
    """WorldXY上の閉曲線を +Z 方向に押し出してソリッド化"""
    if crv_xy is None or (not crv_xy.IsClosed):
        return None
    ext = Rhino.Geometry.Extrusion.Create(crv_xy, height, True)
    if ext:
        brep = ext.ToBrep(True)
        if brep and (not brep.IsSolid):
            brep2 = brep.CapPlanarHoles(tol)
            if brep2:
                brep = brep2
        return brep
    srf = Rhino.Geometry.Surface.CreateExtrusion(crv_xy, Rhino.Geometry.Vector3d(0,0,height))
    if not srf:
        return None
    brep = srf.ToBrep()
    if brep and (not brep.IsSolid):
        brep2 = brep.CapPlanarHoles(tol)
        if brep2:
            brep = brep2
    return brep

def make_frame_ring_on_panel(boundary_xy, panel_plane, to_3d, frame_w, depth, depth_side, frame_pos, tol):
    """外枠リング（XYで作って→パネルへ戻す）"""
    if frame_pos == "inside":
        outer_xy = boundary_xy
        inner_xy = offset_pick_inward(boundary_xy, frame_w, tol)
    elif frame_pos == "outside":
        inner_xy = boundary_xy
        outer_xy = offset_pick_outward(boundary_xy, frame_w, tol)
    else:  # center
        outer_xy = offset_pick_outward(boundary_xy, 0.5*frame_w, tol)
        inner_xy = offset_pick_inward(boundary_xy, 0.5*frame_w, tol)

    if outer_xy is None or inner_xy is None:
        return None

    outer_sol = extrude_xy_curve_solid(outer_xy, depth, tol)
    inner_sol = extrude_xy_curve_solid(inner_xy, depth, tol)
    if outer_sol is None or inner_sol is None:
        return None

    ring_list = Rhino.Geometry.Brep.CreateBooleanDifference(outer_sol, inner_sol, tol)
    ring_xy = pick_largest_brep(ring_list)
    if ring_xy is None:
        return None

    ring_xy.Transform(to_3d)

    n = unitize(panel_plane.Normal)
    if n:
        move = Rhino.Geometry.Vector3d(0,0,0)
        if depth_side == 0:
            move = (-0.5*depth) * n
        elif depth_side == -1:
            move = (-1.0*depth) * n
        if not move.IsTiny(tol):
            ring_xy.Transform(Rhino.Geometry.Transform.Translation(move))

    return ring_xy

# ============================================================
# Main
# ============================================================
def main():
    tol = sc.doc.ModelAbsoluteTolerance

    ids = rs.GetObjects(
        "PlanarSrf（平面サーフェス）を選択：外枠＋格子を作り、PANEL_OUT::PANEL_### に格納",
        rs.filter.surface | rs.filter.polysurface, preselect=True
    )
    if not ids:
        return

    parent_layer = "PANEL_OUT"  # ★新しい親レイヤー

    # params
    s = rs.GetReal("格子：菱形セルの辺長 s", 20.0, 1.0)
    if s is None: return

    grid_w = rs.GetReal("格子：角材 見付幅 w", 1.0, 0.1)
    if grid_w is None: return

    frame_w = rs.GetReal("外枠：幅（面内方向）", 40.0, 0.1)
    if frame_w is None: return

    depth = rs.GetReal("共通：見込み d（面法線方向）", 60.0, 0.1)
    if depth is None: return

    side_str = rs.GetString("見込みの配置（center / positive / negative）",
                            "center", ["center", "positive", "negative"])
    if side_str is None: return
    depth_side = 0
    if side_str == "positive": depth_side = 1
    elif side_str == "negative": depth_side = -1

    frame_pos = rs.GetString("外枠の位置（inside / center / outside）",
                             "inside", ["inside", "center", "outside"])
    if frame_pos is None: return

    eps = rs.GetReal("Union安定用の微小増し eps（0でOK）", 0.0, 0.0)
    if eps is None: return

    step = s * (math.sqrt(3.0) / 2.0)

    rs.EnableRedraw(False)

    # grid directions in XY
    dA = Rhino.Geometry.Vector3d(1, 0, 0)
    dB = Rhino.Geometry.Vector3d(0.5, math.sqrt(3.0)/2.0, 0)
    dA.Unitize(); dB.Unitize()

    nA = Rhino.Geometry.Vector3d(-dA.Y, dA.X, 0)
    nB = Rhino.Geometry.Vector3d(-dB.Y, dB.X, 0)
    nA.Unitize(); nB.Unitize()

    for i, obj_id in enumerate(ids):
        brep = rs.coercebrep(obj_id)
        if brep is None:
            continue

        panel_plane = build_panel_plane(brep, tol)
        if panel_plane is None:
            continue

        boundary = get_outer_boundary(brep, tol)
        if boundary is None:
            continue

        # transforms
        to_xy = Rhino.Geometry.Transform.PlaneToPlane(panel_plane, Rhino.Geometry.Plane.WorldXY)
        to_3d = Rhino.Geometry.Transform.PlaneToPlane(Rhino.Geometry.Plane.WorldXY, panel_plane)

        # boundary in XY
        b2 = boundary.DuplicateCurve()
        b2.Transform(to_xy)

        # ---- Group name / Layer ----
        gname = "PANEL_{:03d}".format(i+1)
        group_idx = sc.doc.Groups.Add(gname)

        sub_layer_idx = ensure_sublayer(parent_layer, gname)  # ★ここでサブレイヤー作成

        # ---- FRAME (ring) ----
        ring = make_frame_ring_on_panel(b2, panel_plane, to_3d, frame_w, depth, depth_side, frame_pos, tol)
        if ring:
            add_brep(ring, sub_layer_idx, group_idx)

        # ---- GRID ----
        # 外枠の「中心線」まで格子を伸ばすためのクリップ領域を作る
        if frame_pos == "inside":
            # 外枠が内側に入る → 中心線は外周から frame_w/2 だけ内側
            region = offset_pick_inward(b2, 0.5 * frame_w, tol) or b2
        elif frame_pos == "outside":
            # 外枠が外側に出る → 中心線は外周から frame_w/2 だけ外側
            region = offset_pick_outward(b2, 0.5 * frame_w, tol) or b2
        else:  # "center"
            # 外枠中心＝外周曲線そのもの
            region = b2

        bb = region.GetBoundingBox(True)
        if not bb.IsValid:
            continue

        diag = (bb.Max - bb.Min).Length
        big = diag + 4.0 * step

        panel_parts = []

        # A direction
        minA, maxA = projected_range_on_bbox(bb, nA)
        k = math.floor(minA / step) * step
        while k <= maxA + tol:
            base = Rhino.Geometry.Point3d(nA.X * k, nA.Y * k, 0)
            pA = base + Rhino.Geometry.Vector3d(-big*dA.X, -big*dA.Y, 0)
            pB = base + Rhino.Geometry.Vector3d(+big*dA.X, +big*dA.Y, 0)
            line = Rhino.Geometry.LineCurve(pA, pB)

            segs = clip_line_to_region_xy(line, region, tol)
            for sgm in segs:
                q0 = sgm.PointAtStart; q1 = sgm.PointAtEnd
                q0.Transform(to_3d); q1.Transform(to_3d)
                box = make_box_for_segment(q0, q1, panel_plane.Normal,
                                           grid_w + eps, depth + eps, depth_side, tol)
                if box:
                    panel_parts.append(box)
            k += step

        # B direction
        minB, maxB = projected_range_on_bbox(bb, nB)
        k = math.floor(minB / step) * step
        while k <= maxB + tol:
            base = Rhino.Geometry.Point3d(nB.X * k, nB.Y * k, 0)
            pA = base + Rhino.Geometry.Vector3d(-big*dB.X, -big*dB.Y, 0)
            pB = base + Rhino.Geometry.Vector3d(+big*dB.X, +big*dB.Y, 0)
            line = Rhino.Geometry.LineCurve(pA, pB)

            segs = clip_line_to_region_xy(line, region, tol)
            for sgm in segs:
                q0 = sgm.PointAtStart; q1 = sgm.PointAtEnd
                q0.Transform(to_3d); q1.Transform(to_3d)
                box = make_box_for_segment(q0, q1, panel_plane.Normal,
                                           grid_w + eps, depth + eps, depth_side, tol)
                if box:
                    panel_parts.append(box)
            k += step

        unioned = boolean_union_breps(panel_parts, tol, batch=30) if panel_parts else None

        if unioned:
            add_brep(unioned, sub_layer_idx, group_idx)
        else:
            # union失敗ならバラで入れる（同じサブレイヤー＆グループ）
            for b in panel_parts:
                if b:
                    add_brep(b, sub_layer_idx, group_idx)

    rs.EnableRedraw(True)
    sc.doc.Views.Redraw()
    print("Done. Created PANEL_OUT sublayers per panel group.")

if __name__ == "__main__":
    main()
