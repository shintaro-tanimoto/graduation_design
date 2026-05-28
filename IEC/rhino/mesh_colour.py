# -*- coding: utf-8 -*-
import rhinoscriptsyntax as rs
import colorsys

def palette_hsv_spread(n, s=0.65, v=0.95, hue_offset=0.0):
    """
    色相を等間隔に散らして、見た目がきれいに離れるパレットを作る
    - n: 色数
    - s, v: 彩度/明度 (0-1)
    - hue_offset: 0-1 のオフセット（並びの開始色を回す）
    """
    cols = []
    if n <= 0:
        return cols
    for i in range(n):
        h = (hue_offset + float(i) / float(n)) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        cols.append((int(r*255), int(g*255), int(b*255)))
    return cols

def main():
    ids = rs.GetObjects("色を付けるメッシュを選択", rs.filter.mesh, preselect=True)
    if not ids:
        return

    colors = palette_hsv_spread(len(ids), s=0.70, v=0.95, hue_offset=0.02)

    rs.EnableRedraw(False)
    for oid, col in zip(ids, colors):
        rs.ObjectColorSource(oid, 1)  # 1 = object color
        rs.ObjectColor(oid, col)
    rs.EnableRedraw(True)

if __name__ == "__main__":
    main()
