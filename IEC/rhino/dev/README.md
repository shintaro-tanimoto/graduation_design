# Rhino Development & Testing Scripts

このディレクトリには、Rhinoスクリプトの開発・デバッグ・テスト用のスクリプトが含まれています。

## スクリプト一覧

### テスト系
- `test_obj_parsing.py` - OBJファイルパース機能のテスト
- `test_face_detection.py` - 面検出ロジックのテスト
- `test_area_filter.py` - 面積フィルタリングのテスト
- `test_tolerance.py` - 許容誤差設定のテスト
- `test_min_vertices.py` - 最小頂点数チェックのテスト
- `capture_test.py` - ビューキャプチャ機能のテスト

### デバッグ系
- `debug_adjacency.py` - 隣接関係のデバッグ

### 分析・インスペクト系
- `analyze_gen25.py` - 特定世代の分析
- `inspect_cell_0.py` - cell0の詳細インスペクト
- `inspect_cell_39.py` - cell39の詳細インスペクト
- `measure_vertex_distances.py` - 頂点間距離測定

## 使用方法

これらのスクリプトは通常のワークフローでは不要です。Rhinoスクリプトの開発やトラブルシューティング時に使用してください。

## メインスクリプト

本番用のRhinoスクリプトは親ディレクトリ (`rhino/`) にあります：
- `iec_ui.py`, `iec_ui_cli.py` - IEC UI
- `import2objs.py`, `import2objs_cli.py`, `import2objs_simple.py` - メッシュインポート
- `visualize_xy_pairs.py` - XYペア可視化
- など
