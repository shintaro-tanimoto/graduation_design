# Laguerre Voronoi Test Programs

このディレクトリには、1000x1000x1000の空間内に40個のランダムな重み付き点を生成し、Laguerre Voronoi（Power Diagram）を計算するテストプログラムとRhinoスクリプトが含まれています。

## ファイル構成

- **test_laguerre.py** - メインのテストプログラム
  - 40個のランダムな重み付き点を生成
  - Laguerre Voronoiダイアグラムを計算
  - OBJファイルとJSONファイルを出力

- **create_spheres_rhino.py** - Rhinoスクリプト
  - JSONファイルから点データを読み込む
  - 各点の位置に重みに比例した半径の球を作成
  - Rhino内でのみ実行可能

- **laguerre_test.obj** - 生成されたLaguerre VoronoiダイアグラムのOBJファイル
  - Voronoiセル（40個）
  - 各点を表す球体

- **sites_data.json** - 点データのJSONファイル
  - 各点の位置（x, y, z）
  - 各点の重み（weight）
  - メタデータ（境界ボックス、シードなど）

## 使用方法

### 1. Pythonプログラムの実行

```bash
cd /home/shint/py_code
python test/test_laguerre.py
```

このコマンドは以下を生成します：
- `test/laguerre_test.obj` - Voronoiダイアグラム
- `test/sites_data.json` - 点データ

### 2. Rhinoで球を作成

#### 方法A: Rhinoスクリプトを実行

1. Rhinoを開く
2. コマンドラインに `RunPythonScript` と入力
3. `test/create_spheres_rhino.py` ファイルを選択
4. スクリプトが実行され、球が作成されます

#### 方法B: スクリプトエディタで実行

1. Rhinoを開く
2. コマンドラインに `EditPythonScript` と入力
3. スクリプトエディタで `test/create_spheres_rhino.py` を開く
4. 実行ボタンをクリック

### 3. OBJファイルをRhinoにインポート

```
1. Rhinoを開く
2. File > Import... を選択
3. test/laguerre_test.obj を選択
4. インポートオプションで適切な設定を選択
```

## パラメータのカスタマイズ

### test_laguerre.py の設定

ファイル内の以下の変数を変更できます：

```python
N_POINTS = 40           # 点の数
BOX_SIZE = 1000         # 境界ボックスのサイズ
WEIGHT_RANGE = (10, 100) # 重みの範囲
SEED = 42               # ランダムシード（再現性のため）
```

### create_spheres_rhino.py の設定

スクリプト内の以下のパラメータを変更できます：

```python
radius_scale = 1.0  # 球の半径スケール
                    # 0.5 = 半分のサイズ
                    # 2.0 = 2倍のサイズ
```

## 出力例

### コンソール出力

```
============================================================
  Laguerre Voronoi Test Program
============================================================
Configuration:
  Number of points: 40
  Bounding box: 1000x1000x1000
  Weight range: 10 - 100
  Random seed: 42
  Output OBJ file: test/laguerre_test.obj
  Output JSON file: test/sites_data.json
============================================================

Generating random weighted points...
Generated 40 points

Sample points (first 5):
  Point 0: position=(374.54, 950.71, 731.99), weight=82.67
  Point 1: position=(598.66, 156.02, 155.99), weight=90.65
  ...

Computing Laguerre Voronoi (Power Diagram)...
Cell 0: OK (14 vertices)
Cell 1: OK (16 vertices)
...

Results:
  Total cells: 40
  Successful cells: 40
  Failed cells: 0
```

## Rhinoスクリプトの機能

### レイヤー管理

- スクリプトは自動的に "LaguerreSpheres" レイヤーを作成します
- すべての球はこのレイヤーに配置されます
- `SelLayer` コマンドですべての球を選択できます

### 球のサイズ

- デフォルトでは、球の半径 = 重み × radius_scale
- `radius_scale` パラメータで調整可能
- 重みの範囲: 10～100
- デフォルトの球の半径範囲: 10～100

### 使用可能なRhinoコマンド

- `SelLayer` - レイヤー内のすべてのオブジェクトを選択
- `Hide` - 選択したオブジェクトを非表示
- `Show` - 非表示のオブジェクトを表示
- `Delete` - 選択したオブジェクトを削除

## トラブルシューティング

### JSONファイルが見つからない

エラー: `Error: JSON file not found`

解決策:
1. `test_laguerre.py` を実行して `sites_data.json` を生成
2. Rhinoスクリプトと同じディレクトリに `sites_data.json` があることを確認

### 球が大きすぎる/小さすぎる

解決策:
1. `create_spheres_rhino.py` の `radius_scale` パラメータを調整
2. 例: `radius_scale = 0.5` で半分のサイズに

### Rhinoスクリプトが実行できない

確認事項:
1. Rhinoが開いているか
2. スクリプトのパスが正しいか
3. Rhinoのバージョンが Python スクリプトに対応しているか（Rhino 5以降）

## 技術詳細

### Laguerre Voronoi (Power Diagram)

- 標準のVoronoiダイアグラムの拡張
- 各点に重み（weight）を持たせる
- セル境界: `pow(p, s) = ||p - s||² - w_s`
- 重みが大きいほど、そのセルが広くなる

### 座標系

- Pythonプログラム: Y-up座標系
- Rhino: Z-up座標系
- OBJエクスポート時に自動変換

### 依存関係

- NumPy >= 1.26.0
- SciPy >= 1.10.0
- Rhino 5以降（Rhinoスクリプト用）

## ライセンス

このコードは教育・研究目的で自由に使用できます。

## 参考文献

- Aurenhammer, F. (1987). Power Diagrams: Properties, Algorithms and Applications
- CLAUDE.MD - プロジェクト全体のドキュメント
