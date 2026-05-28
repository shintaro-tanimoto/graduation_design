# -*- coding: utf-8 -*-
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System

def layer_index_from_name(fullpath):
    try:
        idx = sc.doc.Layers.FindByFullPath(fullpath, -1)
        if idx >= 0:
            return idx
    except:
        pass
    return sc.doc.Layers.FindName(fullpath)

def is_descendant_layer(desc_idx, anc_id):
    """desc_idx の親を辿って anc_id に当たるなら True（循環防止）"""
    if desc_idx < 0:
        return False
    cur = sc.doc.Layers[desc_idx]
    seen = set()
    while cur and cur.ParentLayerId != System.Guid.Empty:
        if cur.Id == anc_id:
            return True
        if cur.Id in seen:
            break
        seen.add(cur.Id)
        pidx = sc.doc.Layers.FindId(cur.ParentLayerId)
        if pidx < 0:
            break
        cur = sc.doc.Layers[pidx]
    return False

def sibling_name_exists(parent_id, name):
    for i in range(sc.doc.Layers.Count):
        ly = sc.doc.Layers[i]
        if ly is None or ly.IsDeleted:
            continue
        if ly.ParentLayerId == parent_id and ly.Name == name:
            return True
    return False

def make_unique_child_name(parent_id, base_name):
    name = base_name
    k = 1
    while sibling_name_exists(parent_id, name):
        name = "{}_{}".format(base_name, k)
        k += 1
        if k > 9999:
            break
    return name

def copy_layer_shallow(src_layer):
    """
    Layer.Duplicate() が無い環境向けに、必要プロパティをコピーした新Layerを作る。
    注意：Id はコピーしない（Modifyでsrc_idxへ反映される）
    """
    nl = Rhino.DocObjects.Layer()
    # 見た目・属性系
    try: nl.Color = src_layer.Color
    except: pass
    try: nl.PlotColor = src_layer.PlotColor
    except: pass
    try: nl.PlotWeight = src_layer.PlotWeight
    except: pass
    try: nl.LinetypeIndex = src_layer.LinetypeIndex
    except: pass
    try: nl.MaterialIndex = src_layer.MaterialIndex
    except: pass
    try: nl.RenderMaterialIndex = src_layer.RenderMaterialIndex
    except: pass
    try: nl.IsVisible = src_layer.IsVisible
    except: pass
    try: nl.IsLocked = src_layer.IsLocked
    except: pass
    try: nl.IsExpanded = src_layer.IsExpanded
    except: pass
    try: nl.PlotWeightSource = src_layer.PlotWeightSource
    except: pass
    try: nl.PlotColorSource = src_layer.PlotColorSource
    except: pass
    try: nl.MaterialSource = src_layer.MaterialSource
    except: pass

    # Name と ParentLayerId は呼び出し側で必ず上書きする
    try: nl.Name = src_layer.Name
    except: pass
    try: nl.ParentLayerId = src_layer.ParentLayerId
    except: pass
    return nl

def move_layer_under_parent(src_idx, dst_parent_idx):
    """srcレイヤーをdst_parentレイヤーの子にする（名前衝突回避つき）"""
    src = sc.doc.Layers[src_idx]
    dst = sc.doc.Layers[dst_parent_idx]

    # 循環防止：dstがsrcの子孫なら不可
    if is_descendant_layer(dst_parent_idx, src.Id):
        return (False, "skip (cycle): {} -> {}".format(src.FullPath, dst.FullPath))

    # すでに同じ親ならスキップ
    if src.ParentLayerId == dst.Id:
        return (True, "already child: {}".format(src.FullPath))

    # 名前衝突回避
    new_name = make_unique_child_name(dst.Id, src.Name)

    new_layer = copy_layer_shallow(src)
    new_layer.ParentLayerId = dst.Id
    new_layer.Name = new_name

    ok = sc.doc.Layers.Modify(new_layer, src_idx, True)
    if not ok:
        return (False, "failed: {}".format(src.FullPath))

    return (True, "moved: {} -> {}::{}".format(src.FullPath, dst.FullPath, new_name))

def main():
    ids = rs.GetObjects("所属レイヤーを移動したいオブジェクトを選択", preselect=True)
    if not ids:
        return

    dst_name = rs.GetLayer("親にしたいレイヤーを選択（ここに子として入れる）")
    if not dst_name:
        return
    dst_idx = layer_index_from_name(dst_name)
    if dst_idx < 0:
        rs.MessageBox("親レイヤーが見つかりませんでした。", 0, "Error")
        return

    # 選択オブジェクトの所属レイヤーをユニーク化
    src_layer_indices = set()
    for oid in ids:
        ro = sc.doc.Objects.FindId(oid)
        if not ro:
            continue
        src_layer_indices.add(ro.Attributes.LayerIndex)

    # 親そのものを移動しようとしてる場合は除外
    src_layer_indices.discard(dst_idx)

    rs.EnableRedraw(False)

    ok_cnt = 0
    ng_cnt = 0
    logs = []

    for src_idx in sorted(list(src_layer_indices)):
        ly = sc.doc.Layers[src_idx]
        if ly is None or ly.IsDeleted:
            continue
        if ly.IsReference:
            ng_cnt += 1
            logs.append("skip (reference): {}".format(ly.FullPath))
            continue

        ok, msg = move_layer_under_parent(src_idx, dst_idx)
        logs.append(msg)
        if ok: ok_cnt += 1
        else: ng_cnt += 1

    rs.EnableRedraw(True)
    sc.doc.Views.Redraw()

    print("Done. moved/ok={}, failed/skip={}".format(ok_cnt, ng_cnt))
    for s in logs:
        print(s)

if __name__ == "__main__":
    main()