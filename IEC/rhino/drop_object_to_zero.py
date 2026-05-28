# -*- coding: utf-8 -*-
import rhinoscriptsyntax as rs

def drop_objects_to_zero():
    # オブジェクトを選択（メッシュ、ポリサーフェスなど）
    ids = rs.GetObjects("Z=0に着地させるオブジェクトを選択", 0, preselect=True)
    if not ids: return

    rs.EnableRedraw(False)
    for id in ids:
        # バウンディングボックスを取得
        bbox = rs.BoundingBox(id)
        if bbox:
            # bbox[0]は底面の角の座標（Point3d）
            min_z = bbox[0][2] 
            # 現在のZ高さ分だけ下に移動（引き算）
            rs.MoveObject(id, [0, 0, -min_z])
    
    rs.EnableRedraw(True)
    # Python 2.7用に .format() 記法に変更
    print "{} 個のオブジェクトをZ=0に移動しました".format(len(ids))

if __name__ == "__main__":
    drop_objects_to_zero()