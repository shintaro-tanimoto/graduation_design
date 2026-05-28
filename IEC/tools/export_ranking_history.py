#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_ranking_history.py - 世代×順位推移データをExcel用CSV形式で出力

Usage:
    python tools/export_ranking_history.py --verbose
    python tools/export_ranking_history.py --output my_ranking.csv
"""

import os
import sys
import json
import csv
import argparse
from pathlib import Path
from typing import Dict, List, Optional


def find_generations(gen_history_dir: str) -> List[int]:
    """
    利用可能な世代番号のリストを取得（昇順）

    Args:
        gen_history_dir: gen_historyディレクトリのパス

    Returns:
        世代番号のリスト（例：[0, 1, 2, ..., 28]）
    """
    gen_history_path = Path(gen_history_dir)

    if not gen_history_path.exists():
        raise FileNotFoundError(f"gen_history directory not found: {gen_history_dir}")

    generations = []

    for item in gen_history_path.iterdir():
        if item.is_dir() and item.name.startswith("gen_"):
            try:
                gen_num = int(item.name.replace("gen_", ""))
                generations.append(gen_num)
            except ValueError:
                # gen_XXXの形式でない場合はスキップ
                continue

    return sorted(generations)


def load_comparison_log(gen_id: int, gen_history_dir: str) -> Optional[dict]:
    """
    comparison_log.json を読み込み

    Args:
        gen_id: 世代番号
        gen_history_dir: gen_historyディレクトリのパス

    Returns:
        comparison_logの辞書、または読み込み失敗時はNone
    """
    gen_dir = Path(gen_history_dir) / f"gen_{gen_id:03d}"
    comparison_log_path = gen_dir / "comparison_log.json"

    if not comparison_log_path.exists():
        return None

    try:
        with open(comparison_log_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"  ⚠ Failed to load {comparison_log_path}: {e}", file=sys.stderr)
        return None


def extract_rankings(comparison_log: dict) -> Dict[str, int]:
    """
    standings から各候補の順位を抽出

    Args:
        comparison_log: comparison_log.json の内容

    Returns:
        候補IDと順位のマッピング（例：{"cand_00": 1, "cand_01": 4, ...}）
    """
    standings = comparison_log.get("standings", [])
    rankings = {}

    for rank, standing_entry in enumerate(standings, start=1):
        # standing_entry は ["cand_XX", score] の形式
        if isinstance(standing_entry, list) and len(standing_entry) >= 1:
            cand_id = standing_entry[0]
            rankings[cand_id] = rank

    return rankings


def export_to_csv(gen_history_dir: str, output_path: str, verbose: bool):
    """
    メイン処理：全世代の順位データをCSV出力

    Args:
        gen_history_dir: gen_historyディレクトリのパス
        output_path: 出力CSVファイルのパス
        verbose: 詳細ログを表示するか
    """
    print("=" * 60)
    print("  世代×順位推移データ エクスポート")
    print("=" * 60)

    # 利用可能な世代を検出
    try:
        generations = find_generations(gen_history_dir)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not generations:
        print(f"❌ No generations found in {gen_history_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"\n✓ Found {len(generations)} generations: gen_{generations[0]:03d} to gen_{generations[-1]:03d}")

    # CSVヘッダー
    fieldnames = [
        '世代',
        'cand_00_順位',
        'cand_01_順位',
        'cand_02_順位',
        'cand_03_順位',
        'cand_04_順位',
        'cand_05_順位',
        '勝者'
    ]

    # データ収集
    rows = []
    success_count = 0
    error_count = 0

    for gen_id in generations:
        if verbose:
            print(f"\nProcessing gen_{gen_id:03d}...")

        comparison_log = load_comparison_log(gen_id, gen_history_dir)

        if comparison_log is None:
            if verbose:
                print(f"  ⚠ No comparison_log.json found, skipping...")
            error_count += 1
            # N/A で埋めるオプション（コメントアウト可能）
            # row = {'世代': gen_id}
            # for cand_idx in range(6):
            #     row[f'cand_{cand_idx:02d}_順位'] = 'N/A'
            # row['勝者'] = 'N/A'
            # rows.append(row)
            continue

        # 順位抽出
        rankings = extract_rankings(comparison_log)
        winner = comparison_log.get('winner', 'N/A')

        # 行データ作成
        row = {'世代': gen_id}

        for cand_idx in range(6):
            cand_id = f'cand_{cand_idx:02d}'
            rank = rankings.get(cand_id, 'N/A')
            row[f'{cand_id}_順位'] = rank

        row['勝者'] = winner

        rows.append(row)
        success_count += 1

        if verbose:
            print(f"  ✓ Rankings: {rankings}")
            print(f"  ✓ Winner: {winner}")

    # CSV出力
    print(f"\n{'='*60}")
    print(f"Writing to {output_path}...")

    try:
        # UTF-8 BOM付きで出力（Excelでの文字化け防止）
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"✓ Successfully exported {len(rows)} generations")
        print(f"{'='*60}")

    except IOError as e:
        print(f"❌ Failed to write CSV: {e}", file=sys.stderr)
        sys.exit(1)

    # サマリー
    print(f"\n📊 Summary:")
    print(f"  Total generations: {len(generations)}")
    print(f"  Successfully processed: {success_count}")
    print(f"  Errors/Skipped: {error_count}")
    print(f"\n📁 Output file: {os.path.abspath(output_path)}")
    print(f"\n💡 Next step: Open the CSV in Excel and create a line chart!")
    print(f"   - X-axis: 世代")
    print(f"   - Y-axis: 順位 (reverse axis: 1 at top)")
    print(f"   - Highlight: cand_00, cand_01 with thick lines")


def main():
    parser = argparse.ArgumentParser(
        description='世代×順位推移データをExcel用CSV形式で出力',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default usage
  python tools/export_ranking_history.py

  # With verbose output
  python tools/export_ranking_history.py --verbose

  # Custom output file
  python tools/export_ranking_history.py --output my_ranking.csv
        """
    )

    parser.add_argument(
        '--gen-history-dir',
        type=str,
        default='gen_history',
        help='gen_historyディレクトリのパス（デフォルト: gen_history）'
    )

    parser.add_argument(
        '--output',
        type=str,
        default='gen_history/ranking_history.csv',
        help='出力CSVファイル名（デフォルト: gen_history/ranking_history.csv）'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='詳細ログを表示'
    )

    args = parser.parse_args()

    export_to_csv(args.gen_history_dir, args.output, args.verbose)


if __name__ == '__main__':
    main()
