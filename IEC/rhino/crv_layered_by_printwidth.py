# -*- coding: utf-8 -*-
import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs

def effective_plot_weight_mm(oid):
    """Resolve effective plot weight (mm) for object id, considering ByLayer/ByObject."""
    rh_obj = sc.doc.Objects.FindId(oid)
    if rh_obj is None:
        return None

    attr = rh_obj.Attributes
    src = attr.PlotWeightSource

    if src in (
        Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromLayer,
        Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromParent
    ):
        layer = sc.doc.Layers[attr.LayerIndex]
        return float(layer.PlotWeight)
    else:
        return float(attr.PlotWeight)

def ensure_layer(name, parent_index=-1):
    """Create layer if not exists; return layer index."""
    idx = sc.doc.Layers.Find(name, True)
    if idx >= 0:
        return idx

    layer = Rhino.DocObjects.Layer()
    layer.Name = name
    if parent_index >= 0:
        layer.ParentLayerId = sc.doc.Layers[parent_index].Id

    idx = sc.doc.Layers.Add(layer)
    return idx

def set_layer_plot_weight(layer_index, w_mm):
    """Set layer plot weight (mm) without using Duplicate()."""
    layer = sc.doc.Layers[layer_index]
    if layer is None:
        return

    # そのまま PlotWeight を更新して Modify に渡す（Duplicate不要）
    try:
        layer.PlotWeight = float(w_mm)
        sc.doc.Layers.Modify(layer, layer_index, True)
    except Exception as e:
        # 環境によっては直接代入がダメなことがあるので回避策
        print("レイヤーのPlotWeight更新に失敗:", e)

def move_selected_curves_to_layers_by_weight(
    prefix="PW_",
    mm_digits=2,
    parent_layer_name="__by_plotweight__",
    set_objects_to_by_layer=True,
    also_set_layer_plotweight=True
):
    ids = rs.SelectedObjects()
    if not ids:
        print("オブジェクトが選択されていません。")
        return

    curve_ids = [oid for oid in ids if rs.ObjectType(oid) & rs.filter.curve]
    if not curve_ids:
        print("選択内に曲線がありません。")
        return

    parent_idx = ensure_layer(parent_layer_name)
    moved = 0
    used_layer_names = set()

    for oid in curve_ids:
        if rs.IsObjectLocked(oid):
            continue

        w = effective_plot_weight_mm(oid)
        if w is None:
            continue

        # 未設定(-1)等は Default 扱い
        if w < 0:
            weight_str = "Default"
            w_rounded = -1.0
        else:
            w_rounded = round(float(w), mm_digits)
            weight_str = ("%.*f" % (mm_digits, w_rounded))

        layer_name = prefix + weight_str + ("" if weight_str == "Default" else "mm")

        target_idx = ensure_layer(layer_name, parent_index=parent_idx)
        used_layer_names.add(layer_name)

        if also_set_layer_plotweight and w_rounded >= 0:
            set_layer_plot_weight(target_idx, w_rounded)

        rh_obj = sc.doc.Objects.FindId(oid)
        if rh_obj is None:
            continue

        attr = rh_obj.Attributes.Duplicate()
        attr.LayerIndex = target_idx

        # 移動後はレイヤー従属（おすすめ）
        if set_objects_to_by_layer:
            attr.PlotWeightSource = Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromLayer

        sc.doc.Objects.ModifyAttributes(oid, attr, True)
        moved += 1

    sc.doc.Views.Redraw()
    print("移動した曲線数:", moved)
    print("作成/使用したレイヤー:")
    for n in sorted(list(used_layer_names)):
        print("  -", n)

# 実行
move_selected_curves_to_layers_by_weight()

