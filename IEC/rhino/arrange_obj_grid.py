# -*- coding: utf-8 -*-
import rhinoscriptsyntax as rs
import math

def arrange_objects_grid():
    # 1. オブジェクトを選択
    ids = rs.GetObjects("整列させるオブジェクトを選択してください", 0, preselect=True)
    if not ids: return

    # 2. 設定（間隔など）
    margin = 10  # オブジェクト同士の隙間（単位: mmなど）
    
    rs.EnableRedraw(False)
    
    # グリッドの折り返し幅を計算（全体の個数の平方根で正方形っぽくする）
    row_count = int(math.ceil(math.sqrt(len(ids))))
    
    current_x = 0
    current_y = 0
    max_y_in_row = 0
    count = 0

    for id in ids:
        # バウンディングボックスを取得
        bbox = rs.BoundingBox(id)
        if not bbox: continue

        # 現在の位置とサイズを計算
        min_pt = bbox[0]
        max_pt = bbox[2]
        width = max_pt[0] - min_pt[0]
        depth = max_pt[1] - min_pt[1]
        
        # 移動ベクトルを計算（現在の場所から、ターゲット位置へ）
        # ターゲット位置: (current_x, current_y, 0)
        # オブジェクトの現在の左下: (min_pt[0], min_pt[1], min_pt[2])
        translation = [
            current_x - min_pt[0],
            current_y - min_pt[1],
            0 - min_pt[2] # Zは0に固定（念のため）
        ]
        
        rs.MoveObject(id, translation)

        # 次のX座標を更新
        current_x += width + margin
        
        # その行の中で一番大きいY（奥行き）を記録しておく
        if depth > max_y_in_row:
            max_y_in_row = depth
            
        count += 1
        
        # 折り返し判定
        if count % row_count == 0:
            current_x = 0
            current_y += max_y_in_row + margin
            max_y_in_row = 0 # 次の行のためにリセット

    rs.EnableRedraw(True)
    print "{} 個のオブジェクトを整列しました".format(len(ids))

if __name__ == "__main__":
    arrange_objects_grid()