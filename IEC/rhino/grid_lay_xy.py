# -*- coding: utf-8 -*-

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import math

# -------------------------
# basic utils
# -------------------------
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

def try_repair(brep, tol):
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

def union_list(breps, tol, batch=40):
    """小分けUnion。戻りは list[Brep]（1個とは限らない）"""
    work = [try_repair(b, tol) for b in breps if b is not None]
    work = [b for b in work if b is not None]
    if not work:
        return []
    if len(work) == 1:
        return work

    merged = []
    i = 0
    while i < len(work):
        chunk = work[i:i+batch]
        i += batch
        res = Rhino.Geometry.Brep.CreateBooleanUnion(chunk, tol)
        if res and len(res) > 0:
            merged.extend(res)
        else:
            # chunkがダメなら分割のまま残す（後工程でclipするので致命傷ではない）
            merged.extend(chunk)

    # もう一回まとめる
    if len(merged) <= 1:
        return merged
    res2 = Rhino.Geometry.Brep.CreateBooleanUnion(merged, tol)
    return res2 if (res2 and len(res2) > 0) else merged

def intersect_planar(a_list, b_list, tol):
    """BrepのBooleanIntersection（planar同士でもOK）。戻り list[Brep]"""
    if not a_list or not b_list:
        return []
    res = Rhino.Geometry.Brep.CreateBooleanIntersection(a_list, b_list, tol)
    return res if (res and len(res) > 0) else []

# -------------------------
# plane & boundary
# -------------------------
def build_panel_plane(brep, tol):
    """Planar Brepから安定した平面（Y軸=WorldZ投影）を作る"""
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
    """外周閉曲線を取得（最大閉曲線）"""
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
# offset pick (for convex-ish)
# -------------------------
def offset_pick_inward(curve_xy, dist, tol):
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
    cands.sort(key=lambda x: x[0])  # smaller area
    return cands[0][1]

def offset_pick_outward(curve_xy, dist, tol):
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
    cands.sort(key=lambda x: x[0], reverse=True)  # larger area
    return cands[0][1]

# -*- coding: utf-8 -*-

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import math

# -------------------------
# basic utils
# -------------------------
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

def try_repair(brep, tol):
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

def union_list(breps, tol, batch=40):
    """小分けUnion。戻りは list[Brep]（1個とは限らない）"""
    work = [try_repair(b, tol) for b in breps if b is not None]
    work = [b for b in work if b is not None]
    if not work:
        return []
    if len(work) == 1:
        return work

    merged = []
    i = 0
    while i < len(work):
        chunk = work[i:i+batch]
        i += batch
        res = Rhino.Geometry.Brep.CreateBooleanUnion(chunk, tol)
        if res and len(res) > 0:
            merged.extend(res)
        else:
            merged.extend(chunk)

    if len(merged) <= 1:
        return merged
    res2 = Rhino.Geometry.Brep.CreateBooleanUnion(merged, tol)
    return res2 if (res2 and len(res2) > 0) else merged

# -------------------------
# plane & boundary
# -------------------------
def build_panel_plane(brep, tol):
    """Planar Brepから安定した平面（Y軸=WorldZ投影）を作る"""
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
    """外周閉曲線を取得（最大閉曲線）"""
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
# offset pick (convex-ish)
# -------------------------
def offset_pick_inward(curve_xy, dist, tol):
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
    cands.sort(key=lambda x: x[0])  # smaller area
    return cands[0][1]

def offset_pick_outward(curve_xy, dist, tol):
    if curve_xy is None or not curve_xy.IsClosed:
        return None
# -*- coding: utf-8 -*-
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import math

def ensure_layer(name):
    idx = sc.doc.Layers.FindName(name)
    if idx >= 0:
        return idx
    layer = Rhino.DocObjects.Layer()
    layer.Name = name
    return sc.doc.Layers.Add(layer)

def best_base_plane_from_brep(brep, tol):
    """
    Brepから「元のパネル平面っぽい平面」を推定する。
    方針：
      1) 平面Faceのうち面積最大のものを採用（押し出しなら上下どちらかが大面積）
      2) 取れなければ、BBoxから近似（最後の保険）
    """
    if brep is None or brep.Faces.Count == 0:
        return Rhino.Geometry.Plane.WorldXY

    best_pl = None
    best_area = -1.0

    # 1) planar face の最大面積を探す
    for f in brep.Faces:
        if f is None:
            continue
        rc, pl = f.TryGetPlane(tol)
        if not rc:
            continue
        amp = Rhino.Geometry.AreaMassProperties.Compute(f)
        a = amp.Area if amp else 0.0
        if a > best_area:
            best_area = a
            best_pl = pl

    if best_pl is not None:
        # 原点はBrep重心の投影に寄せると整列が安定
        vmp = Rhino.Geometry.VolumeMassProperties.Compute(brep)
        if vmp:
            cen = vmp.Centroid
            # 平面に原点を移す（軸はそのまま）
            best_pl.Origin = best_pl.ClosestPoint(cen)
        return best_pl

    # 2) 保険：BBoxから平面推定（精度は落ちる）
    bb = brep.GetBoundingBox(True)
    cen = bb.Center
    return Rhino.Geometry.Plane(cen, Rhino.Geometry.Vector3d.ZAxis)

def flatten_brep_to_worldxy(brep, tol):
    """Brepを、その基準平面からWorldXYへPlaneToPlaneで寝かせる"""
    base = best_base_plane_from_brep(brep, tol)
    xform = Rhino.Geometry.Transform.PlaneToPlane(base, Rhino.Geometry.Plane.WorldXY)

    dup = brep.DuplicateBrep()
    dup.Transform(xform)

    # 微小誤差でZが残るので、BBoxのminZを0へ寄せる（“床に置く”）
    bb = dup.GetBoundingBox(True)
    dz = -bb.Min.Z
    dup.Transform(Rhino.Geometry.Transform.Translation(0, 0, dz))
    return dup

def main():
    tol = sc.doc.ModelAbsoluteTolerance

    ids = rs.GetObjects("押し出しで作った立体フレーム（Brep）を選択",
                        rs.filter.polysurface | rs.filter.surface, preselect=True)
    if not ids:
        return

    gap = rs.GetReal("並べる間隔 gap（WorldXYでのX方向）", 50.0, 0.0)
    if gap is None:
        return

    layer_idx = ensure_layer("FLAT_XY_SOLIDS")
    attr = Rhino.DocObjects.ObjectAttributes()
    attr.LayerIndex = layer_idx

    rs.EnableRedraw(False)

    x_cursor = 0.0
    made = 0

    for obj_id in ids:
        brep = rs.coercebrep(obj_id)
        if brep is None:
            continue

        flat = flatten_brep_to_worldxy(brep, tol)

        # 幅を計ってX方向に整列
        bb = flat.GetBoundingBox(True)
        if not bb.IsValid:
            continue

        # 左端を x_cursor に合わせる
        dx = x_cursor - bb.Min.X
        flat.Transform(Rhino.Geometry.Transform.Translation(dx, 0, 0))

        sc.doc.Objects.AddBrep(flat, attr)
        made += 1

        # 次の配置位置へ
        bb2 = flat.GetBoundingBox(True)
        x_cursor = bb2.Max.X + gap

    rs.EnableRedraw(True)
    sc.doc.Views.Redraw()
    print("Done. made: {}".format(made))

if __name__ == "__main__":
    main()
