#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Archive a completed generation's tournament results.

Usage:
    python archive_gen_results.py --gen-id 0
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from generation.archive_manager import ArchiveManager


def load_generation_candidates(gen_id: int):
    """
    Load all candidates from a generation's population directory.

    Args:
        gen_id: Generation ID

    Returns:
        List of candidate dictionaries
    """
    gen_dir = Path(f"../gen_history/gen_{gen_id:03d}")
    pop_dir = gen_dir / "population"

    if not pop_dir.exists():
        raise FileNotFoundError(f"Population directory not found: {pop_dir}")

    candidates = []
    cand_dirs = sorted([d for d in pop_dir.iterdir() if d.is_dir() and d.name.startswith('cand_')])

    for cand_dir in cand_dirs:
        cand_id = cand_dir.name

        # Build file paths
        meta_path = cand_dir / "meta.json"
        mesh_path = cand_dir / "mesh.obj"
        mesh_inner_path = cand_dir / "mesh_inner.obj"
        xy_lines_path = cand_dir / "xy_lines.obj"
        prov_path = cand_dir / "provenance.json"

        if not meta_path.exists():
            print(f"WARNING: Skipping {cand_id} - meta.json not found")
            continue

        # Load metadata for display
        with open(meta_path, 'r') as f:
            meta = json.load(f)

        # Load provenance if available
        origin = "unknown"
        if prov_path.exists():
            with open(prov_path, 'r') as f:
                prov = json.load(f)
                origin = prov.get('origin_type', 'unknown')

        candidate = {
            'id': cand_id,
            'file_paths': {
                'meta': str(meta_path.absolute()),
                'mesh': str(mesh_path.absolute()) if mesh_path.exists() else None,
                'mesh_inner': str(mesh_inner_path.absolute()) if mesh_inner_path.exists() else None,
                'xy_lines': str(xy_lines_path.absolute()) if xy_lines_path.exists() else None,
            },
            'meta': meta,
            'origin': origin
        }

        candidates.append(candidate)

    return candidates


def load_winner_info(gen_id: int):
    """
    Load winner information from winner_info.json.

    Args:
        gen_id: Generation ID

    Returns:
        Winner ID string (e.g., 'cand_00')
    """
    gen_dir = Path(f"../gen_history/gen_{gen_id:03d}")
    winner_file = gen_dir / "winner_info.json"

    if not winner_file.exists():
        raise FileNotFoundError(f"Winner info not found: {winner_file}")

    with open(winner_file, 'r') as f:
        winner_info = json.load(f)

    return winner_info['winner_cand_id']


def update_archive(candidates, winner_id: str, gen_id: int):
    """
    Update archive with tournament results.

    Args:
        candidates: List of candidate dictionaries
        winner_id: ID of winning candidate (e.g., 'cand_00')
        gen_id: Generation ID
    """
    print("\nUpdating archive...")

    try:
        archive_mgr = ArchiveManager('../archive')

        # Archive all candidates (if not already in archive)
        archived_count = 0
        for cand in candidates:
            try:
                genotype_hash = archive_mgr.archive_candidate(
                    cand['file_paths']['meta'],
                    gen_id
                )

                # Record comparison (each candidate participated in tournament)
                archive_mgr.record_comparison(genotype_hash)
                archived_count += 1

            except Exception as e:
                print(f"  WARNING: Failed to archive {cand['id']}: {e}")

        print(f"✓ Archived {archived_count}/{len(candidates)} candidates")

        # Update winner metadata
        winner_cand = next((c for c in candidates if c['id'] == winner_id), None)
        if winner_cand:
            try:
                winner_hash = archive_mgr.archive_candidate(
                    winner_cand['file_paths']['meta'],
                    gen_id
                )
                archive_mgr.update_winner(winner_hash, gen_id)
                print(f"✓ Updated winner metadata ({winner_id})")
            except Exception as e:
                print(f"  WARNING: Failed to update winner: {e}")
        else:
            print(f"  WARNING: Winner {winner_id} not found in candidates")

    except Exception as e:
        print(f"\n❌ Failed to update archive: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description='Archive generation tournament results')
    parser.add_argument('--gen-id', type=int, required=True, help='Generation ID to archive')

    args = parser.parse_args()

    print("=" * 60)
    print(f"  ARCHIVE GENERATION {args.gen_id} RESULTS")
    print("=" * 60)

    # Load candidates
    print(f"\nLoading candidates from gen_{args.gen_id:03d}...")
    candidates = load_generation_candidates(args.gen_id)
    print(f"✓ Loaded {len(candidates)} candidates")

    # Load winner
    print(f"\nLoading winner info...")
    winner_id = load_winner_info(args.gen_id)
    print(f"✓ Winner: {winner_id}")

    # Update archive
    update_archive(candidates, winner_id, args.gen_id)

    print("\n" + "=" * 60)
    print("✓ Archive update complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
