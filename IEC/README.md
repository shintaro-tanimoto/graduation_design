# IEC - Interactive Evolutionary Computation for Architectural Form Generation

人間参加型の進化的形態生成システム。3D重み付きVoronoi図（Power Diagram）を使用した建築デザインの探索ツールです。

## システム概要

2つのワークフローが利用可能です：

### 🎯 6候補生成システム（Phase 1-3完了・推奨）

**卒業設計や本格的な設計探索に最適**

1. **世代生成**: 6候補を同時生成（cand_00～cand_05）
2. **トーナメント比較**: Swiss-system方式で効率的な9マッチ比較
3. **勝者選択**: トーナメント結果から最優秀候補を選出
4. **次世代生成**: 勝者と高品質Archive候補を親として進化
5. **系譜追跡**: 完全なprovenance追跡で形態の由来を可視化
6. **制約管理**: 6種類の制約チェック + 自動修復

### 🔰 2候補ペアシステム（簡易版）

**学習やクイックテストに最適**

1. **生成**: 2つの候補形態（A/B）を3D Power Diagramとして生成
2. **評価**: Rhinoなどの3Dビューアで両方の形態を並べて表示
3. **選択**: デザイナーが好みの形態を選択
4. **探索**: ランダムサンプリングで広範囲の設計空間を探索
5. **反復**: 好みの形態が見つかるまで繰り返し
6. **AI支援**: 20回以上の選択後、GNNがあなたの好みを学習し最適な候補を提案

## クイックスタート

### オプション1: 6候補生成システム（推奨・卒業設計用）

```bash
# 1. IECディレクトリに移動
cd IEC/tools

# 2. Generation 0を生成（6候補のブートストラップ）
python generate_generation.py --gen-id 0
# → gen_history/gen_000/population/cand_00～cand_05/ に6候補生成

# 3. Rhinoで6候補を比較・視覚化（オプション）
# 各候補のmesh.objとmesh_inner.objを開く

# 4. トーナメント比較を実行（9マッチ）
python compare_generation.py --gen-id 0
# Swiss-system方式で最良候補を選出
# → 各マッチで rhino/temp/ に自動コピー（固定ファイル名）
# → シンプルなRhinoコマンドを表示（パラメータなし、毎回同じ）

# 5. Generation 1を生成（進化的生成）
python generate_generation.py --gen-id 1
# 勝者とArchive候補を親として新たな6候補を生成

# 6. 継続的な進化ループ
python compare_generation.py --gen-id 1
python generate_generation.py --gen-id 2
...
```

詳細なワークフローは `WORKFLOW.md` を参照してください。

---

### オプション2: 2候補ペアシステム（簡易版・学習用）

```bash
# 1. IECディレクトリに移動
cd IEC/tools

# 2. 初期ペアを生成
python generate_pair.py --init

# 3. ターミナルUIを起動
python iec_terminal_ui.py

# 4. 3Dビューアで gen/A.obj と gen/B.obj を開く
#    - オンライン: https://3dviewer.net/
#    - Rhino、Blender、MeshLabなど

# 5. ターミナルで好みの形態（AまたはB）を選択
```

## ディレクトリ構造

```
IEC/
├── gen_history/             # 【6候補システム】世代アーカイブ（NEW！卒業設計用）
│   ├── gen_000/            # 世代0
│   │   ├── population/     # 候補群
│   │   │   ├── cand_00/   # 候補0
│   │   │   │   ├── meta.json          # 遺伝子型
│   │   │   │   ├── provenance.json    # 生成由来（親・変異情報）
│   │   │   │   ├── mesh.obj           # メッシュ
│   │   │   │   ├── mesh_inner.obj     # 境界除去版
│   │   │   │   └── xy_lines.obj       # XYペア接続線
│   │   │   ├── cand_01/ ... cand_05/  # 候補1～5
│   │   ├── comparison_log.json        # トーナメント結果
│   │   ├── winner_info.json           # 勝者情報
│   │   └── generation_summary.json    # 世代サマリ
│   ├── gen_001/ ... gen_N/
│
├── generation/              # 【6候補システム】パッケージ（NEW！）
│   ├── generation_manager.py  # ディレクトリ管理
│   ├── provenance.py          # 由来追跡
│   ├── archive_manager.py     # Archive選択（品質・多様性スコア）
│   ├── comparison_tournament.py # Swiss-systemトーナメント
│   ├── constraint_checker.py  # 制約チェック（6種類）
│   └── repair.py              # 制約修復
│
├── archive/                 # Archive（親選択用の高品質形態）
│   └── meta_*.json         # 遺伝子型（8個保存）
│
├── log/
│   ├── choices.csv          # 選択履歴（GNN訓練データ）
│   └── iteration_counter.txt # 世代カウンター
│
├── model/
│   └── gnn/                 # GNNモデル（推奨）
│       ├── preference_gnn.pt      # 訓練済みGNN
│       ├── node_scaler.pkl        # ノード特徴スケーラー
│       ├── global_scaler.pkl      # グローバル特徴スケーラー
│       └── training_config.json   # 訓練設定
│
├── pytorch_project/         # GNN実装
│   ├── data/               # グラフ構築・データセット
│   ├── models/             # GNNモデル定義
│   ├── training/           # 訓練スクリプト
│   ├── inference/          # 推論
│   └── .venv/              # PyTorch環境
│
├── tools/
│   ├── generate_generation.py  # 【6候補システム】6候補生成（NEW！）
│   ├── compare_generation.py   # 【6候補システム】トーナメント比較（NEW！）
│   ├── generate_pair.py        # 【2候補システム】ペア生成
│   ├── iec_terminal_ui.py      # ターミナルUI（両システム対応）
│   └── extract_features.py     # 特徴量抽出
│
├── rhino/
│   ├── iec_ui.py, iec_ui_cli.py           # IEC UI
│   ├── import2objs.py, import2objs_cli.py # メッシュインポート
│   ├── import2objs_simple.py              # 簡易インポート（NEW！）
│   ├── visualize_xy_pairs.py              # XYペア可視化
│   ├── temp/                              # トーナメント比較用（自動生成）
│   │   ├── A_mesh.obj        # 候補A メッシュ
│   │   ├── B_mesh.obj        # 候補B メッシュ
│   │   ├── A_lines.obj       # 候補A XYペア線
│   │   └── B_lines.obj       # 候補B XYペア線
│   └── dev/                               # 開発・テスト用（NEW！）
│       ├── test_*.py          # テストスクリプト
│       ├── debug_*.py         # デバッグスクリプト
│       └── analyze_*.py       # 分析スクリプト
│
└── legacy/                  # 旧2候補システム（参照用）
    ├── gen/                # 旧作業ディレクトリ（A/B.obj）
    ├── gen_log/            # 旧世代履歴
    ├── elite/              # 旧エリートアーカイブ
    ├── test_gnn_gen/       # 旧テストデータ
    ├── model/              # 旧LogisticRegressionモデル
    ├── tools/              # 旧訓練スクリプト
    └── README.md           # 旧システム説明
```

---

## システム比較

| 機能 | 2候補ペアシステム | 6候補生成システム |
|-----|-----------------|------------------|
| **候補数/世代** | 2 (A/B) | 6 (cand_00～05) |
| **比較方式** | ペア比較（A vs B） | Swiss-systemトーナメント（9マッチ） |
| **ユーザー負荷** | 低（1回の選択） | 中（9回の選択/世代） |
| **親選択** | 単純な勝者 | Archive + 品質スコア + 多様性スコア |
| **由来追跡** | なし | provenance.json（完全な系譜追跡） |
| **制約チェック** | 基本的 | 6種類の制約 + 自動修復 |
| **出力構造** | フラット（gen/） | 階層化（gen_history/gen_XXX/） |
| **Archive管理** | シンプル | 品質・多様性スコアベース選択 |
| **推奨用途** | 学習・クイックテスト | 本格的な設計探索・卒業設計 |

### 使い分けのガイドライン

- **6候補システム（推奨）**: 卒業設計、研究、本格的な形態探索
- **2候補システム**: システムの学習、クイックテスト、シンプルな比較

詳細なワークフローは `WORKFLOW.md` を参照してください。

---

## 🎲 ランダム探索による形態生成

### 概要

IECシステムは**完全ランダムサンプリング**で広範な設計空間を探索します：

**生成の流れ:**
```
[ランダム生成] × 100候補 → [GNN評価] → 最良の2つを選択 → ユーザー評価
```

### ランダム生成の特徴

**仕組み:**
- 毎世代、100個の候補を完全にランダムに生成
- 親の遺伝子型は参照せず、独立に生成
- 広範な設計空間を効率的に探索

**利点:**
- 局所最適解に陥りにくい
- 多様な形態を常に提示
- GNNと組み合わせることで効率的な探索が可能

### GNN支援による効率化

**20回以上の選択後:**
- 100個のランダム候補を内部で生成
- GNNが全候補をスコアリング
- 能動学習戦略で最適な2つを自動選択
- ユーザーは最終判断のみ（疲労軽減）

**効果:**
- ランダム探索の多様性 + GNNの学習能力
- 人間の評価負荷を大幅削減（100候補→2候補）
- 好みの方向へ高速収束

---

## 🏗️ XY-Pair構造進化

### 概要

**XY-Pair**（XYペア）は、同じ(x,y)座標を共有し、異なるz座標を持つ点のペアです。これにより、建築的な「柱」や「層」のような垂直方向の構造関係を意図的に進化させることができます。

### 主な機能

#### 1. 目標ペア数を指定した初期生成

```bash
# 5つのXYペアを含む初期集団を生成
python generate_pair.py --init --target-pairs 5 --export-xy-lines
```

#### 2. XY構造変異オペレータ

進化過程でXYペアは以下の4つの戦略に従って変異します（各世代で自動選択）：

| 戦略 | 確率 | 動作 |
|------|------|------|
| **PRESERVE_XY** | 30% | XYペアを保持、Z座標のみ変異 |
| **BREAK_XY** | 20% | ペアを破壊（XY座標をシフト） |
| **INCREASE_XY** | 20% | 新しいペアを作成（単独点を揃える） |
| **NONE** | 30% | XY特有の変異なし（通常変異のみ） |

#### 3. XYペアメトリクス（自動計測）

すべての生成されるメタデータに、以下のXYペア構造メトリクスが自動追加されます：

```json
{
  "metadata": {
    "metrics": {
      "xy_pair_count": 6,        // XYペアの数
      "mean_pair_dz": 187.5,     // ペア間Z差の平均（縦方向の厚み）
      "std_pair_dz": 85.3,       // ペア間Z差の標準偏差（ばらつき）
      "max_pair_dz": 400.0,      // 最大Z差
      "min_pair_dz": 58.2        // 最小Z差
    }
  }
}
```

#### 4. XYペア接続線の可視化

XY座標が同じ頂点ペア間の線を別OBJファイルとしてエクスポートできます：

```bash
# XYペア接続線を含めて生成
python generate_pair.py --init --target-pairs 5 --export-xy-lines

# Rhinoで自動インポート
RunPythonScript import2objs.py
```

詳細な座標変換情報は`WORKFLOW.md`を参照してください。

---

## 🤖 AI/GNN選好学習システム ✨

### 概要

**20回以上の選択履歴からGNNがあなたの好みを学習**し、最適な候補を自動提案します。

**2種類のモデル:**
1. **LogisticRegressionモデル** - 軽量・高速（13-17次元の特徴量）
2. **GNNモデル（推奨）** - 高精度（Graph Neural Network）✨

**仕組み:**
1. **選択1-19回**: 通常モード（データ収集）
2. **20回目の選択後**: GNN訓練を実行（初回訓練）
3. **21回目以降**: GNNが100候補から最良の2つを自動選択
4. **5回ごとに再訓練**: 25, 30, 35, 40... 選択後に自動再訓練で精度向上

**効果:**
- 探索効率が大幅に向上（100候補を内部で評価）
- 人間は最終判断のみ（疲労軽減）
- 好みの方向へ高速収束
- 頻繁な再訓練で継続的な精度向上

---

### LogisticRegressionモデル（軽量版）

#### 特徴量（13次元 or 17次元）

| 特徴量 | 説明 |
|--------|------|
| n_points | 点の数 |
| weight_mean/std/min/max | 重みの統計 |
| point_density_mean/std | 点の密度 |
| centrality_mean | 中心からの距離 |
| boundary_proximity | 境界への近さ |
| weight_range | 重みの範囲 |
| **xy_pair_count** | **XYペアの数（垂直構造）** |
| **mean_pair_dz** | **XYペア内のZ差の平均（層の厚み）** |
| **std_pair_dz** | **XYペア内のZ差の分散** |
| volume_mean/max/std/cv | セル体積の統計（オプション）|

#### 訓練方法

```bash
# 基本訓練（体積推定なし、13次元）
python tools/train_preference_model.py log/choices.csv --verbose

# 体積推定あり（17次元、より高精度だが遅い）
python tools/train_preference_model.py log/choices.csv --verbose --include-volume
```

**出力例:**
```
Training accuracy: 0.850
Cross-val accuracy: 0.700 ± 0.150

Feature Importance:
  xy_pair_count       :  +0.520  → Prefer A (more vertical pairs)
  mean_pair_dz        :  +0.340  → Prefer A (thicker layers)
  n_points            :  -0.420  → Prefer B (fewer points)
  ...
```

---

### GNNモデル（推奨・高精度）✨ **NEW!**

#### 概要

**Graph Neural Network（GNN）**を使用した選好学習システム。従来のLogisticRegressionよりも高精度で、点群の幾何学的関係を直接学習します。

**技術:**
- フレームワーク: PyTorch Geometric
- アーキテクチャ: 2層GCN + Global Pooling + MLP
- グラフ表現: kNN (k=20) + 固定点接続
- 損失関数: Pairwise Ranking Loss (Bradley-Terry)

#### LogisticRegressionとの比較

| 項目 | LogisticRegression | GNN（推奨） |
|------|-------------------|------------|
| **精度** | 中程度 (60-70%) | 高精度 (70-85%) |
| **特徴量** | 手作り13-17次元 | 自動学習（点群グラフ） |
| **訓練速度** | 高速（数秒） | 中速（数十秒） |
| **依存関係** | scikit-learn | PyTorch, PyTorch Geometric |
| **小データ対応** | 良好 | 良好（dropout, early stopping） |
| **幾何学的理解** | 限定的 | 深い（kNN関係を直接学習） |

**推奨:**
- **初回訓練**: GNN（高精度）
- **軽量・高速が必要**: LogisticRegression

#### グラフ構造

**ノード特徴（4次元）:**
- [x, y, z, weight] - 正規化済み

**エッジ:**
- kNN (k=20) - 最近傍20点との接続
- 固定点接続 - 全ノードから固定点（indices 0, 1）への双方向エッジ
- 重複エッジは距離最小化で統合

**グローバル特徴（6次元）:**
- [n_points, xy_pair_count, mean_pair_dz, std_pair_dz, max_pair_dz, min_pair_dz]

**固定点（cell0, cell1）:**
- cell0: [400, 350, 200] - XY平面上部基準点
- cell1: [400, 350, -50] - XY平面下部基準点
- すべてのノードと接続され、XY平面との関係を明示的にモデル化

**GNNモデル構造:**
```
Input Graph → GCN(4→64) → ReLU → GCN(64→64) → ReLU
  → GlobalMeanPool → Concat(64 + 6) → MLP(70→32→1) → Sigmoid → Score [0,1]
```

#### 訓練方法

```bash
# GNN訓練（venv内のPythonを使用）
cd IEC
pytorch_project/.venv/bin/python pytorch_project/training/train_pref_gnn.py log/choices.csv --verbose
```

**訓練パラメータ（デフォルト）:**
- Epochs: 100（early stopping: patience=20）
- Batch size: 4
- Learning rate: 0.001
- Hidden dim: 64
- Dropout: 0.3
- k-neighbors: 20
- Fixed point indices: [0, 1]

**出力例:**
```
============================================================
  GNN PREFERENCE MODEL TRAINING
============================================================

Device: cpu

Step 1: Preparing GraphBuilder...
  k-neighbors: 20
  Fixed point indices: [0, 1]

Step 2: Loading preference dataset...
  PreferenceDataset: 28 pairs loaded
  Fitting scalers on all data...
  Train: 23 pairs
  Val:   5 pairs

Step 3: Building GNN model...
  Hidden dim: 64
  Dropout: 0.3
  Parameters: 6785

Step 4: Training...
Epoch   1/100: train_loss=0.6931, val_loss=0.6925, val_acc=0.600
Epoch  10/100: train_loss=0.5234, val_loss=0.5489, val_acc=0.650
...
Early stopping at epoch 35

Step 5: Saving model artifacts...
  Model saved to: model/gnn/
    - preference_gnn.pt
    - node_scaler.pkl
    - global_scaler.pkl
    - training_config.json

============================================================
TRAINING COMPLETE
============================================================

Best validation loss: 0.6922
Best validation accuracy: 0.600
```

#### 使用方法（自動）

ターミナルUIは自動的にGNNモデルを検出して使用します：

```bash
python tools/iec_terminal_ui.py

# 出力:
#   🧠 GNN Mode: ENABLED
#      GNN will suggest best candidates from 100 options
#      (Using advanced Graph Neural Network model)
```

**優先順位:**
1. GNNモデルが存在 → `🧠 GNN Mode`
2. LogisticRegressionモデルのみ → `🤖 AI Mode`
3. モデルなし → `👤 Traditional Mode`

#### 手動での使用

```bash
# GNN支援モードで生成
python tools/generate_pair.py --parent gen/meta_A.json --use-gnn-model

# カスタムパラメータ
python tools/generate_pair.py --parent gen/meta_A.json \
  --use-gnn-model \
  --gnn-model-dir model/gnn \
  --candidates 100 \
  --strategy top_and_uncertain
```

---

### Active Learning戦略

AI/GNN支援モード時の候補選択戦略を選べます：

| 戦略 | 説明 | 推奨フェーズ |
|------|------|------------|
| `hybrid_active` | **A: トップスコア + B: Top-20多様性 / 不確実性（5世代ごと）**（**デフォルト**） | 全フェーズ |
| `top_2` | 最良の2つ（純粋な搾取） | 探索後期（収束重視） |
| `top_and_uncertain` | 最良 + 最も不確実 | 探索初期〜中期 |
| `diverse` | 最良 + 最も異なる（多様性重視） | 探索初期 |
| `expected_improvement` | 最良 + 改善期待値が高い | 探索中期 |
| `uncertainty_sampling` | 最も不確実な2つ（純粋な学習） | データ収集 |

**hybrid_active戦略の詳細:**
- **A案**: 常にトップスコア候補（exploitation）
- **B案**:
  - 通常（世代0, 1, 2, 3, 4, 6, 7...）: Top-20候補からA案と最も異なる候補を選択（メタ特徴L2距離）
  - 5世代ごと（世代5, 10, 15, 20...）: 最大不確実性候補（スコアが0.5に最も近い）
- **効果**: 多様性確保（exploration）と収束（exploitation）のバランスが自動調整される

```bash
# 例: hybrid_active戦略（デフォルト）
python tools/generate_pair.py --parent gen/meta_A.json --use-gnn-model --strategy hybrid_active

# 例: 多様性重視（レガシー）
python tools/generate_pair.py --parent gen/meta_A.json --use-gnn-model --strategy diverse
```

---

### モデル再訓練

選択を重ねるごとに再訓練すると精度が向上：

```bash
# GNN再訓練（ターミナルUIが自動的にプロンプト表示）
pytorch_project/.venv/bin/python pytorch_project/training/train_pref_gnn.py log/choices.csv --verbose

# LogisticRegression再訓練
python tools/train_preference_model.py log/choices.csv --verbose
```

**自動再訓練スケジュール:**
- **20回選択後**: 初回訓練（必須）← ターミナルUIが自動プロンプト
- **25回選択後**: 再訓練推奨 ← 自動プロンプト
- **30回選択後**: 再訓練推奨 ← 自動プロンプト
- **以降5回ごと**: 35, 40, 45, 50... ← 自動プロンプト

**効果:**
- 頻繁な再訓練で継続的な精度向上
- 新しい選択データを即座に反映
- 好みの変化に柔軟に対応

---

## 遺伝子型とパラメータ

### 遺伝子型の構造

各形態は以下のデータで定義されます（建築スケール: mm単位）：

```json
{
  "points": [
    {
      "position": [x, y, z],  // mm単位
      "weight": w              // mm単位
    },
    ...
  ],
  "metadata": {
    "iteration": 0,
    "parent_hash": null,
    "n_points": 10,
    "hash": "def456",
    "metrics": {
      "xy_pair_count": 6,
      "mean_pair_dz": 187.5,
      ...
    }
  }
}
```

### バウンディングボックス（固定）

**建築スケール: 800mm × 700mm × 400mm**

すべての形態はこのボリューム内で生成されます：
- X軸: 0 - 800mm
- Y軸: 0 - 700mm
- Z軸: 0 - 400mm

### 変異パラメータ

デフォルト設定（`generate_pair.py`で変更可能）：

| パラメータ | デフォルト | 説明 |
|-----------|----------|------|
| `n_points` | 10 | 初期点数 |
| `pos_mutation_sigma` | 30.0 mm | 位置摂動の標準偏差 |
| `weight_mutation_sigma` | 10.0 | 重み摂動の標準偏差 |
| `add_point_prob` | 0.1 | 点追加の確率 |
| `remove_point_prob` | 0.1 | 点削除の確率 |
| `bounds` | [0,0,0] - [800,700,400] mm | バウンディングボックス（固定） |
| `weight_range` | 10 - 100 mm | 重みの範囲 |

### パラメータのカスタマイズ

```bash
# より多くの点、より大きな変異（探索フェーズ）
python generate_pair.py --init --n-points 15 --pos-sigma 50.0 --weight-sigma 15.0

# より少ない点、より小さな変異（微調整フェーズ）
python generate_pair.py --parent gen/meta_A.json --n-points 8 --pos-sigma 10.0 --weight-sigma 5.0
```

---

## 技術詳細

### Power Diagram（重み付きVoronoi図）

- 各点に位置（x, y, z）と重み（w）を持つ
- 重みが大きいほど、その点の影響範囲が広がる
- 通常のVoronoi図の一般化

### OBJエクスポート

- Y-up座標系からZ-up座標系への変換（Rhino対応）
- 各Voronoiセルをポリゴンメッシュとして出力
- XYペア線の座標変換: `(x, y, z) → (x, z, -y)`

### 選択履歴の記録

すべての選択は `log/choices.csv` に記録されます：

```csv
timestamp,iteration,selected,parent_hash,hash_A,hash_B,n_points_A,n_points_B
2025-12-21T10:30:00,0,A,null,4de3c46b,d120849b,10,10
2025-12-21T10:31:23,1,B,4de3c46b,47b18e8e,9abb937e,9,10
```

---

## トラブルシューティング

### "No module named 'LaguerreVoronoi'" エラー

`generate_pair.py` は親ディレクトリの `LaguerreVoronoi.py` を参照します。
プロジェクト構造を維持してください：

```
py_code/
├── LaguerreVoronoi.py
└── IEC/
    └── tools/
        └── generate_pair.py
```

### GNN関連エラー

**"No module named 'torch'":**
```bash
# GNN訓練は専用のvenvを使用
pytorch_project/.venv/bin/python pytorch_project/training/train_pref_gnn.py log/choices.csv --verbose
```

**"GNN model not found":**
```bash
# GNN訓練を実行
pytorch_project/.venv/bin/python pytorch_project/training/train_pref_gnn.py log/choices.csv --verbose
```

### AI/GNN支援モードが有効化されない

**原因:**
1. モデルファイルが存在しない
2. 選択回数が10回未満

**解決:**
```bash
# 選択回数を確認
wc -l log/choices.csv
# → 11行（ヘッダー1行 + 10回選択）なら10回完了

# モデル訓練
pytorch_project/.venv/bin/python pytorch_project/training/train_pref_gnn.py log/choices.csv --verbose
# または
python tools/train_preference_model.py log/choices.csv --verbose
```

### 精度が低い

**原因:** データ不足（10回では不十分）

**解決:**
- 20-30回以上選択してから再訓練
```bash
pytorch_project/.venv/bin/python pytorch_project/training/train_pref_gnn.py log/choices.csv --verbose
```

---

## セッション管理とベストプラクティス

### 推奨セッション長

- 1セッション: 10-15世代
- 理由: 人間の評価疲れを考慮（15世代で警告表示）

### エリートアーカイブ

ターミナルUIで 'S' キーを押してお気に入りを保存：

```bash
python iec_terminal_ui.py
# → Sキーで保存
```

保存先: `IEC/elite/elite_<hash>.json`

### 複数セッションに分ける

```bash
# セッション1（初期探索）
python iec_terminal_ui.py  # → 10回選択

# モデル訓練
pytorch_project/.venv/bin/python pytorch_project/training/train_pref_gnn.py log/choices.csv --verbose

# セッション2（AI/GNN支援探索）
python iec_terminal_ui.py  # → 10回選択

# 再訓練
pytorch_project/.venv/bin/python pytorch_project/training/train_pref_gnn.py log/choices.csv --verbose

# セッション3（収束）
python iec_terminal_ui.py  # → 5-10回選択
```

---

## 依存関係

### Python（計算側）

**基本:**
```
numpy
scipy
```

**AI支援モード（LogisticRegression）:**
```
scikit-learn
pandas
```

**GNN支援モード:**
```
torch
torch-geometric
pandas
scikit-learn
```

GNN環境は `pytorch_project/.venv/` に独立して構築されています。

### Rhino（オプション）

- Rhino 7以降推奨
- Python 3対応
- `rhinoscriptsyntax` モジュール

**注**: ターミナルUIを使用する場合、Rhinoは不要です。

---

## 開発・テストツール

### 自動デモモード

システム全体の動作をテストする自動デモ：

```bash
cd IEC/tools
python demo_evolution.py 5  # 5世代を自動生成
```

ランダムな選択で指定世代数を自動的に進化させ、ログを記録します。

### GNNモデルテスト

```bash
# 訓練済みGNNモデルをテスト
cd IEC
pytorch_project/.venv/bin/python pytorch_project/test_model.py
```

---

## 🏛️ 6候補生成システム（卒業設計用）**NEW!**

### 概要

**卒業設計での検証可能性を重視した6候補同時生成システム**です。Phase 1として生成インフラを実装済み、Phase 2で比較ループを追加予定です。

**特徴:**
- **完全な由来追跡（Provenance）**: 各候補の生成方法、親、修復履歴を記録
- **制約チェックと自動修復**: 6種類の制約を自動的にチェック・修復
- **世代ごとのディレクトリ保存**: gen_history/gen_XXX/ で完全な履歴管理
- **GA4 + Random2構成**: 変異2種、交叉2種、ランダム2種で多様性確保

### 6候補の構成（固定テンプレート）

| Candidate | Origin Type | Parent(s) | Purpose |
|-----------|-------------|-----------|---------|
| **cand_00** | mutate_weak | recent_winner | Exploitation（漸進改善） |
| **cand_01** | mutate_strong | recent_winner | Exploration（局所脱出） |
| **cand_02** | crossover_winner_archive | recent_winner × archive_winner | Hybrid |
| **cand_03** | crossover_archive_archive | archive_winner_A × archive_winner_B | Pure archive mixing |
| **cand_04** | random_baseline | None | Baseline random |
| **cand_05** | random_extreme | None | Extreme random |

### Provenance Tracking（由来追跡）

各候補は完全な生成履歴を保持：

```json
{
  "cand_id": "cand_00",
  "gen_id": 1,
  "origin_type": "mutate_weak",
  "parents": ["gen_000/cand_03"],
  "operator_config": {
    "mutation_mode": "weak",
    "xy_strategy": "PRESERVE_XY",
    "sigma_multiplier": 0.5
  },
  "random_seed": 1234567890,
  "repair_log": [
    {"issue": "bbox_violation", "action": "clipped_3_points", "success": true}
  ],
  "repair_iterations": 1,
  "generation_success": true
}
```

### Constraint & Repair System

**6種類の制約:**
1. 固定点の存在（indices 0, 1）
2. バウンディングボックス準拠
3. 除外ゾーン回避
4. 点数目標（±2許容）
5. XYペア目標（±3許容）
6. 重み範囲準拠

**自動修復（最大10回）:**
- bbox外点 → クリッピング
- 除外ゾーン侵入 → 再配置
- 点数不足/超過 → 追加/削除
- XYペア不足/超過 → 作成/破壊
- 重み範囲外 → クリッピング

修復失敗時は異なるseedで再生成（最大3回試行）。

### 使用方法（完全版）

**Step 1: Generation 0を生成（Phase 1）**
```bash
cd IEC/tools
python generate_generation.py --gen-id 0 --n-points 100 --target-pairs 40
```

**Step 2: トーナメント比較を実行（Phase 3）**
```bash
python compare_generation.py --gen-id 0
# → 9マッチの比較（Swiss-system）を実行
# → 各マッチで IEC/rhino/temp/ に自動コピー（固定ファイル名）
# → シンプルなRhinoコマンドを表示（パラメータなし）
# → Rhinoでコマンド実行 → 候補比較 → 勝者選択

# Rhino可視化が不要な場合
python compare_generation.py --gen-id 0 --no-rhino
```

**シンプルなRhino可視化ワークフロー:**
- **固定フォルダ**: `IEC/rhino/temp/` に毎回同じ場所にコピー
- **固定ファイル名**: `A_mesh.obj`, `B_mesh.obj`, `A_lines.obj`, `B_lines.obj`
- **シンプルなコマンド**: 毎回同じコマンドをコピー&ペースト
  ```
  _-RunPythonScript "\\wsl$\Ubuntu\home\shint\py_code\IEC\rhino\import2objs.py"
  ```
- **自動上書き**: 次のマッチで自動的にファイル更新（クリーンアップ不要）

**Step 3: 比較結果を確認（Phase 3）**
```bash
cat ../gen_history/gen_000/comparison_log.json | jq .winner
cat ../gen_history/gen_000/winner_info.json
```

**Step 4: Generation 1を生成（Phase 2）**
```bash
python generate_generation.py --gen-id 1 --n-points 100 --target-pairs 40
# → 実際の勝者が親として使用される
# → コンソールに "✓ Using actual winner from comparison: cand_XX" が表示
```

**Step 5: 継続的な進化ループ**
```bash
python compare_generation.py --gen-id 1
python generate_generation.py --gen-id 2
# 以降繰り返し...
```

**実装完了（Phase 1-3）:**
- ✅ 6候補同時生成（Phase 1）
- ✅ 進化的生成（変異・交叉）（Phase 2）
- ✅ Swiss-systemトーナメント（9マッチ）（Phase 3）
- ✅ Archive管理拡張（win_count、quality_score、diversity_score）（Phase 3）
- ✅ 実際の勝者ベース親選択（Phase 3）
- ✅ Rhino CLI統合（Phase 3）
- ✅ **シンプルなRhino可視化ワークフロー** ✨ **NEW!**
  - 固定フォルダ（`IEC/rhino/temp/`）に自動コピー
  - 固定ファイル名（A_mesh.obj, B_mesh.obj, A_lines.obj, B_lines.obj）
  - パラメータなしのシンプルなRhinoコマンド（毎回同じ）
  - 自動上書き（クリーンアップ不要）

### Generation Summary

各世代のサマリが自動生成：

```json
{
  "gen_id": 0,
  "population_size": 6,
  "invalid_count": 0,
  "candidate_origins": {
    "mutate_weak": 1,
    "mutate_strong": 1,
    "crossover": 2,
    "random": 2
  },
  "population_metrics": {
    "xy_pair_count": {"mean": 20.5, "std": 3.2},
    "mean_pair_dz": {"mean": 180.0, "std": 25.0},
    "n_points": {"mean": 122.0, "std": 2.0}
  },
  "diversity_score": 0.85
}
```

### 卒業設計での利点

- **完全な検証可能性**: すべての候補の生成過程を追跡
- **再現性**: random_seedで完全再現可能
- **多様性の定量化**: diversity_scoreで集団の多様性を測定
- **制約違反の記録**: repair_logで修復過程を記録

---

## 今後の拡張

### 実装済み ✅
- [x] A/B差別化変異戦略
- [x] 適応的変異強度（アニーリング）
- [x] セッション管理 + エリートアーカイブ
- [x] 交叉（Crossover）機能
- [x] XY-Pair構造進化
- [x] 選好学習（LogisticRegression）
- [x] **GNN選好学習（Graph Neural Network）** ✨
- [x] Active Learning（5種類の選択戦略）
- [x] **6候補生成システム（Phase 1: 生成インフラ）**
  - Provenance tracking
  - Constraint checking & repair
  - Generation history management
- [x] **6候補生成システム（Phase 2: 進化的生成）**
  - Parent selection (recent_winner, archive diversity)
  - Mutation (weak/strong)
  - Crossover (winner×archive, archive×archive)
  - Generation 1+ with GA4 + Random2
- [x] **6候補生成システム（Phase 3: トーナメント比較）** ✨ **NEW!**
  - Swiss-system tournament (3 rounds, 9 matches)
  - Archive management extensions (win_count, quality_score, diversity_score)
  - Rhino CLI integration (import2objs_cli.py)
  - Actual winner-based parent selection
  - **Simplified Rhino visualization workflow** ✨ **LATEST!**
    - Fixed folder location (IEC/rhino/temp/)
    - Fixed file names (A_mesh.obj, B_mesh.obj, A_lines.obj, B_lines.obj)
    - Parameter-free Rhino command (same every match)
    - Auto-overwrite (no cleanup needed)

### 今後の検討
- [ ] 定期的ランダム注入（局所最適回避）
- [ ] 選択パターン分析スクリプト
- [ ] 正確な体積計算（現在は推定）
- [ ] マルチビューレンダリング
- [ ] 多目的最適化対応
- [ ] WebベースのUIオプション

---

## ライセンス

このプロジェクトは教育・研究目的で開発されています。

## 参考文献

- Aurenhammer, F. (1987). Power Diagrams: Properties, Algorithms and Applications
- Takagi, H. (2001). Interactive Evolutionary Computation
- Shiffman, D. - The Nature of Code (Genetic Algorithms chapter)
- Kipf, T. N., & Welling, M. (2016). Semi-supervised classification with graph convolutional networks
- Burges, C., et al. (2005). Learning to rank using gradient descent
