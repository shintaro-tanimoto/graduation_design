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

class UnionFind(object):
    def __init__(self, n):
        self.p = list(range(n))
        self.r = [0]*n
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb: return
        if self.r[ra] < self.r[rb]:
            self.p[ra] = rb
        elif self.r[ra] > self.r[rb]:
            self.p[rb] = ra
        else:
            self.p[rb] = ra
            self.r[ra] += 1

def get_group_list(rhobj):
    try:
        return list(rhobj.Attributes.GetGroupList()) if rhobj and rhobj.Attributes.GroupCount > 0 else []
    except:
        return []

def try_get_planar_face_plane(brep, tol):
    best_pl = None
    best_area = -1.0
    if brep is None: 
        return None
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
    return best_pl

def best_base_plane_from_breps(breps, tol):
    # planar face 最大面積の平面を探す
    best_pl = None
    best_area = -1.0

    for b in breps:
        pl = try_get_planar_face_plane(b, tol)
        if pl is None:
            continue
        # 面積最大を優先
        # （TryGetPlaneだけだと面積が取れないので、もう一度計算して比較）
        for f in b.Faces:
            rc, pl2 = f.TryGetPlane(tol)
            if not rc:
                continue
            # plとpl2が同一平面の場合だけ面積比較
            if pl2.Normal.IsParallelTo(pl.Normal, 0.01) != 0:
                amp = Rhino.Geometry.AreaMassProperties.Compute(f)
                a = amp.Area if amp else 0.0
                if a > best_area:
                    best_area = a
                    best_pl = pl2

    if best_pl is None:
        return Rhino.Geometry.Plane.WorldXY

    # 原点をまとまりのbbox中心投影に寄せる（安定）
    bbs = [b.GetBoundingBox(True) for b in breps if b is not None]
    if bbs:
        bb = bbs[0]
        for x in bbs[1:]:
            bb.Union(x)
        cen = bb.Center
        best_pl.Origin = best_pl.ClosestPoint(cen)

    return best_pl

def bbox_of_breps(breps):
    if not breps:
        return None
    bb = breps[0].GetBoundingBox(True)
    for b in breps[1:]:
        bb.Union(b.GetBoundingBox(True))
    return bb

def flatten_group_breps_to_worldxy(breps, tol):
    base = best_base_plane_from_breps(breps, tol)
    xform = Rhino.Geometry.Transform.PlaneToPlane(base, Rhino.Geometry.Plane.WorldXY)

    dup_list = []
    for b in breps:
        if b is None:
            continue
        d = b.DuplicateBrep()
        d.Transform(xform)
        dup_list.append(d)

    if not dup_list:
        return []

    # Z=0へ床置き
    bb = bbox_of_breps(dup_list)
    dz = -bb.Min.Z
    if abs(dz) > tol:
        t = Rhino.Geometry.Transform.Translation(0, 0, dz)
        for d in dup_list:
            d.Transform(t)

    return dup_list

def main():
    tol = sc.doc.ModelAbsoluteTolerance

    ids = rs.GetObjects("押し出しで作った立体フレーム（Brep）を選択（グループはまとめて扱う）",
                        rs.filter.polysurface | rs.filter.surface, preselect=True)
    if not ids:
        return

    gap_x = rs.GetReal("配置の横間隔 gap_x", 50.0, 0.0)
    if gap_x is None: return
    gap_y = rs.GetReal("配置の縦間隔 gap_y", 50.0, 0.0)
    if gap_y is None: return

    # collect RhinoObjects + breps
    rhobjs = []
    breps = []
    for oid in ids:
        ro = sc.doc.Objects.FindId(oid)
        b = rs.coercebrep(oid)
        if ro and b:
            rhobjs.append(ro)
            breps.append(b)

    if not breps:
        return

    # --- group connectivity: "share any group => same item"
    n = len(breps)
    uf = UnionFind(n)

    gmap = {}
    for i, ro in enumerate(rhobjs):
        gl = get_group_list(ro)
        for g in gl:
            gmap.setdefault(g, []).append(i)

    for g, idxs in gmap.items():
        if len(idxs) >= 2:
            a0 = idxs[0]
            for j in idxs[1:]:
                uf.union(a0, j)

    comp = {}
    for i in range(n):
        r = uf.find(i)
        comp.setdefault(r, []).append(i)

    items = []
    for root, idxs in comp.items():
        items.append((min(idxs), idxs))
    items.sort(key=lambda x: x[0])
    items = [idxs for _, idxs in items]

    # flatten each item and measure
    flat_items = []
    widths = []
    heights = []

    for idxs in items:
        group_breps = [breps[i] for i in idxs]
        flat = flatten_group_breps_to_worldxy(group_breps, tol)
        if not flat:
            continue
        bb = bbox_of_breps(flat)
        w = bb.Max.X - bb.Min.X
        h = bb.Max.Y - bb.Min.Y
        flat_items.append((flat, bb, w, h))
        widths.append(w); heights.append(h)

    if not flat_items:
        return

    # heuristic wrap width
    max_w = max(widths) if widths else 1000.0
    total_area = sum([max(0.0, w)*max(0.0, h) for w, h in zip(widths, heights)])
    wrap_width = max(math.sqrt(total_area)*1.3, max_w*3.0)

    # output layer
    layer_idx = ensure_layer("FLAT_XY_SOLIDS")

    rs.EnableRedraw(False)

    x_cursor = 0.0
    y_cursor = 0.0
    row_h = 0.0

    made = 0
    item_count = 0

    for flat, bb, w, h in flat_items:
        # wrap
        if x_cursor > 0.0 and (x_cursor + w) > wrap_width:
            x_cursor = 0.0
            y_cursor -= (row_h + gap_y)
            row_h = 0.0

        # move so bbox min goes to cursor
        dx = x_cursor - bb.Min.X
        dy = y_cursor - bb.Min.Y
        t = Rhino.Geometry.Transform.Translation(dx, dy, 0)

        # create a new group for this copied item
        gname = "FLAT_ITEM_{:03d}".format(item_count+1)
        gindex = sc.doc.Groups.Add(gname)
        item_count += 1

        for b in flat:
            b.Transform(t)

            # ★ここが修正点：ObjectAttributes() は引数なしで作る
            attr = Rhino.DocObjects.ObjectAttributes()
            attr.LayerIndex = layer_idx
            if gindex >= 0:
                attr.AddToGroup(gindex)

            sc.doc.Objects.AddBrep(b, attr)
            made += 1

        x_cursor += w + gap_x
        row_h = max(row_h, h)

    rs.EnableRedraw(True)
    sc.doc.Views.Redraw()
    print("Done. items: {}, breps added: {}".format(len(flat_items), made))

if __name__ == "__main__":
    main()
