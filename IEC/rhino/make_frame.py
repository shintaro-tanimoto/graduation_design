# -*- coding: utf-8 -*-

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

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

def offset_pick_inward(curve_xy, dist, tol):
    """両側オフセットして、面積が小さい方を採用（凸形状の内側に強い）"""
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
    cands.sort(key=lambda x: x[0])  # small area
    return cands[0][1]

def offset_pick_outward(curve_xy, dist, tol):
    """両側オフセットして、面積が大きい方を採用（凸形状の外側に強い）"""
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
    cands.sort(key=lambda x: x[0], reverse=True)  # large area
    return cands[0][1]

def build_panel_plane(brep, tol):
    """平面Brepからローカル平面（Y軸=WorldZ投影）を作る"""
    if brep is None or brep.Faces.Count == 0:
        return None
    face = brep.Faces[0]

    rc, plane = face.TryGetPlane(tol)
    if not rc:
        du = face.Domain(0); dv = face.Domain(1)
        u = 0.5*(du.T0 + du.T1)
        v = 0.5*(dv.T0 + dv.T1)
        rc, plane = face.FrameAt(u, v)
        if not rc:
            return None

    amp = Rhino.Geometry.AreaMassProperties.Compute(brep)
    origin = amp.Centroid if amp else plane.Origin

    n = unitize(plane.Normal)
    if n is None:
        return None

    worldZ = Rhino.Geometry.Vector3d(0,0,1)
    vproj = worldZ - (worldZ*n)*n
    if vproj.IsTiny(tol):
        worldX = Rhino.Geometry.Vector3d(1,0,0)
        vproj = worldX - (worldX*n)*n

    y = unitize(vproj)
    if y is None:
        return None
    x = unitize(Rhino.Geometry.Vector3d.CrossProduct(y, n))
    if x is None:
        return None

    return Rhino.Geometry.Plane(origin, x, y)

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

def extrude_xy_curve_solid(crv_xy, height, tol):
    """WorldXY上の閉曲線を +Z 方向に押し出してソリッド化"""
    if crv_xy is None or (not crv_xy.IsClosed):
        return None
    ext = Rhino.Geometry.Extrusion.Create(crv_xy, height, True)  # cap=True
    if ext:
        brep = ext.ToBrep(True)
        if brep and (not brep.IsSolid):
            brep2 = brep.CapPlanarHoles(tol)
            if brep2:
                brep = brep2
        return brep
    # fallback
    srf = Rhino.Geometry.Surface.CreateExtrusion(crv_xy, Rhino.Geometry.Vector3d(0,0,height))
    if not srf:
        return None
    brep = srf.ToBrep()
    if brep and (not brep.IsSolid):
        brep2 = brep.CapPlanarHoles(tol)
        if brep2:
            brep = brep2
    return brep

def ensure_layer(name):
    idx = sc.doc.Layers.FindName(name)
    if idx >= 0:
        return idx
    layer = Rhino.DocObjects.Layer()
    layer.Name = name
    return sc.doc.Layers.Add(layer)

def main():
    tol = sc.doc.ModelAbsoluteTolerance

    ids = rs.GetObjects("PlanarSrfで作った平面サーフェスを選択（外枠だけ作成）",
                        rs.filter.surface | rs.filter.polysurface, preselect=True)
    if not ids:
        return

    frame_w = rs.GetReal("外枠の幅（面内方向）", 40.0, 0.1)
    if frame_w is None:
        return

    depth = rs.GetReal("外枠の見込み（面法線方向）", 60.0, 0.1)
    if depth is None:
        return

    side_str = rs.GetString("見込みの配置（center / positive / negative）",
                            "center", ["center", "positive", "negative"])
    if side_str is None:
        return
    depth_side = 0
    if side_str == "positive":
        depth_side = 1
    elif side_str == "negative":
        depth_side = -1

    frame_pos = rs.GetString("外枠の位置（inside / center / outside）",
                             "inside", ["inside", "center", "outside"])
    if frame_pos is None:
        return

    layer_index = ensure_layer("PERIM_nt_FRAME")
    attr = Rhino.DocObjects.ObjectAttributes()
    attr.LayerIndex = layer_index

    rs.EnableRedraw(False)

    made = 0
    failed = 0

    for obj_id in ids:
        brep = rs.coercebrep(obj_id)
        if brep is None:
            failed += 1
            continue

        panel_plane = build_panel_plane(brep, tol)
        if panel_plane is None:
            failed += 1
            continue

        boundary = get_outer_boundary(brep, tol)
        if boundary is None:
            failed += 1
            continue

        # XYに寝かせる
        to_xy = Rhino.Geometry.Transform.PlaneToPlane(panel_plane, Rhino.Geometry.Plane.WorldXY)
        to_3d = Rhino.Geometry.Transform.PlaneToPlane(Rhino.Geometry.Plane.WorldXY, panel_plane)

        b2 = boundary.DuplicateCurve()
        b2.Transform(to_xy)

        # outer / inner の2D曲線を作る
        if frame_pos == "inside":
            outer_xy = b2
            inner_xy = offset_pick_inward(b2, frame_w, tol)
        elif frame_pos == "outside":
            inner_xy = b2
            outer_xy = offset_pick_outward(b2, frame_w, tol)
        else:  # center
            outer_xy = offset_pick_outward(b2, 0.5*frame_w, tol)
            inner_xy = offset_pick_inward(b2, 0.5*frame_w, tol)

        if outer_xy is None or inner_xy is None:
            failed += 1
            continue

        # XYで押し出し（+Z）
        outer_sol = extrude_xy_curve_solid(outer_xy, depth, tol)
        inner_sol = extrude_xy_curve_solid(inner_xy, depth, tol)
        if outer_sol is None or inner_sol is None:
            failed += 1
            continue

        # outer - inner = リング
        ring_list = Rhino.Geometry.Brep.CreateBooleanDifference(outer_sol, inner_sol, tol)
        ring_xy = pick_largest_brep(ring_list)
        if ring_xy is None:
            failed += 1
            continue

        # 元のパネルへ戻す
        ring_xy.Transform(to_3d)

        # 見込み位置（center/negative）調整
        n = unitize(panel_plane.Normal)
        if n:
            move = Rhino.Geometry.Vector3d(0,0,0)
            if depth_side == 0:
                move = (-0.5*depth) * n
            elif depth_side == -1:
                move = (-1.0*depth) * n
            if not move.IsTiny(tol):
                ring_xy.Transform(Rhino.Geometry.Transform.Translation(move))

        sc.doc.Objects.AddBrep(ring_xy, attr)
        made += 1

    rs.EnableRedraw(True)
    sc.doc.Views.Redraw()

    print("Done. made: {}, failed: {}".format(made, failed))

if __name__ == "__main__":
    main()
