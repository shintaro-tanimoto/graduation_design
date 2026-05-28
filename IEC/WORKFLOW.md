# 6候補生成システム ワークフロー - 卒業設計用

このドキュメントは、6候補同時生成システムを使った形態生成の完全な手順を説明します。

---

## システム概要

**6候補生成システム** - 検証可能性を重視した建築形態生成システム

### 主な特徴

- **6候補同時生成**: 1世代につき6つの候補を同時に生成
- **完全なProvenance追跡**: 各候補の生成由来、親、修復履歴を記録
- **自動制約チェック**: 6種類の制約を自動検証
- **自動修復機能**: 制約違反を自動的に修復（最大10回試行）
- **Swiss-systemトーナメント**: 効率的な6候補比較（9マッチ）
- **Archive管理拡張**: 勝者カウント、品質スコア、多様性スコア追跡
- **再現性**: すべての候補にrandom_seedを記録、完全再現可能

### 実装状況

- ✅ **Phase 1**: 生成インフラ（完成）- Generation 0の生成が可能
- ✅ **Phase 2**: 進化的生成（完成）- Generation 1+の遺伝的操作
- ✅ **Phase 3**: トーナメント比較（完成）- Swiss-system比較とArchive管理

---

## 前提条件

### 必要な環境

```bash
# Pythonライブラリの確認
python3 -c "import numpy, scipy; print('OK')"
# → "OK" が表示されればOK
```

### ディレクトリ構造

```
IEC/
├── gen_history/       # 世代履歴（6候補システム専用）
│   ├── gen_000/
│   │   ├── population/
│   │   │   ├── cand_00/
│   │   │   │   ├── meta.json          # 遺伝子型
│   │   │   │   ├── provenance.json    # 生成由来・修復履歴
│   │   │   │   ├── mesh.obj           # Laguerre Voronoiメッシュ
│   │   │   │   ├── mesh_inner.obj     # 境界除去版
│   │   │   │   └── xy_lines.obj       # XYペア可視化
│   │   │   ├── cand_01/ ... cand_05/
│   │   ├── comparison_log.json    # トーナメント結果（Phase 3）
│   │   ├── winner_info.json       # 勝者情報（Phase 3）
│   │   └── gen_summary.json       # 世代統計サマリ
│   ├── gen_001/
│   └── ...
├── generation/        # 6候補生成システムモジュール
│   ├── __init__.py
│   ├── generation_manager.py      # 世代ディレクトリ管理
│   ├── provenance.py              # Provenance追跡
│   ├── constraint_checker.py      # 制約チェック
│   ├── repair.py                  # 自動修復
│   ├── archive_manager.py         # Archive管理拡張（Phase 3）
│   └── comparison_tournament.py   # Swiss-systemトーナメント（Phase 3）
├── tools/
│   ├── generate_generation.py     # 6候補生成メインスクリプト
│   ├── compare_generation.py      # トーナメント比較スクリプト（Phase 3）
│   ├── generate_pair.py           # 既存: 2候補生成（従来システム）
│   └── ...
├── rhino/
│   ├── import2objs.py             # Rhino統合（従来）
│   └── import2objs_cli.py         # Rhino CLI版（Phase 3）
├── archive/           # 過去の遺伝子型保存（拡張メタデータ付き）
├── gen/               # 現在の候補ペア（従来システム用）
├── log/               # 選択履歴（従来システム用）
└── elite/             # お気に入り保存
```

---

## Step 1: Generation 0（ブートストラップ）の生成

### 1.1: 初回生成コマンド

```bash
cd IEC/tools
python generate_generation.py --gen-id 0 --n-points 100 --target-pairs 40
```

**パラメータ説明:**
- `--gen-id 0`: Generation 0（ブートストラップ）を生成
- `--n-points 100`: 各候補の点数（固定点2つを除く）
- `--target-pairs 40`: XYペア構造の目標数

### 1.2: 生成される構造

```
IEC/gen_history/gen_000/
├── population/
│   ├── cand_00/     # 候補0（random_baseline）
│   ├── cand_01/     # 候補1（random_baseline）
│   ├── cand_02/     # 候補2（random_baseline）
│   ├── cand_03/     # 候補3（random_baseline）
│   ├── cand_04/     # 候補4（random_extreme - 高XYペア）
│   └── cand_05/     # 候補5（random_extreme - 高XYペア）
└── gen_summary.json
```

**Generation 0の候補構成:**
- **cand_00〜03**: `random_baseline` - 標準パラメータでランダム生成
- **cand_04〜05**: `random_extreme` - 極端なパラメータで生成
  - gen_id % 4 でバリエーション変化
  - 例: gen_id=0 → 高XYペア（target_pairs=30）

### 1.3: 生成結果の確認

**コンソール出力例:**
```
============================================================
  6-CANDIDATE GENERATION SYSTEM
============================================================
  Generation ID: 0
  n_points: 100 (+ 2 fixed)
  target_pairs: 40
  Base directory: /home/shint/py_code/IEC/gen_history
============================================================

============================================================
  GENERATION 0: Bootstrap (All Random)
============================================================

Generating cand_00...
  Initial: 102 points, 5 XY-pairs
  ⚠ Found 3 constraint violations, attempting repair...
  ✅ Repair successful (6 actions)

Generating cand_01...
  Initial: 105 points, 8 XY-pairs
  ✅ All constraints satisfied

...

============================================================
  GENERATION SUMMARY
============================================================
{
  "gen_id": 0,
  "population_size": 6,
  "invalid_count": 0,
  "candidate_origins": {
    "random_baseline": 4,
    "random_extreme": 2
  },
  "population_metrics": {
    "xy_pair_count": {
      "mean": 10.5,
      "std": 8.06,
      "min": 4,
      "max": 25
    },
    ...
  },
  "diversity_score": 15.16
}
```

---

## Step 2: トーナメント比較（Phase 3）

### 2.1: 比較ループの実行

```bash
cd IEC/tools
python compare_generation.py --gen-id 0
```

**パラメータ説明:**
- `--gen-id 0`: Generation 0の候補を比較
- `--no-rhino`: Rhino可視化を無効化（デフォルトは有効）
- `--rounds 3`: トーナメントラウンド数（デフォルト: 3）

**Rhino可視化について:**
- デフォルトで有効（各マッチでファイルコピー＋コマンド表示）
- `IEC/rhino/temp/` に固定ファイル名でコピー
- 毎回同じシンプルなコマンドを実行するだけ

### 2.2: Swiss-systemトーナメント

**3ラウンド、9マッチの効率的な比較:**

```
Round 1: ランダムペアリング（3マッチ）
  Match 1: cand_00 vs cand_01
  Match 2: cand_02 vs cand_03
  Match 3: cand_04 vs cand_05

Round 2: スコアベースペアリング（3マッチ）
  高スコア同士、低スコア同士をマッチング
  Match 4: 1位 vs 2位
  Match 5: 3位 vs 4位
  Match 6: 5位 vs 6位

Round 3: 最終ランキング（3マッチ）
  更新されたスコアでペアリング
  Match 7-9: 同様のスコアベース

最終結果: 最高スコアの候補が勝者
```

### 2.3: 比較の実行例

```
============================================================
  TOURNAMENT COMPARISON - Generation 0
  Swiss-system: 3 rounds, 9 total matches
============================================================

--- Match 1/3 (Round 1) ---

  CAND_00:
    Origin: random_baseline
    Points: 102
    XY Pairs: 35
    Pair ΔZ: 147.2 ± 93.4 mm
    Hash: 09707c91...

  CAND_01:
    Origin: random_baseline
    Points: 98
    XY Pairs: 15
    Pair ΔZ: 215.6 ± 51.2 mm
    Hash: 6c99416d...

  Rhino Visualization:
  ----------------------------------------------------------
  Files copied to: /home/shint/py_code/IEC/rhino/temp
  Files copied: 4/4

  Copy this command into Rhino:
  ==========================================================
  _-RunPythonScript "\\wsl$\Ubuntu\home\shint\py_code\IEC\rhino\import2objs.py"
  ==========================================================

  Note: Files are copied with fixed names:
    - Candidate A: A_mesh.obj, A_lines.obj
    - Candidate B: B_mesh.obj, B_lines.obj

  Choose winner (A or B): A
  ✓ Winner: A (cand_00)

  Current Standings:
    1. cand_00: 1 points
    2. cand_01: 0 points
    ...
```

**シンプルなRhino可視化ワークフロー:**
- **固定フォルダ**: `IEC/rhino/temp/` に毎回同じ場所にコピー
- **固定ファイル名**: `A_mesh.obj`, `B_mesh.obj`, `A_lines.obj`, `B_lines.obj`
- **シンプルなコマンド**: パラメータなし、毎回同じコマンドをコピー&ペースト
- **自動上書き**: 次のマッチで自動的にファイル更新（クリーンアップ不要）

### 2.4: 比較結果の保存

**自動生成されるファイル:**

1. **comparison_log.json**（トーナメント完全記録）
```json
{
  "gen_id": 0,
  "timestamp": "2025-12-31T12:00:00",
  "n_rounds": 3,
  "total_matches": 9,
  "match_history": [
    {
      "round": 0,
      "match_id": 0,
      "cand_a": "cand_00",
      "cand_b": "cand_01",
      "winner": "cand_00",
      "timestamp": "2025-12-31T12:05:00"
    }
  ],
  "final_scores": {
    "cand_00": 3,
    "cand_01": 2,
    "cand_02": 2,
    "cand_03": 1,
    "cand_04": 1,
    "cand_05": 0
  },
  "winner": "cand_00"
}
```

2. **winner_info.json**（勝者情報）
```json
{
  "gen_id": 0,
  "winner_cand_id": "cand_00",
  "final_score": 3,
  "total_rounds": 3,
  "genotype_hash": "09707c91",
  "n_points": 102,
  "xy_pair_count": 35,
  "provenance_origin": "random_baseline"
}
```

---

## Step 3: Archive更新（Phase 3）

### 3.1: 自動Archive更新

トーナメント終了後、以下が自動実行されます:

1. **全6候補のArchive追加**（新規の場合のみ）
2. **勝者のwin_count更新**
3. **全候補のcomparison_count更新**
4. **quality_score再計算**

### 3.2: Archive拡張メタデータ

```json
{
  "metadata": {
    "archive_metadata": {
      "win_count": 1,
      "comparison_count": 3,
      "quality_score": 0.333,
      "diversity_score": 45.6,
      "last_win_gen": 0,
      "first_archived": "2025-12-31T10:00:00",
      "last_compared": "2025-12-31T12:00:00"
    }
  }
}
```

**メタデータの意味:**
- `win_count`: この候補が勝利した回数
- `comparison_count`: 比較に登場した回数
- `quality_score`: win_count / comparison_count（勝率）
- `diversity_score`: 全Archive候補との平均L2距離
- `last_win_gen`: 最後に勝利した世代ID

### 3.3: Archive確認

```bash
# Archive候補の勝者カウント確認
cat archive/meta_*.json | jq '.metadata.archive_metadata.win_count' | sort -rn | head -5

# 品質スコア確認
cat archive/meta_*.json | jq '.metadata.archive_metadata.quality_score' | sort -rn | head -5
```

---

## Step 4: Generation 1+の生成（Phase 2）

### 4.1: 進化的生成の実行

```bash
python generate_generation.py --gen-id 1 --n-points 100 --target-pairs 40
```

**親選択の改善（Phase 3）:**
- `select_recent_winner()`: `comparison_log.json`から**実際の勝者**を使用
- フォールバック: ログがない場合はcand_00

**コンソール出力例:**
```
Parent Selection:
  ✓ Using actual winner from comparison: cand_00
  ✓ recent_winner: gen_000/cand_00 (102 points)
  ✓ archive_winner (diversity): archive/meta_789a9a51.json
  ✓ archive_winner_A: archive/meta_a3ee5535.json
  ✓ archive_winner_B: archive/meta_926a9122.json
```

### 4.2: Generation 1+の候補構成

| Candidate | Origin Type | Parent(s) | 実装内容 |
|-----------|-------------|-----------|---------|
| **cand_00** | mutate_weak | recent_winner | sigma × 0.5、PRESERVE_XY |
| **cand_01** | mutate_strong | recent_winner | sigma × 1.5、BREAK_XY |
| **cand_02** | crossover_winner_archive | recent_winner × archive | blend交叉、60/40比率 |
| **cand_03** | crossover_archive_archive | archive × archive | uniform交叉、50/50 |
| **cand_04** | random_baseline | None | ベースラインランダム |
| **cand_05** | random_extreme | None | 極端ランダム（4バリアント） |

**遺伝的操作の詳細:**

- **mutate_weak**: 小さな変異でexploitation（漸進改善）
- **mutate_strong**: 大きな変異でexploration（局所脱出）
- **crossover**: 親の良い特徴を組み合わせ
- **random**: 設計空間全体の探索を維持

---

## Step 5: 継続的な進化ループ

### 5.1: 完全なワークフロー

```bash
# === Generation 0: ブートストラップ ===
python generate_generation.py --gen-id 0 --n-points 100 --target-pairs 40
python compare_generation.py --gen-id 0

# === Generation 1: 進化開始 ===
python generate_generation.py --gen-id 1 --n-points 100 --target-pairs 40
python compare_generation.py --gen-id 1

# === Generation 2: 継続 ===
python generate_generation.py --gen-id 2 --n-points 100 --target-pairs 40
python compare_generation.py --gen-id 2

# === 以降継続... ===
```

### 5.2: Rhinoでの確認（推奨）

**比較時にRhinoを使用:**

```bash
# Rhino表示有効（デフォルト）
python compare_generation.py --gen-id 0
```

各マッチでOBJファイルパスが表示されます:
```
Candidate A mesh: gen_history/gen_000/population/cand_00/mesh.obj
Candidate B mesh: gen_history/gen_000/population/cand_01/mesh.obj
Candidate A inner: gen_history/gen_000/population/cand_00/mesh_inner.obj
Candidate B inner: gen_history/gen_000/population/cand_01/mesh_inner.obj
```

**手動でRhinoにインポート:**
1. Rhino 7以降を開く
2. `_-Import` コマンドで上記パスを指定
3. 2つのメッシュを比較
4. ターミナルで`A`または`B`を選択

---

## Step 6: 多様性スコアの計算

### 6.1: Archive多様性スコアの更新

```bash
python -c "
from generation.archive_manager import ArchiveManager
mgr = ArchiveManager('archive')
mgr.compute_diversity_scores()
print('✓ Diversity scores updated')
"
```

### 6.2: 多様性スコアの確認

```bash
# Archive候補の多様性スコア確認
cat archive/meta_*.json | jq '.metadata.archive_metadata.diversity_score' | sort -rn | head -5
```

**高い多様性スコア = 他候補と異なる特徴を持つ**

---

## 制約と自動修復の理解

### 6種類の制約

システムは以下の制約を自動的にチェックします:

1. **Fixed Points（固定点）**
   - 必須条件: indices 0, 1に固定点が存在
   - cell0: `[400, 350, 200]` (XY平面上部)
   - cell1: `[400, 350, -50]` (XY平面下部)

2. **Bounding Box（境界ボックス）**
   - すべての点が`[bounds_min, bounds_max]`内に存在
   - デフォルト: `[0, 0, -50]` 〜 `[800, 700, 700]`

3. **Exclusion Zone（除外ゾーン）**
   - 指定領域内に点が存在しない
   - デフォルト: `X[200-600], Y[200-500], Z[0-300]`

4. **Point Count（点数）**
   - 目標点数 ± 2の許容範囲内
   - 例: `n_points=100` → 98〜102点

5. **Target Pairs（XYペア数）**
   - 目標XYペア数 ± 3の許容範囲内
   - 例: `target_pairs=40` → 37〜43ペア

6. **Weight Range（重み範囲）**
   - すべての重みが`[weight_min, weight_max]`内
   - デフォルト: `[10, 50]`

### 自動修復の流れ

```
候補生成 → 制約チェック → 違反あり？
                              ↓ YES
                    修復関数実行 → 再チェック
                              ↓
                    最大10回試行 → 成功？
                                    ↓ NO
                          新しいseedで再生成（最大3回）
```

**修復アクション:**
- `bbox_violation` → 点をクリッピング
- `exclusion_violation` → 点を移動または再サンプリング
- `n_points_mismatch` → 点を追加または削除
- `target_pairs_mismatch` → XYペアを作成または破壊
- `weight_violation` → 重みをクリッピング

---

## 卒業設計での活用

### 検証可能性の確保

**すべての履歴を確認:**
```bash
# 世代ディレクトリ一覧
ls -la gen_history/

# 特定候補の生成過程を追跡
cat gen_history/gen_000/population/cand_00/provenance.json

# トーナメント結果を確認
cat gen_history/gen_000/comparison_log.json

# 勝者情報を確認
cat gen_history/gen_000/winner_info.json

# 世代ごとの多様性を比較
for i in 000 001 002; do
  echo "Generation $i:"
  jq '.diversity_score' gen_history/gen_$i/gen_summary.json
done
```

### Archive分析

**品質ベースの分析:**
```bash
# 最も勝率の高い候補Top 5
for f in archive/meta_*.json; do
  hash=$(basename $f .json | sed 's/meta_//')
  quality=$(jq -r '.metadata.archive_metadata.quality_score // 0' $f)
  win=$(jq -r '.metadata.archive_metadata.win_count // 0' $f)
  echo "$quality $win $hash"
done | sort -rn | head -5
```

**多様性ベースの分析:**
```bash
# 最も多様な候補Top 5
for f in archive/meta_*.json; do
  hash=$(basename $f .json | sed 's/meta_//')
  diversity=$(jq -r '.metadata.archive_metadata.diversity_score // 0' $f)
  echo "$diversity $hash"
done | sort -rn | head -5
```

---

## トラブルシューティング

### 問題: 候補生成が失敗する

**エラー例:**
```
❌ Repair failed, regenerating with different seed...
```

**原因:**
- 制約が厳しすぎる（除外ゾーンが大きい、XYペア目標が高すぎる）
- パラメータが矛盾（n_pointsが少なすぎてtarget_pairsを満たせない）

**解決:**
```bash
# パラメータを緩和
python generate_generation.py --gen-id 0 --n-points 150 --target-pairs 30
```

### 問題: トーナメント比較でエラー

**エラー例:**
```
ValueError: Generation 0 does not exist
```

**原因:** Generation 0が生成されていない

**解決:**
```bash
# Generation 0を先に生成
python generate_generation.py --gen-id 0
```

### 問題: 親選択がcand_00に固定される

**原因:** comparison_log.jsonが存在しない

**確認:**
```bash
ls gen_history/gen_000/comparison_log.json
# → ファイルが存在しない場合、compare_generation.pyを実行
```

**解決:**
```bash
# トーナメント比較を実行
python compare_generation.py --gen-id 0
```

---

## コマンド早見表

| タスク | コマンド |
|--------|----------|
| **Generation 0生成** | `python generate_generation.py --gen-id 0 --n-points 100 --target-pairs 40` |
| **トーナメント比較** | `python compare_generation.py --gen-id 0 --no-rhino` |
| **Generation 1生成** | `python generate_generation.py --gen-id 1` |
| **Provenance確認** | `cat gen_history/gen_000/population/cand_00/provenance.json` |
| **Summary確認** | `cat gen_history/gen_000/gen_summary.json` |
| **比較ログ確認** | `cat gen_history/gen_000/comparison_log.json` |
| **勝者確認** | `cat gen_history/gen_000/winner_info.json` |
| **多様性スコア計算** | `python -c "from generation.archive_manager import ArchiveManager; ArchiveManager('archive').compute_diversity_scores()"` |
| **Archive品質確認** | `cat archive/meta_*.json \| jq '.metadata.archive_metadata.quality_score' \| sort -rn \| head -5` |

---

## 推奨ワークフロー（完全版）

```bash
# === Step 1: Generation 0を生成 ===
cd IEC/tools
python generate_generation.py --gen-id 0 --n-points 100 --target-pairs 40

# === Step 2: すべての候補を確認 ===
# Rhinoで6つのmesh.objを順番に開いて評価
# gen_history/gen_000/population/cand_00/mesh.obj
# gen_history/gen_000/population/cand_01/mesh.obj
# ...

# === Step 3: トーナメント比較を実行 ===
python compare_generation.py --gen-id 0 --no-rhino
# 各マッチでAまたはBを選択（9マッチ）

# === Step 4: 比較結果を確認 ===
cat gen_history/gen_000/comparison_log.json | jq .winner
cat gen_history/gen_000/winner_info.json

# === Step 5: Generation 1を生成（進化開始） ===
python generate_generation.py --gen-id 1 --n-points 100 --target-pairs 40
# → 実際の勝者が親として使用される

# === Step 6: Generation 1の比較 ===
python compare_generation.py --gen-id 1 --no-rhino

# === Step 7: 継続的な進化 ===
python generate_generation.py --gen-id 2
python compare_generation.py --gen-id 2
# 以降繰り返し...

# === Step 8: Archive分析 ===
# 多様性スコア計算
python -c "from generation.archive_manager import ArchiveManager; ArchiveManager('archive').compute_diversity_scores()"

# 品質ベースTop 5
cat archive/meta_*.json | jq -r '.metadata.archive_metadata | "\(.quality_score // 0) \(.win_count // 0)"' | sort -rn | head -5
```

---

## まとめ

このシステムでは:

1. **Generation 0**: 6候補をランダム生成（完全な検証可能性）
2. **トーナメント比較**: Swiss-system（9マッチ）で効率的な選択
3. **Archive管理**: 勝者カウント、品質スコア、多様性スコア追跡
4. **Generation 1+**: 実際の勝者を親とした進化的生成
   - 変異（weak/strong）
   - 交叉（winner×archive、archive×archive）
   - ランダム（baseline/extreme）
5. **制約チェック**: 6種類の制約を自動検証
6. **自動修復**: 違反を自動修復（最大10回試行）
7. **Provenance追跡**: すべての候補の由来・修復履歴を記録
8. **再現性**: random_seedで完全再現可能

**実装完了（Phase 1-3）:**
- ✅ 6候補同時生成
- ✅ 制約チェック・修復システム
- ✅ Provenance完全追跡
- ✅ 世代ディレクトリ管理
- ✅ OBJエクスポート（mesh, mesh_inner, xy_lines）
- ✅ 進化的生成（変異・交叉）
- ✅ Swiss-systemトーナメント
- ✅ Archive管理拡張（win_count、quality_score、diversity_score）
- ✅ 実際の勝者ベース親選択
- ✅ Rhino CLI統合

---

## 参考ファイル

### 実装ファイル
- `tools/generate_generation.py`: 6候補生成メインスクリプト
- `tools/compare_generation.py`: トーナメント比較スクリプト
- `generation/generation_manager.py`: 世代管理
- `generation/provenance.py`: Provenance追跡
- `generation/constraint_checker.py`: 制約チェック
- `generation/repair.py`: 自動修復
- `generation/archive_manager.py`: Archive管理拡張
- `generation/comparison_tournament.py`: Swiss-systemトーナメント
- `rhino/import2objs_cli.py`: Rhino CLI統合

### データファイル
- `gen_history/gen_XXX/gen_summary.json`: 世代サマリ
- `gen_history/gen_XXX/comparison_log.json`: トーナメント結果
- `gen_history/gen_XXX/winner_info.json`: 勝者情報
- `gen_history/gen_XXX/population/cand_XX/provenance.json`: 生成由来
- `gen_history/gen_XXX/population/cand_XX/meta.json`: 遺伝子型
- `gen_history/gen_XXX/population/cand_XX/mesh.obj`: メッシュ
- `archive/meta_XXXX.json`: Archive候補（拡張メタデータ付き）

---

Good luck with your graduation project! 🎨🏗️🎓
