# -*- coding: utf-8 -*-

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import math

# -------------------------
# utils
# -------------------------
def unitize(v):
    v2 = Rhino.Geometry.Vector3d(v)
    if v2.IsTiny(sc.doc.ModelAbsoluteTolerance):
        return None
    v2.Unitize()
    return v2

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
    """小分けUnion→段階統合"""
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

# -------------------------
# panel plane & boundary
# -------------------------
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
    """外周閉曲線を取得"""
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

# -------------------------
# region clipping (centerline)
# -------------------------
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
    """WorldXY上の直線を、閉曲線regionの内側区間だけに切り出す（中点内外判定）"""
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

# -------------------------
# geometry creation
# -------------------------
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

    x = unitize(Rhino.Geometry.Vector3d.CrossProduct(n, dirv))  # 見付方向（面内で線分に直交）
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

def extrude_xy_curve_solid(crv_xy, height, tol):
    """WorldXY上の閉曲線を +Z に押し出してソリッド化"""
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
    return None

def make_panel_cutter(boundary_xy, panel_plane, to_3d, depth, depth_side, tol):
    """
    境界で“ギリギリ”に切るためのカッターソリッドを作る
    - WorldXYで boundary を +Z に depth 押し出し
    - パネル平面へTransform
    - depth_sideに合わせて位置調整
    """
    cutter_xy = extrude_xy_curve_solid(boundary_xy, depth, tol)
    if cutter_xy is None:
        return None

    cutter_xy.Transform(to_3d)

    n = unitize(panel_plane.Normal)
    if n is None:
        return cutter_xy

    move = Rhino.Geometry.Vector3d(0, 0, 0)
    if depth_side == 0:      # center
        move = (-0.5 * depth) * n
    elif depth_side == -1:   # negative側へ全部
        move = (-1.0 * depth) * n
    # positive は移動なし

    if not move.IsTiny(tol):
        cutter_xy.Transform(Rhino.Geometry.Transform.Translation(move))

    return cutter_xy

def ensure_layer(name):
    idx = sc.doc.Layers.FindName(name)
    if idx >= 0:
        return idx
    layer = Rhino.DocObjects.Layer()
    layer.Name = name
    return sc.doc.Layers.Add(layer)

# -------------------------
# main
# -------------------------
def main():
    tol = sc.doc.ModelAbsoluteTolerance

    ids = rs.GetObjects("PlanarSrfで作った平面サーフェスを選択", rs.filter.surface | rs.filter.polysurface, preselect=True)
    if not ids:
        return

    s = rs.GetReal("菱形セル（正三角形2つ）の辺長 s", 20.0, 1.0)
    if s is None:
        return

    width = rs.GetReal("角材 見付幅 w", 1.0, 0.1)
    if width is None:
        return

    depth = rs.GetReal("角材 見込み d（面法線方向）", 1.0, 0.1)
    if depth is None:
        return

    side_str = rs.GetString("見込みの配置（center / positive / negative）", "center", ["center", "positive", "negative"])
    if side_str is None:
        return
    depth_side = 0
    if side_str == "positive":
        depth_side = 1
    elif side_str == "negative":
        depth_side = -1

    # ここを True にしておくと、境界でピタッとトリムされます（おすすめ）
    trim_flush_to_surface = True

    # 60°菱形格子：平行線間隔 step = s*sqrt(3)/2
    step = s * (math.sqrt(3.0) / 2.0)

    layer_index = ensure_layer("GRID_ONLY")
    attr = Rhino.DocObjects.ObjectAttributes()
    attr.LayerIndex = layer_index

    rs.EnableRedraw(False)

    # 2D格子方向（WorldXY）
    dA = Rhino.Geometry.Vector3d(1, 0, 0)  # 0°
    dB = Rhino.Geometry.Vector3d(0.5, math.sqrt(3.0)/2.0, 0)  # 60°
    dA.Unitize(); dB.Unitize()

    # それぞれの法線（2D）
    nA = Rhino.Geometry.Vector3d(-dA.Y, dA.X, 0)
    nB = Rhino.Geometry.Vector3d(-dB.Y, dB.X, 0)
    nA.Unitize(); nB.Unitize()

    panels_done = 0
    panels_union_failed = 0

    # Union成功率を上げる“ほんの少しの食い込み”
    # mm運用なら 0.1〜1.0 くらいが効くことが多い（必要なければ 0.0）
    eps = 0.0

    for obj_id in ids:
        brep = rs.coercebrep(obj_id)
        if brep is None:
            continue

        panel_plane = build_panel_plane(brep, tol)
        if panel_plane is None:
            continue

        boundary = get_outer_boundary(brep, tol)
        if boundary is None:
            continue

        # flatten transforms
        to_xy = Rhino.Geometry.Transform.PlaneToPlane(panel_plane, Rhino.Geometry.Plane.WorldXY)
        to_3d = Rhino.Geometry.Transform.PlaneToPlane(Rhino.Geometry.Plane.WorldXY, panel_plane)

        b2 = boundary.DuplicateCurve()
        b2.Transform(to_xy)          # WorldXY上の境界（region）
        region = b2                 # ★オフセットなし = “ぎりぎりまで”

        bb = region.GetBoundingBox(True)
        if not bb.IsValid:
            continue

        diag = (bb.Max - bb.Min).Length
        big = diag + 4.0 * step

        # 面ごと部材
        panel_parts = []

        # A方向（0°）
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
                box = make_box_for_segment(q0, q1, panel_plane.Normal, width + eps, depth + eps, depth_side, tol)
                if box:
                    panel_parts.append(box)
            k += step

        # B方向（60°）
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
                box = make_box_for_segment(q0, q1, panel_plane.Normal, width + eps, depth + eps, depth_side, tol)
                if box:
                    panel_parts.append(box)
            k += step

        # 面ごとUnion
        unioned = boolean_union_breps(panel_parts, tol, batch=30) if panel_parts else None
        if unioned is None:
            panels_union_failed += 1
            # 保険：バラで追加
            for b in panel_parts:
                if b:
                    sc.doc.Objects.AddBrep(b, attr)
            panels_done += 1
            continue

        # 境界で“ぎりぎり”に切る（おすすめ）
        if trim_flush_to_surface:
            cutter = make_panel_cutter(b2, panel_plane, to_3d, depth, depth_side, tol)
            if cutter:
                inter = Rhino.Geometry.Brep.CreateBooleanIntersection([unioned], [cutter], tol)
                cut = pick_largest_brep(inter)
                if cut:
                    sc.doc.Objects.AddBrep(cut, attr)
                else:
                    # Intersection失敗時はそのまま出す
                    sc.doc.Objects.AddBrep(unioned, attr)
            else:
                sc.doc.Objects.AddBrep(unioned, attr)
        else:
            sc.doc.Objects.AddBrep(unioned, attr)

        panels_done += 1

    rs.EnableRedraw(True)
    sc.doc.Views.Redraw()
    print("Done. Panels: {}, union_failed: {}".format(panels_done, panels_union_failed))

if __name__ == "__main__":
    main()
