# -*- coding: utf-8 -*-
import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs

def _effective_plot_weight(rh_obj):
    """Return effective plot weight (mm). Handles ByLayer/ByObject."""
    attr = rh_obj.Attributes
    src = attr.PlotWeightSource  # ObjectPlotWeightSource

    # Rhino 7/8 enum names
    if src == Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromLayer:
        layer = sc.doc.Layers[attr.LayerIndex]
        return layer.PlotWeight
    elif src == Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromParent:
        # Treat as layer-based in most cases
        layer = sc.doc.Layers[attr.LayerIndex]
        return layer.PlotWeight
    else:
        return attr.PlotWeight

def _is_from_layer(rh_obj):
    return rh_obj.Attributes.PlotWeightSource == Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromLayer

def join_curves_same_layer_same_weight(tol=None, skip_locked=True):
    if tol is None:
        tol = sc.doc.ModelAbsoluteTolerance

    # collect curve objects
    ids = rs.ObjectsByType(rs.filter.curve, select=False)
    if not ids:
        print("曲線が見つかりません。")
        return

    # group by (layer_index, effective_plot_weight)
    groups = {}
    for oid in ids:
        rh_obj = sc.doc.Objects.FindId(oid)
        if rh_obj is None:
            continue
        if skip_locked and rh_obj.Attributes.Locked:
            continue

        layer_index = rh_obj.Attributes.LayerIndex
        w = _effective_plot_weight(rh_obj)

        # floatキーの誤差対策：丸め
        key = (layer_index, round(float(w), 6))
        groups.setdefault(key, []).append(oid)

    joined_count = 0

    for (layer_index, w), curve_ids in groups.items():
        if len(curve_ids) < 2:
            continue

        # 同グループ内の曲線をJoin（繋がるものだけ結合される）
        res = rs.JoinCurves(curve_ids, delete_input=True, tolerance=tol)
        if not res:
            continue

        # 結合後の曲線に線幅属性を“維持”させる
        # すべてByLayerだったグループはByLayerのまま、
        # それ以外はByObjectにして線幅を固定する
        all_from_layer = True
        for oid in curve_ids:
            rh_obj = sc.doc.Objects.FindId(oid)
            if rh_obj and not _is_from_layer(rh_obj):
                all_from_layer = False
                break

        for new_id in res:
            new_obj = sc.doc.Objects.FindId(new_id)
            if new_obj is None:
                continue
            attr = new_obj.Attributes.Duplicate()
            attr.LayerIndex = layer_index
            if all_from_layer:
                attr.PlotWeightSource = Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromLayer
            else:
                attr.PlotWeightSource = Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromObject
                attr.PlotWeight = float(w)
            sc.doc.Objects.ModifyAttributes(new_id, attr, True)

        joined_count += len(res)

    sc.doc.Views.Redraw()
    print("完了。結合後に作成された曲線数:", joined_count)

# 実行（必要ならtolを少し大きく：例 tol=0.05 など）
join_curves_same_layer_same_weight()
