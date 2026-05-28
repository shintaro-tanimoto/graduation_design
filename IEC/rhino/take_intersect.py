# -*- coding: utf-8 -*-
import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
import System

# ===== 設定 =====
INCLUDE_SUBLAYERS = True      # True: 指定レイヤー配下のサブレイヤーも対象
CREATE_RESULT_LAYER = True    # True: 交差結果を専用レイヤーへ
RESULT_LAYER_ROOT = "INTERSECTIONS"
# =================


def _clean_layer_name(s):
    return s.replace("::", "__").replace("/", "_").replace("\\", "_").replace(":", "_")


def _get_layer_indices(fullpath, include_sublayers=True):
    """fullpath のレイヤーindexと（必要なら）子孫レイヤーindexも返す"""
    doc = sc.doc
    idx = doc.Layers.FindByFullPath(fullpath, True)
    if idx < 0:
        return []

    indices = [idx]
    if not include_sublayers:
        return indices

    def collect_children(parent_index):
        parent = doc.Layers[parent_index]
        for layer in doc.Layers:
            if layer.ParentLayerId == parent.Id:
                indices.append(layer.Index)
                collect_children(layer.Index)

    collect_children(idx)
    return indices


def _ensure_result_layer(target_layer_path):
    """RESULT_LAYER_ROOT::(target_layer_path整形) を作ってそのindexを返す"""
    doc = sc.doc

    root_idx = doc.Layers.FindByFullPath(RESULT_LAYER_ROOT, True)
    if root_idx < 0:
        root_layer = Rhino.DocObjects.Layer()
        root_layer.Name = RESULT_LAYER_ROOT
        root_idx = doc.Layers.Add(root_layer)

    child_name = _clean_layer_name(target_layer_path)
    full = RESULT_LAYER_ROOT + "::" + child_name
    out_idx = doc.Layers.FindByFullPath(full, True)
    if out_idx < 0:
        child = Rhino.DocObjects.Layer()
        child.Name = child_name
        child.ParentLayerId = doc.Layers[root_idx].Id
        out_idx = doc.Layers.Add(child)

    return out_idx


def _to_curve(rh_obj):
    g = rh_obj.Geometry
    if isinstance(g, Rhino.Geometry.Curve):
        return g
    try:
        return Rhino.Geometry.Curve.TryConvertCurve(g)
    except:
        return None


def _to_brep(rh_obj):
    g = rh_obj.Geometry
    if isinstance(g, Rhino.Geometry.Extrusion):
        try:
            return g.ToBrep()
        except:
            return None
    if isinstance(g, Rhino.Geometry.Brep):
        return g
    try:
        return Rhino.Geometry.Brep.TryConvertBrep(g)
    except:
        return None


def _iter_objects_in_layer_indices(layer_indices):
    """指定layer index群のオブジェクト(Guid)を返す（判定なし）"""
    doc = sc.doc
    for rh_obj in doc.Objects:
        if rh_obj is None or rh_obj.IsDeleted:
            continue
        if rh_obj.Attributes is None:
            continue
        if rh_obj.Attributes.LayerIndex not in layer_indices:
            continue
        yield rh_obj.Id


def _add_results(curves, points, layer_index, name_prefix):
    """曲線配列と点配列をドキュメントへ追加"""
    doc = sc.doc
    added_ids = []

    attr = Rhino.DocObjects.ObjectAttributes()
    if layer_index is not None:
        attr.LayerIndex = layer_index

    if curves:
        for i, c in enumerate(curves):
            if c is None:
                continue
            cid = doc.Objects.AddCurve(c, attr)
            if cid != System.Guid.Empty:
                rs.ObjectName(cid, "{}_curve_{:03d}".format(name_prefix, i))
                added_ids.append(cid)

    if points:
        for i, p in enumerate(points):
            pid = doc.Objects.AddPoint(p, attr)
            if pid != System.Guid.Empty:
                rs.ObjectName(pid, "{}_pt_{:03d}".format(name_prefix, i))
                added_ids.append(pid)

    return added_ids


def _brepbrep_intersection(brepA, brepB, tol):
    """
    Intersection.BrepBrep の戻り値差（2値/3値）を吸収して
    (curves_list, points_list) を返す
    """
    res = Rhino.Geometry.Intersect.Intersection.BrepBrep(brepA, brepB, tol)

    # Rhino環境により res が (curves, points) or (success, curves, points)
    if isinstance(res, tuple):
        if len(res) == 3:
            rc, crvs, pts = res
            if not rc:
                return [], []
        elif len(res) == 2:
            crvs, pts = res
        else:
            return [], []
    else:
        # 想定外（基本ここには来ないはず）
        return [], []

    curves = list(crvs) if crvs else []
    points = [pt for pt in pts] if pts else []
    return curves, points


def _intersect_pair(target_obj, other_obj, tol):
    """
    target_obj, other_obj: RhinoObject
    返り値: (curves, points) それぞれ list
    """
    t_brep = _to_brep(target_obj)
    o_brep = _to_brep(other_obj)
    t_crv = _to_curve(target_obj)
    o_crv = _to_curve(other_obj)

    curves = []
    points = []

    # Brep - Brep
    if t_brep and o_brep:
        crvs, pts = _brepbrep_intersection(t_brep, o_brep, tol)
        curves.extend(crvs)
        points.extend(pts)
        return curves, points

    # Curve - Brep
    if t_crv and o_brep:
        x = Rhino.Geometry.Intersect.Intersection.CurveBrep(t_crv, o_brep, tol, tol)
        if x:
            for ev in x:
                if ev is None:
                    continue
                if ev.IsPoint:
                    points.append(ev.PointA)
                elif ev.IsOverlap and ev.OverlapA:
                    curves.append(ev.OverlapA)
        return curves, points

    # Brep - Curve
    if t_brep and o_crv:
        x = Rhino.Geometry.Intersect.Intersection.CurveBrep(o_crv, t_brep, tol, tol)
        if x:
            for ev in x:
                if ev is None:
                    continue
                if ev.IsPoint:
                    points.append(ev.PointA)
                elif ev.IsOverlap and ev.OverlapA:
                    curves.append(ev.OverlapA)
        return curves, points

    # Curve - Curve
    if t_crv and o_crv:
        x = Rhino.Geometry.Intersect.Intersection.CurveCurve(t_crv, o_crv, tol, tol)
        if x:
            for ev in x:
                if ev is None:
                    continue
                if ev.IsPoint:
                    points.append(ev.PointA)
                elif ev.IsOverlap:
                    points.append(ev.PointA)
                    points.append(ev.PointB)
        return curves, points

    # 非対応（Meshなど）
    return None, None


def main():
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance

    target_id = rs.GetObject("Intersectの基準（ターゲット）を1つ選択", preselect=True)
    if not target_id:
        return
    target_obj = doc.Objects.Find(target_id)
    if target_obj is None:
        return

    layer_path = rs.GetLayer("Intersect対象のレイヤーを選択（中の全オブジェクトとターゲットを1対1でIntersect）")
    if not layer_path:
        return

    layer_indices = _get_layer_indices(layer_path, INCLUDE_SUBLAYERS)
    if not layer_indices:
        rs.MessageBox("指定レイヤーが見つかりません: {}".format(layer_path), 0, "Error")
        return

    other_ids = [oid for oid in _iter_objects_in_layer_indices(layer_indices) if oid != target_id]
    if len(other_ids) == 0:
        rs.MessageBox("指定レイヤー内に対象オブジェクトがありません。", 0, "Info")
        return

    out_layer_index = None
    if CREATE_RESULT_LAYER:
        out_layer_index = _ensure_result_layer(layer_path)

    rs.EnableRedraw(False)

    made_pairs = 0
    made_geom = 0
    skipped = 0

    for i, oid in enumerate(other_ids):
        other_obj = doc.Objects.Find(oid)
        if other_obj is None:
            skipped += 1
            continue

        curves, points = _intersect_pair(target_obj, other_obj, tol)
        if curves is None and points is None:
            skipped += 1
            continue
        if (not curves) and (not points):
            continue

        name_prefix = "IX_{:03d}".format(i)
        added = _add_results(curves, points, out_layer_index, name_prefix)

        if added:
            made_pairs += 1
            made_geom += len(added)

    rs.EnableRedraw(True)
    doc.Views.Redraw()

    Rhino.RhinoApp.WriteLine(
        "Done. IntersectPairs(with results)={}, CreatedObjects={}, Skipped(unsupported)={}".format(
            made_pairs, made_geom, skipped
        )
    )


if __name__ == "__main__":
    main()
