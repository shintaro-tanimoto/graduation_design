# -*- coding: utf-8 -*-
"""
6-Candidate Tournament Comparison Script
Swiss-system tournament for generation comparison with Rhino visualization
"""

import sys
import os
import json
import argparse
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Rhino comparison fixed folder (NEW)
RHINO_TEMP_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "rhino", "temp"
))

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from generation.generation_manager import GenerationManager
from generation.comparison_tournament import TournamentManager
from generation.archive_manager import ArchiveManager
from tools.generate_pair import load_genotype, compute_genotype_hash


def load_generation_candidates(gen_id: int, manager: GenerationManager) -> List[Dict]:
    """
    Load all 6 candidates from generation.

    Args:
        gen_id: Generation ID
        manager: GenerationManager instance

    Returns:
        List of candidate dicts with metadata

    Raises:
        ValueError: If generation doesn't exist or doesn't have 6 candidates
    """
    if not manager.generation_exists(gen_id):
        raise ValueError(f"Generation {gen_id} does not exist")

    candidates = []

    for cand_id in range(6):
        file_paths = manager.get_candidate_files(gen_id, cand_id)

        # Load genotype
        points, weights, metadata, raw_data = load_genotype(file_paths['meta'])

        # Load provenance
        provenance_path = file_paths['provenance']
        with open(provenance_path, 'r') as f:
            provenance = json.load(f)

        # Compute hash
        genotype_hash = compute_genotype_hash(points, weights)

        candidate = {
            'cand_id': f'cand_{cand_id:02d}',
            'gen_id': gen_id,
            'cand_num': cand_id,
            'points': points,
            'weights': weights,
            'metadata': metadata,
            'provenance': provenance,
            'genotype_hash': genotype_hash,
            'file_paths': file_paths
        }

        candidates.append(candidate)

    return candidates


def display_candidate_info(cand_dict: Dict):
    """
    Display candidate metadata in terminal.

    Args:
        cand_dict: Candidate dictionary from load_generation_candidates()
    """
    print(f"\n  {cand_dict['cand_id'].upper()}:")
    print(f"    Origin: {cand_dict['provenance']['origin_type']}")
    print(f"    Points: {cand_dict['metadata']['n_points']}")
    print(f"    XY Pairs: {cand_dict['metadata'].get('metrics', {}).get('xy_pair_count', 'N/A')}")

    metrics = cand_dict['metadata'].get('metrics', {})
    if 'mean_pair_dz' in metrics:
        print(f"    Pair ΔZ: {metrics['mean_pair_dz']:.1f} ± {metrics.get('std_pair_dz', 0):.1f} mm")

    print(f"    Hash: {cand_dict['genotype_hash'][:8]}...")


def format_origin_description(provenance: Dict) -> str:
    """
    Convert provenance information to human-readable Japanese origin description.

    Args:
        provenance: Provenance dictionary from provenance.json

    Returns:
        Human-readable origin description string

    Examples:
        "mutate_weak" + parents=["gen_000/cand_01"]
          → "弱変異 from gen_000/cand_01"
        "crossover_winner_archive" + parents=["gen_000/cand_01", "archive/meta_abc123.json"]
          → "交叉 (gen_000/cand_01 x archive (abc12345))"
        "random_baseline" + parents=[]
          → "ランダム生成 (baseline)"
    """
    origin_type = provenance.get('origin_type', 'unknown')
    parents = provenance.get('parents', [])

    # Helper function to classify parent paths
    def classify_parent(parent_path: str) -> str:
        if parent_path.startswith('gen_'):
            # gen_XXX/cand_YY format
            gen_id = parent_path.split('/')[0].replace('gen_', '')
            cand_id = parent_path.split('/')[1] if '/' in parent_path else ''
            return f"gen_{gen_id}/{cand_id}"
        elif parent_path.startswith('archive/'):
            # archive/meta_XXX.json format
            hash_id = parent_path.replace('archive/meta_', '').replace('.json', '')
            return f"archive ({hash_id[:8]})"
        else:
            return parent_path

    # Generate description based on origin type
    if origin_type == 'mutate_weak':
        if parents:
            parent_desc = classify_parent(parents[0])
            return f"弱変異 from {parent_desc}"
        return "弱変異 (親不明)"

    elif origin_type == 'mutate_strong':
        if parents:
            parent_desc = classify_parent(parents[0])
            return f"強変異 from {parent_desc}"
        return "強変異 (親不明)"

    elif origin_type == 'crossover_winner_archive':
        if len(parents) >= 2:
            parent1 = classify_parent(parents[0])
            parent2 = classify_parent(parents[1])
            return f"交叉 ({parent1} x {parent2})"
        return "交叉 (前世代勝者 x archive)"

    elif origin_type == 'crossover_archive_archive':
        if len(parents) >= 2:
            parent1 = classify_parent(parents[0])
            parent2 = classify_parent(parents[1])
            return f"交叉 ({parent1} x {parent2})"
        return "交叉 (archive x archive)"

    elif origin_type == 'random_baseline':
        return "ランダム生成 (baseline)"

    elif origin_type == 'random_extreme':
        return "ランダム生成 (extreme)"

    else:
        return f"不明 ({origin_type})"


def to_windows_path(path):
    r"""
    Convert Linux path to Windows-style path for Rhino (WSL compatibility).

    Args:
        path: Linux path (e.g., /home/user/file.obj)

    Returns:
        Windows-style path (e.g., \\wsl$\Ubuntu\home\user\file.obj)
    """
    abs_path = os.path.abspath(path)
    # If running on WSL, convert /home/... to \\wsl$\Ubuntu\home\...
    if abs_path.startswith('/'):
        return f"\\\\wsl$\\Ubuntu{abs_path}"
    return abs_path


def call_rhino_import(mesh_a: str, mesh_b: str,
                     inner_a: str = None, inner_b: str = None,
                     lines_a: str = None, lines_b: str = None):
    """
    Call Rhino import script via subprocess.

    Note: This function prepares the command but does NOT execute it automatically.
          The user must run the command in Rhino manually.

    Args:
        mesh_a: Path to candidate A's mesh.obj
        mesh_b: Path to candidate B's mesh.obj
        inner_a: Path to candidate A's mesh_inner.obj (optional)
        inner_b: Path to candidate B's mesh_inner.obj (optional)
        lines_a: Path to candidate A's xy_lines.obj (optional)
        lines_b: Path to candidate B's xy_lines.obj (optional)

    Returns:
        Command string for manual execution
    """

    # Use inner meshes if provided, fallback to mesh_a/mesh_b
    obj_a = inner_a if inner_a else mesh_a
    obj_b = inner_b if inner_b else mesh_b

    obj_a_win = to_windows_path(obj_a)
    obj_b_win = to_windows_path(obj_b)

    cmd_parts = [
        '_-RunPythonScript',
        f'"{os.path.abspath("rhino/import2objs_cli.py")}"',
        f'--obj-a "{obj_a_win}"',
        f'--obj-b "{obj_b_win}"'
    ]

    # Only add inner parameters if they differ from main obj (backward compatibility)
    if inner_a and inner_a != obj_a:
        cmd_parts.append(f'--obj-a-inner "{to_windows_path(inner_a)}"')
    if inner_b and inner_b != obj_b:
        cmd_parts.append(f'--obj-b-inner "{to_windows_path(inner_b)}"')

    # Add XY-pair lines (NEW)
    if lines_a:
        cmd_parts.append(f'--obj-a-lines "{to_windows_path(lines_a)}"')
    if lines_b:
        cmd_parts.append(f'--obj-b-lines "{to_windows_path(lines_b)}"')

    cmd = ' '.join(cmd_parts)
    return cmd


def create_match_temp_folder(gen_id: int, round_num: int, match_num: int) -> str:
    """
    Create temporary folder for tournament match visualization.

    Args:
        gen_id: Generation ID
        round_num: Round number (0-indexed internally)
        match_num: Match number (1-3)

    Returns:
        Absolute path to created temporary folder

    Example:
        >>> path = create_match_temp_folder(1, 0, 1)
        >>> print(path)
        /tmp/rhino_comparison_gen_001_round_1_match_1
    """
    # Create folder name (round_num is 0-indexed, display as 1-indexed)
    folder_name = f"rhino_comparison_gen_{gen_id:03d}_round_{round_num + 1}_match_{match_num}"
    temp_path = os.path.join("/tmp", folder_name)

    try:
        os.makedirs(temp_path, exist_ok=True)
        return temp_path
    except OSError as e:
        print(f"  WARNING: Failed to create temp folder: {e}")
        # Fallback: use tempfile.mkdtemp()
        fallback_path = tempfile.mkdtemp(prefix=f"rhino_match_{gen_id}_r{round_num+1}_m{match_num}_")
        print(f"  Using fallback temp folder: {fallback_path}")
        return fallback_path


def copy_candidate_files_to_temp(cand_dict: Dict, temp_dir: str) -> Dict[str, str]:
    """
    Copy candidate's mesh_inner.obj and xy_lines.obj to temporary folder.

    Args:
        cand_dict: Candidate dictionary from load_generation_candidates()
        temp_dir: Destination temporary directory path

    Returns:
        Dictionary mapping file types to new paths:
        {
            'mesh_inner': '/tmp/.../cand_00_mesh_inner.obj',
            'xy_lines': '/tmp/.../cand_00_xy_lines.obj'
        }

    Example:
        >>> paths = copy_candidate_files_to_temp(cand_a, "/tmp/rhino_...")
        >>> print(paths['mesh_inner'])
        /tmp/rhino_comparison_gen_001_round_1_match_1/cand_00_mesh_inner.obj
    """
    cand_num = cand_dict['cand_num']
    file_paths = cand_dict['file_paths']

    copied_paths = {}

    # Copy mesh_inner.obj
    src_inner = file_paths.get('mesh_inner')
    if src_inner and os.path.exists(src_inner):
        dest_inner = os.path.join(temp_dir, f"cand_{cand_num:02d}_mesh_inner.obj")
        try:
            shutil.copy2(src_inner, dest_inner)
            copied_paths['mesh_inner'] = dest_inner
        except (IOError, shutil.Error) as e:
            print(f"  WARNING: Failed to copy mesh_inner for cand_{cand_num:02d}: {e}")
    else:
        print(f"  WARNING: mesh_inner.obj not found for cand_{cand_num:02d}")

    # Copy xy_lines.obj
    src_lines = file_paths.get('xy_lines')
    if src_lines and os.path.exists(src_lines):
        dest_lines = os.path.join(temp_dir, f"cand_{cand_num:02d}_xy_lines.obj")
        try:
            shutil.copy2(src_lines, dest_lines)
            copied_paths['xy_lines'] = dest_lines
        except (IOError, shutil.Error) as e:
            print(f"  WARNING: Failed to copy xy_lines for cand_{cand_num:02d}: {e}")
    else:
        print(f"  WARNING: xy_lines.obj not found for cand_{cand_num:02d}")

    return copied_paths


def cleanup_tournament_temp_folders(temp_folder_list: List[str]):
    """
    Delete all temporary folders created during tournament.

    Args:
        temp_folder_list: List of temporary folder paths to delete

    Example:
        >>> cleanup_tournament_temp_folders(['/tmp/rhino_.../', '/tmp/rhino_.../'])
        Cleaning up 9 temporary folders...
        ✓ Deleted 9 temporary folders
    """
    if not temp_folder_list:
        return

    print(f"\nCleaning up {len(temp_folder_list)} temporary folders...")

    deleted_count = 0
    for folder in temp_folder_list:
        try:
            if os.path.exists(folder):
                shutil.rmtree(folder)
                deleted_count += 1
        except (OSError, shutil.Error) as e:
            print(f"  WARNING: Failed to delete {folder}: {e}")

    print(f"✓ Deleted {deleted_count} temporary folders")


def copy_candidate_to_fixed_location(cand_dict: Dict, dest_prefix: str, temp_dir: str) -> int:
    """
    Copy candidate files to fixed location with fixed names.

    Args:
        cand_dict: Candidate dictionary with file_paths
        dest_prefix: 'A' or 'B'
        temp_dir: Destination directory (IEC/rhino/temp/)

    Returns:
        Number of files successfully copied

    Example:
        >>> copied = copy_candidate_to_fixed_location(cand_a, 'A', '/path/to/rhino/temp')
        >>> print(copied)  # 2 (mesh + lines)
    """
    file_paths = cand_dict['file_paths']
    copied_count = 0

    # Copy mesh_inner.obj → A_mesh.obj or B_mesh.obj
    src_inner = file_paths.get('mesh_inner')
    if src_inner and os.path.exists(src_inner):
        dest_mesh = os.path.join(temp_dir, f"{dest_prefix}_mesh.obj")
        try:
            shutil.copy2(src_inner, dest_mesh)
            copied_count += 1
        except (IOError, shutil.Error) as e:
            print(f"  WARNING: Failed to copy mesh for {dest_prefix}: {e}")
    else:
        print(f"  WARNING: mesh_inner.obj not found for {dest_prefix}")

    # Copy xy_lines.obj → A_lines.obj or B_lines.obj
    src_lines = file_paths.get('xy_lines')
    if src_lines and os.path.exists(src_lines):
        dest_lines = os.path.join(temp_dir, f"{dest_prefix}_lines.obj")
        try:
            shutil.copy2(src_lines, dest_lines)
            copied_count += 1
        except (IOError, shutil.Error) as e:
            print(f"  WARNING: Failed to copy lines for {dest_prefix}: {e}")
    else:
        print(f"  WARNING: xy_lines.obj not found for {dest_prefix}")

    return copied_count


def prompt_comparison_choice(cand_a_id: str, cand_b_id: str) -> str:
    """
    Prompt user to choose between two candidates.

    Args:
        cand_a_id: First candidate ID
        cand_b_id: Second candidate ID

    Returns:
        Winner candidate ID (either cand_a_id or cand_b_id)
    """
    while True:
        choice = input(f"\n  Choose winner (A or B): ").strip().upper()

        if choice == 'A':
            return cand_a_id
        elif choice == 'B':
            return cand_b_id
        else:
            print(f"  ⚠ Invalid choice '{choice}'. Please enter 'A' or 'B'.")


def run_tournament(gen_id: int, n_rounds: int = 3, use_rhino: bool = True):
    """
    Main tournament loop.

    Args:
        gen_id: Generation ID to compare
        n_rounds: Number of tournament rounds (default: 3)
        use_rhino: Display Rhino import commands (default: True)

    Returns:
        Tuple: (tournament_manager, winner_id, candidates)
    """
    print("\n" + "=" * 60)
    print(f"  TOURNAMENT COMPARISON - Generation {gen_id}")
    print(f"  Swiss-system: {n_rounds} rounds, {n_rounds * 3} total matches")
    print("=" * 60)

    # Initialize manager
    manager = GenerationManager()

    # Load candidates
    print("\nLoading candidates...")
    candidates = load_generation_candidates(gen_id, manager)
    print(f"✓ Loaded {len(candidates)} candidates")

    # Initialize tournament
    tournament = TournamentManager(candidates, n_rounds=n_rounds)

    # Run tournament
    for round_num in range(n_rounds):
        print("\n" + "=" * 60)
        print(f"  ROUND {round_num + 1} / {n_rounds}")
        print("=" * 60)

        # Generate pairings
        pairings = tournament.generate_round_pairings()

        # Process each match
        for match_num, (cand_a_id, cand_b_id) in enumerate(pairings, 1):
            print(f"\n--- Match {match_num}/3 (Round {round_num + 1}) ---")

            # Get candidate data
            cand_a = next(c for c in candidates if c['cand_id'] == cand_a_id)
            cand_b = next(c for c in candidates if c['cand_id'] == cand_b_id)

            # Display info
            display_candidate_info(cand_a)
            display_candidate_info(cand_b)

            # Rhino visualization with fixed folder
            if use_rhino:
                print("\n  Rhino Visualization:")
                print("  " + "-" * 58)

                try:
                    # Ensure fixed temp folder exists
                    os.makedirs(RHINO_TEMP_DIR, exist_ok=True)

                    # Copy candidate A files with fixed names
                    copied_a = copy_candidate_to_fixed_location(cand_a, 'A', RHINO_TEMP_DIR)

                    # Copy candidate B files with fixed names
                    copied_b = copy_candidate_to_fixed_location(cand_b, 'B', RHINO_TEMP_DIR)

                    total_copied = copied_a + copied_b
                    print(f"  Files copied to: {RHINO_TEMP_DIR}")
                    print(f"  Files copied: {total_copied}/4")

                    # Generate simple Rhino command
                    import2objs_path = os.path.join(
                        os.path.dirname(__file__), "..", "rhino", "import2objs.py"
                    )
                    import2objs_wsl = to_windows_path(os.path.abspath(import2objs_path))

                    rhino_cmd = f'_-RunPythonScript "{import2objs_wsl}"'

                    # Display simple command for user to copy
                    print("\n  Copy this command into Rhino:")
                    print("  " + "=" * 58)
                    print(f"  {rhino_cmd}")
                    print("  " + "=" * 58)
                    print("\n  Note: Files are copied with fixed names:")
                    print(f"    - Candidate A: A_mesh.obj, A_lines.obj")
                    print(f"    - Candidate B: B_mesh.obj, B_lines.obj")

                except Exception as e:
                    print(f"  WARNING: Rhino setup failed: {e}")
                    print(f"  Continuing without visualization...")

            # Get user choice
            winner_id = prompt_comparison_choice(cand_a_id, cand_b_id)

            # Record result
            tournament.record_match_result(cand_a_id, cand_b_id, winner_id)

            winner_label = 'A' if winner_id == cand_a_id else 'B'
            print(f"  ✓ Winner: {winner_label} ({winner_id})")

        # Show current standings
        print("\n  Current Standings:")
        standings = tournament.get_current_standings()
        for rank, (cand_id, score) in enumerate(standings, 1):
            print(f"    {rank}. {cand_id}: {score} points")

        # Advance round
        tournament.current_round += 1

    # Final results
    winner_id = tournament.get_winner()

    print("\n" + "=" * 60)
    print("  TOURNAMENT COMPLETE!")
    print("=" * 60)
    print(f"\n  🏆 Winner: {winner_id}")

    # Display detailed standings with origin descriptions
    final_standings = tournament.get_current_standings()
    print("\n  Final Standings:")
    print("  " + "-" * 58)

    for rank, (cand_id, score) in enumerate(final_standings, 1):
        # Get candidate origin information
        cand = next(c for c in candidates if c['cand_id'] == cand_id)
        origin_desc = format_origin_description(cand['provenance'])

        # Display ranking with origin
        print(f"    {rank}位: {cand_id} ({score}点) - {origin_desc}")

    print("  " + "-" * 58)

    return tournament, winner_id, candidates


def save_comparison_results(gen_id: int, tournament: TournamentManager,
                            winner_id: str, candidates: List[Dict],
                            manager: GenerationManager):
    """
    Save comparison results to files.

    Creates:
    - gen_history/gen_XXX/comparison_log.json
    - gen_history/gen_XXX/winner_info.json

    Args:
        gen_id: Generation ID
        tournament: TournamentManager instance
        winner_id: Winner's candidate ID
        candidates: List of all candidates
        manager: GenerationManager instance
    """
    gen_dir = manager.get_generation_dir(gen_id)

    # Get winner data
    winner = next(c for c in candidates if c['cand_id'] == winner_id)

    # Comparison log with candidate origins
    comparison_log = {
        'gen_id': gen_id,
        'timestamp': datetime.now().isoformat(),
        **tournament.to_log_dict(),
        # Add candidate origin information for later review
        'candidate_origins': {
            cand['cand_id']: {
                'origin_type': cand['provenance'].get('origin_type'),
                'parents': cand['provenance'].get('parents', []),
                'origin_description': format_origin_description(cand['provenance'])
            }
            for cand in candidates
        }
    }

    comparison_log_path = os.path.join(gen_dir, 'comparison_log.json')
    with open(comparison_log_path, 'w', encoding='utf-8') as f:
        json.dump(comparison_log, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved comparison log: {comparison_log_path}")

    # Winner info
    winner_info = {
        'gen_id': gen_id,
        'winner_cand_id': winner_id,
        'final_score': tournament.scores[winner_id],
        'total_rounds': tournament.n_rounds,
        'timestamp': datetime.now().isoformat(),
        'genotype_hash': winner['genotype_hash'],
        'n_points': winner['metadata']['n_points'],
        'xy_pair_count': winner['metadata'].get('metrics', {}).get('xy_pair_count', None),
        'provenance_origin': winner['provenance']['origin_type']
    }

    winner_info_path = os.path.join(gen_dir, 'winner_info.json')
    with open(winner_info_path, 'w', encoding='utf-8') as f:
        json.dump(winner_info, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved winner info: {winner_info_path}")


def update_archive(candidates: List[Dict], winner_id: str, gen_id: int):
    """
    Update archive with tournament results.

    Args:
        candidates: List of all candidates
        winner_id: Winner's candidate ID
        gen_id: Generation ID
    """
    print("\nUpdating archive...")

    archive_mgr = ArchiveManager('../archive')

    # Archive all candidates (if not already in archive)
    archived_hashes = []
    for cand in candidates:
        try:
            genotype_hash = archive_mgr.archive_candidate(
                cand['file_paths']['meta'],
                gen_id
            )
            archived_hashes.append(genotype_hash)

            # Record comparison
            archive_mgr.record_comparison(genotype_hash)

        except Exception as e:
            print(f"  ⚠ Failed to archive {cand['cand_id']}: {e}")

    print(f"✓ Archived {len(archived_hashes)} candidates")

    # Update winner
    winner = next(c for c in candidates if c['cand_id'] == winner_id)
    winner_hash = winner['genotype_hash']

    try:
        archive_mgr.update_winner(winner_hash, gen_id)
        print(f"✓ Updated winner record for {winner_hash[:8]}...")
    except Exception as e:
        print(f"  ⚠ Failed to update winner: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="6-Candidate Tournament Comparison"
    )

    parser.add_argument('--gen-id', type=int, required=True,
                       help="Generation ID to compare")
    parser.add_argument('--rounds', type=int, default=3,
                       help="Number of tournament rounds (default: 3)")
    parser.add_argument('--no-rhino', action='store_true',
                       help="Disable Rhino visualization prompts")

    args = parser.parse_args()

    # Run tournament
    try:
        tournament, winner_id, candidates = run_tournament(
            args.gen_id,
            n_rounds=args.rounds,
            use_rhino=not args.no_rhino
        )
    except Exception as e:
        print(f"\n❌ Tournament failed: {e}")
        return 1

    # Save results
    try:
        manager = GenerationManager()
        save_comparison_results(args.gen_id, tournament, winner_id, candidates, manager)
    except Exception as e:
        print(f"\n❌ Failed to save results: {e}")
        return 1

    # Update archive
    try:
        update_archive(candidates, winner_id, args.gen_id)
    except Exception as e:
        print(f"\n❌ Failed to update archive: {e}")
        # Non-fatal, continue

    print("\n" + "=" * 60)
    print("✓ Comparison complete!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
