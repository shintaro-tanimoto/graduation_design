# -*- coding: utf-8 -*-
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System

def layer_index_from_fullpath(fullpath):
    try:
        idx = sc.doc.Layers.FindByFullPath(fullpath, -1)
        if idx >= 0:
            return idx
    except:
        pass
    return sc.doc.Layers.FindName(fullpath)

def is_descendant(layer_idx, ancestor_id):
    """layer_idx が ancestor_id の配下(子孫)なら True"""
    if layer_idx < 0:
        return False
    cur = sc.doc.Layers[layer_idx]
    seen = set()
    while cur and cur.ParentLayerId != System.Guid.Empty:
        if cur.ParentLayerId == ancestor_id:
            return True
        if cur.Id in seen:
            break
        seen.add(cur.Id)
        pidx = sc.doc.Layers.FindId(cur.ParentLayerId)
        if pidx < 0:
            break
        cur = sc.doc.Layers[pidx]
    return False

def build_counts_subtree():
    """
    direct_count[layer_idx]  : そのレイヤー直下(=そのレイヤーに属する)の数
    subtree_count[layer_idx] : そのレイヤー配下(子孫含む)の合計数
    """
    direct_count = {}
    subtree_count = {}

    # すべての通常オブジェクトを列挙
    it = sc.doc.Objects.GetObjectList(Rhino.DocObjects.ObjectType.AnyObject)
    for obj in it:
        if obj is None:
            continue
        if obj.IsDeleted:
            continue

        li = obj.Attributes.LayerIndex
        if li < 0:
            continue

        direct_count[li] = direct_count.get(li, 0) + 1

        # 親へ遡ってsubtree_countを増やす
        cur_idx = li
        guard = 0
        while cur_idx >= 0 and guard < 200:
            subtree_count[cur_idx] = subtree_count.get(cur_idx, 0) + 1
            lyr = sc.doc.Layers[cur_idx]
            if lyr.ParentLayerId == System.Guid.Empty:
                break
            cur_idx = sc.doc.Layers.FindId(lyr.ParentLayerId)
            guard += 1

    return direct_count, subtree_count

def main():
    # 親レイヤーを選ぶ
    parent_full = rs.GetLayer("サブレイヤーを調べたい『親レイヤー』を選択")
    if not parent_full:
        return

    parent_idx = layer_index_from_fullpath(parent_full)
    if parent_idx < 0:
        rs.MessageBox("親レイヤーが見つかりませんでした。", 0, "Error")
        return

    parent_layer = sc.doc.Layers[parent_idx]
    parent_id = parent_layer.Id

    # 「サブツリー込み」で数える（FRAME/GRIDみたいに下に分けてても合計できる）
    include_descendants = True

    # しきい値（デフォルト2）
    min_required = rs.GetInteger("何個未満を抽出しますか？（例：2 → 0個/1個を抽出）", 2, 0)
    if min_required is None:
        return

    direct_count, subtree_count = build_counts_subtree()

    # 対象サブレイヤー一覧
    targets = []
    for i in range(sc.doc.Layers.Count):
        ly = sc.doc.Layers[i]
        if ly is None or ly.IsDeleted:
            continue
        if ly.Id == parent_id:
            continue
        if is_descendant(i, parent_id):
            targets.append(i)

    if not targets:
        rs.MessageBox("親レイヤー配下にサブレイヤーが見つかりませんでした。", 0, "Info")
        return

    # 抽出
    bad = []
    for li in targets:
        cnt = (subtree_count.get(li, 0) if include_descendants else direct_count.get(li, 0))
        if cnt < min_required:
            ly = sc.doc.Layers[li]
            bad.append((cnt, ly.FullPath if ly.FullPath else ly.Name))

    bad.sort(key=lambda x: (x[0], x[1]))

    # 出力
    if not bad:
        rs.MessageBox("条件に合うサブレイヤーはありませんでした。", 0, "OK")
        return

    print("=== sublayers with object count < {} (descendants included={}) ===".format(min_required, include_descendants))
    for cnt, path in bad:
        print("{:>3}  {}".format(cnt, path))

    rs.MessageBox("見つかったサブレイヤー数：{}\n詳細はコマンド履歴(History)に出力しました。".format(len(bad)), 0, "Done")

if __name__ == "__main__":
    main()
