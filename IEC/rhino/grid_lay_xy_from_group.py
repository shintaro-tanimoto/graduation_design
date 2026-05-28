# -*- coding: utf-8 -*-
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import math

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

def layer_key_from_obj(rhobj):
    """レイヤー階層込みでキー化（例: PANEL_OUT::PANEL_001）"""
    try:
        li = rhobj.Attributes.LayerIndex
        layer = sc.doc.Layers[li]
        # FullPath が使える環境ならそれ優先
        fp = layer.FullPath
        if fp: return fp
        return layer.Name
    except:
        return None

def best_base_plane_from_breps(breps, tol):
    """押し出し体の“面積最大の平面Face”を基準平面にする"""
    best_pl = None
    best_area = -1.0

    for b in breps:
        if b is None: 
            continue
        for f in b.Faces:
            rc, pl = f.TryGetPlane(tol)
            if not rc:
                continue
            amp = Rhino.Geometry.AreaMassProperties.Compute(f)
            a = amp.Area if amp else 0.0
            if a > best_area:
                best_area = a
                best_pl = pl

    if best_pl is None:
        return Rhino.Geometry.Plane.WorldXY

    # 原点はbbox中心の投影へ寄せて安定化
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

def flatten_group_keep_layer(breps, layer_indices, tol):
    """
    まとまり（同一平面扱い）をWorldXYへ寝かせて、
    各Brepに「元レイヤー」を保持して返す: [(flat_brep, layer_idx), ...]
    """
    base = best_base_plane_from_breps(breps, tol)
    xform = Rhino.Geometry.Transform.PlaneToPlane(base, Rhino.Geometry.Plane.WorldXY)

    pairs = []
    for b, li in zip(breps, layer_indices):
        if b is None:
            continue
        d = b.DuplicateBrep()
        d.Transform(xform)
        pairs.append((d, li))

    if not pairs:
        return []

    # Z=0へ床置き（まとまり全体で揃える）
    bb = bbox_of_breps([p[0] for p in pairs])
    dz = -bb.Min.Z
    if abs(dz) > tol:
        t = Rhino.Geometry.Transform.Translation(0, 0, dz)
        for d, _ in pairs:
            d.Transform(t)

    return pairs

def main():
    tol = sc.doc.ModelAbsoluteTolerance

    ids = rs.GetObjects(
        "押し出しで作った立体（Brep）を選択（寝かせたコピーを元レイヤーに追加）",
        rs.filter.polysurface | rs.filter.surface,
        preselect=True
    )
    if not ids:
        return

    gap_x = rs.GetReal("配置の横間隔 gap_x", 50.0, 0.0)
    if gap_x is None: return
    gap_y = rs.GetReal("配置の縦間隔 gap_y", 50.0, 0.0)
    if gap_y is None: return

    # collect: (RhinoObject, Brep, group_list, layer_index, layer_key)
    ro_list = []
    b_list = []
    g_list = []
    li_list = []
    lk_list = []

    for oid in ids:
        ro = sc.doc.Objects.FindId(oid)
        b = rs.coercebrep(oid)
        if ro and b:
            ro_list.append(ro)
            b_list.append(b)
            g_list.append(get_group_list(ro))
            li_list.append(ro.Attributes.LayerIndex)
            lk_list.append(layer_key_from_obj(ro))

    if not b_list:
        return

    # --- connectivity: share any group => same item
    # --- fallback: if no groups, share same layer(fullpath) => same item
    n = len(b_list)
    uf = UnionFind(n)

    # group-based union
    gmap = {}
    any_group = False
    for i, gl in enumerate(g_list):
        if gl:
            any_group = True
        for g in gl:
            gmap.setdefault(g, []).append(i)
    for g, idxs in gmap.items():
        if len(idxs) >= 2:
            a0 = idxs[0]
            for j in idxs[1:]:
                uf.union(a0, j)

    # layer-based union (always safeに追加。グループが無くてもまとまる)
    lmap = {}
    for i, lk in enumerate(lk_list):
        if lk:
            lmap.setdefault(lk, []).append(i)
    # “グループが全く無い”場合はレイヤーでまとめる（念のため）
    if not any_group:
        for lk, idxs in lmap.items():
            if len(idxs) >= 2:
                a0 = idxs[0]
                for j in idxs[1:]:
                    uf.union(a0, j)

    # build items
    comp = {}
    for i in range(n):
        r = uf.find(i)
        comp.setdefault(r, []).append(i)

    # preserve order
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
        breps = [b_list[i] for i in idxs]
        layers = [li_list[i] for i in idxs]
        pairs = flatten_group_keep_layer(breps, layers, tol)
        if not pairs:
            continue

        bb = bbox_of_breps([p[0] for p in pairs])
        w = bb.Max.X - bb.Min.X
        h = bb.Max.Y - bb.Min.Y
        flat_items.append((pairs, bb, w, h))
        widths.append(w)
        heights.append(h)

    if not flat_items:
        return

    # heuristic wrap width（適当折り返し）
    max_w = max(widths) if widths else 1000.0
    total_area = sum([max(0.0, w)*max(0.0, h) for w, h in zip(widths, heights)])
    wrap_width = max(math.sqrt(total_area) * 1.3, max_w * 3.0)

    rs.EnableRedraw(False)

    x_cursor = 0.0
    y_cursor = 0.0
    row_h = 0.0
    made = 0

    for pairs, bb, w, h in flat_items:
        # wrap
        if x_cursor > 0.0 and (x_cursor + w) > wrap_width:
            x_cursor = 0.0
            y_cursor -= (row_h + gap_y)
            row_h = 0.0

        # move to cursor
        dx = x_cursor - bb.Min.X
        dy = y_cursor - bb.Min.Y
        t = Rhino.Geometry.Transform.Translation(dx, dy, -100)

        for b, layer_idx in pairs:
            b.Transform(t)

            attr = Rhino.DocObjects.ObjectAttributes()
            # ★重要：元レイヤーへ入れる（階層も同じ）
            attr.LayerIndex = layer_idx

            sc.doc.Objects.AddBrep(b, attr)
            made += 1

        x_cursor += w + gap_x
        row_h = max(row_h, h)

    rs.EnableRedraw(True)
    sc.doc.Views.Redraw()
    print("Done. breps added: {}".format(made))

if __name__ == "__main__":
    main()
