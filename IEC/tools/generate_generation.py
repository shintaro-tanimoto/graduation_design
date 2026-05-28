#!/usr/bin/env python3
"""
generate_generation.py - 6-Candidate Generation System (Main Script)

Generates 6 candidates per generation with full provenance tracking,
constraint checking, and repair mechanisms.

Usage:
    # Generate generation 0 (bootstrap)
    python generate_generation.py --gen-id 0

    # Generate generation 1+ (requires parent selection from archive)
    python generate_generation.py --gen-id 1
"""

import os
import sys
import argparse
import random
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# Import existing modules
from LaguerreVoronoi import compute_power_diagram
from generate_pair import (
    DEFAULT_PARAMS,
    generate_random_genotype,
    mutate_genotype,
    crossover_genotypes,
    save_genotype,
    compute_genotype_hash,
    export_xy_pair_lines,
    load_genotype
)

# Import generation modules
from generation.generation_manager import GenerationManager, create_initial_generation_summary
from generation.provenance import (
    ProvenanceTracker,
    create_mutation_provenance,
    create_crossover_provenance,
    create_random_provenance
)
from generation.constraint_checker import ConstraintChecker
from generation.repair import repair_candidate


# ==============================================================================
# PARENT SELECTION (for Generation 1+)
# ==============================================================================

def select_recent_winner(gen_id: int, manager: GenerationManager) -> Tuple[np.ndarray, np.ndarray, str]:
    """
    前世代の勝者を比較ログから選択（フォールバック：cand_00）

    Args:
        gen_id: 現在の世代ID
        manager: GenerationManager instance

    Returns:
        (points, weights, parent_path): 勝者の遺伝子型と参照パス
    """
    prev_gen_id = gen_id - 1

    if not manager.generation_exists(prev_gen_id):
        raise ValueError(
            f"Previous generation (gen_{prev_gen_id:03d}) does not exist. "
            f"Please start with --gen-id 0"
        )

    # comparison_log.json の読み込みを試行
    gen_dir = manager.get_generation_dir(prev_gen_id)
    comparison_log_path = os.path.join(gen_dir, 'comparison_log.json')

    winner_cand_id = 0  # デフォルトフォールバック

    if os.path.exists(comparison_log_path):
        try:
            with open(comparison_log_path, 'r') as f:
                log = json.load(f)

            winner_id = log.get('winner', 'cand_00')
            winner_cand_id = int(winner_id.split('_')[1])

            print(f"  ✓ Using actual winner from comparison: {winner_id}")
        except Exception as e:
            print(f"  ⚠ Failed to load comparison log: {e}")
            print(f"  → Falling back to cand_00")
    else:
        print(f"  ℹ No comparison log found, using cand_00 as winner")

    # 勝者の遺伝子型をロード
    file_paths = manager.get_candidate_files(prev_gen_id, winner_cand_id)
    points, weights, metadata, _ = load_genotype(file_paths['meta'])

    cand_path = f"gen_{prev_gen_id:03d}/cand_{winner_cand_id:02d}"
    return points, weights, cand_path


def select_archive_winner_diversity(recent_winner_points: np.ndarray,
                                     recent_winner_weights: np.ndarray,
                                     archive_dir: str = '../archive') -> Tuple[np.ndarray, np.ndarray, str]:
    """
    Archive内で最も多様性の高い候補を選択（メタ特徴のL2距離ベース）

    Args:
        recent_winner_points: recent_winnerの点座標
        recent_winner_weights: recent_winnerの重み
        archive_dir: Archiveディレクトリパス

    Returns:
        (points, weights, archive_path): Archive候補の遺伝子型と参照パス

    Raises:
        ValueError: Archiveが空の場合
    """
    from tools.extract_features import extract_features_from_genotype

    archive_files = list(Path(archive_dir).glob('meta_*.json'))
    if len(archive_files) == 0:
        raise ValueError("Archive is empty")

    # recent_winnerの特徴抽出
    winner_features = extract_features_from_genotype(
        recent_winner_points, recent_winner_weights, include_volume=False
    )

    # 最大距離の候補を探索
    max_distance = -1
    best_archive = None

    for archive_file in archive_files:
        points, weights, _, _ = load_genotype(str(archive_file))
        features = extract_features_from_genotype(points, weights, include_volume=False)
        distance = np.linalg.norm(winner_features - features)

        if distance > max_distance:
            max_distance = distance
            best_archive = (points, weights, f"archive/{archive_file.name}")

    return best_archive


def select_archive_winners_quality(archive_dir: str = '../archive',
                                    n: int = 2,
                                    method: str = 'random') -> List[Tuple[np.ndarray, np.ndarray, str]]:
    """
    Archiveから複数候補を選択（簡易版）

    Args:
        archive_dir: Archiveディレクトリパス
        n: 選択する候補数
        method: 選択方法（'random' or 'latest'）

    Returns:
        [(points, weights, archive_path), ...]: Archive候補のリスト

    Raises:
        ValueError: Archive内の候補数が不足している場合
    """
    archive_files = list(Path(archive_dir).glob('meta_*.json'))

    if len(archive_files) < n:
        raise ValueError(f"Archive has only {len(archive_files)} candidates, need {n}")

    if method == 'random':
        selected_files = random.sample(archive_files, n)
    elif method == 'latest':
        selected_files = sorted(
            archive_files,
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )[:n]
    else:
        # デフォルトはrandom
        selected_files = random.sample(archive_files, n)

    results = []
    for f in selected_files:
        points, weights, _, _ = load_genotype(str(f))
        results.append((points, weights, f"archive/{f.name}"))

    return results


# ==============================================================================
# GENERATION 0: Bootstrap (All Random)
# ==============================================================================

def generate_bootstrap_population(gen_id: int, params: Dict, manager: GenerationManager):
    """
    Generate Generation 0 with 6 random candidates.

    Args:
        gen_id: Generation ID (should be 0)
        params: Parameter dictionary
        manager: GenerationManager instance

    Returns:
        List of (cand_id, points, weights, provenance_tracker) tuples
    """
    print(f"\n{'='*60}")
    print(f"  GENERATION {gen_id}: Bootstrap (All Random)")
    print(f"{'='*60}\n")

    population = []

    for cand_idx in range(6):
        cand_id = f"cand_{cand_idx:02d}"
        print(f"\nGenerating {cand_id}...")

        # Generate random seed
        seed = random.randint(1, 2**31 - 1)
        np.random.seed(seed)
        random.seed(seed)

        # Determine random type
        if cand_idx < 4:
            random_type = "baseline"
            target_pairs = params.get('target_pairs', 0)
        else:
            # cand_04, cand_05: random_extreme
            random_type = "extreme"
            # Rotate through variants
            variant = gen_id % 4
            if variant == 0:
                target_pairs = 30  # High pairs
                params_variant = params.copy()
                params_variant['target_pairs'] = target_pairs
            elif variant == 1:
                target_pairs = 5  # Low pairs
                params_variant = params.copy()
                params_variant['target_pairs'] = target_pairs
            elif variant == 2:
                target_pairs = params.get('target_pairs', 0)
                params_variant = params.copy()
                params_variant['weight_min'] = 30
                params_variant['weight_max'] = 70
            else:
                target_pairs = params.get('target_pairs', 0)
                params_variant = params.copy()
                params_variant['weight_min'] = 5
                params_variant['weight_max'] = 20

            params = params_variant

        # Generate random genotype
        points, weights, gen_params = generate_random_genotype(params, target_pairs=target_pairs)

        print(f"  Initial: {len(points)} points, {gen_params.get('actual_pairs', 0)} XY-pairs")

        # Check constraints and repair if needed
        checker = ConstraintChecker(params)
        violations = checker.check_all(points, weights)

        if violations:
            print(f"  ⚠ Found {len(violations)} constraint violations, attempting repair...")
            repaired_points, repaired_weights, repair_log, success = repair_candidate(
                points, weights, params, max_iter=10
            )

            if success:
                points, weights = repaired_points, repaired_weights
                print(f"  ✅ Repair successful ({len(repair_log.actions)} actions)")
            else:
                print(f"  ❌ Repair failed, regenerating with different seed...")
                # Regeneration logic would go here
                # For now, continue with best effort
        else:
            print(f"  ✅ All constraints satisfied")
            repair_log = None

        # Create provenance tracker
        provenance = create_random_provenance(
            cand_id=cand_id,
            gen_id=gen_id,
            random_type=random_type,
            target_pairs=target_pairs,
            seed=seed
        )

        # Add repair log if any
        if repair_log:
            for action in repair_log.actions:
                provenance.add_repair_action(
                    action['issue'],
                    action['action'],
                    action['success']
                )

        population.append((cand_id, points, weights, provenance))

    print(f"\n{'='*60}")
    print(f"  Generation {gen_id}: {len(population)} candidates created")
    print(f"{'='*60}\n")

    return population


# ==============================================================================
# GENERATION 1+: Evolution (GA4 + Random2)
# ==============================================================================

def generate_evolution_population(gen_id: int, params: Dict, manager: GenerationManager):
    """
    Generate Generation 1+ with evolutionary operators.

    6 candidates:
    - cand_00: mutate_weak (sigma × 0.5, PRESERVE_XY)
    - cand_01: mutate_strong (sigma × 1.5, BREAK_XY)
    - cand_02: crossover (recent_winner × archive_winner, blend)
    - cand_03: crossover (archive_A × archive_B, uniform)
    - cand_04: random_baseline
    - cand_05: random_extreme

    Args:
        gen_id: Generation ID (must be >= 1)
        params: Parameter dictionary
        manager: GenerationManager instance

    Returns:
        List of (cand_id, points, weights, provenance_tracker) tuples
    """
    print(f"\n{'='*60}")
    print(f"  GENERATION {gen_id}: Evolution (GA4 + Random2)")
    print(f"{'='*60}\n")

    population = []

    # ============================================================
    # STEP 1: 親選択
    # ============================================================

    print("Parent Selection:")

    # recent_winner（前世代の勝者、簡易版：cand_00）
    recent_winner_points, recent_winner_weights, recent_winner_path = \
        select_recent_winner(gen_id, manager)
    print(f"  ✓ recent_winner: {recent_winner_path} ({len(recent_winner_points)} points)")

    # archive_winner（多様性ベース）
    try:
        archive_winner_points, archive_winner_weights, archive_winner_path = \
            select_archive_winner_diversity(
                recent_winner_points,
                recent_winner_weights,
                '../archive'
            )
        print(f"  ✓ archive_winner (diversity): {archive_winner_path}")
    except ValueError as e:
        print(f"  ⚠ Archive selection failed: {e}")
        print(f"  → Fallback: Using recent_winner as archive_winner")
        archive_winner_points = recent_winner_points.copy()
        archive_winner_weights = recent_winner_weights.copy()
        archive_winner_path = recent_winner_path

    # archive_winner_A, archive_winner_B（品質ベース簡易版：ランダム2つ）
    try:
        archive_ab = select_archive_winners_quality('../archive', n=2, method='random')
        archive_a_points, archive_a_weights, archive_a_path = archive_ab[0]
        archive_b_points, archive_b_weights, archive_b_path = archive_ab[1]
        print(f"  ✓ archive_winner_A: {archive_a_path}")
        print(f"  ✓ archive_winner_B: {archive_b_path}")
    except ValueError as e:
        print(f"  ⚠ Archive selection failed: {e}")
        print(f"  → Fallback: Using recent_winner and archive_winner")
        archive_a_points = recent_winner_points.copy()
        archive_a_weights = recent_winner_weights.copy()
        archive_a_path = recent_winner_path
        archive_b_points = archive_winner_points.copy()
        archive_b_weights = archive_winner_weights.copy()
        archive_b_path = archive_winner_path

    print()

    # ============================================================
    # STEP 2: 候補生成（各候補ごとに）
    # ============================================================

    #---cand_00: mutate_weak ---
    cand_id = "cand_00"
    print(f"\nGenerating {cand_id} (mutate_weak)...")

    seed = random.randint(1, 2**31 - 1)
    np.random.seed(seed)
    random.seed(seed)

    params_weak = params.copy()
    params_weak['pos_mutation_sigma'] = params['pos_mutation_sigma'] * 0.5
    params_weak['weight_mutation_sigma'] = params['weight_mutation_sigma'] * 0.5
    params_weak['add_point_prob'] = params.get('add_point_prob', 0.1) * 0.5
    params_weak['remove_point_prob'] = params.get('remove_point_prob', 0.1) * 0.5

    points, weights = mutate_genotype(
        recent_winner_points, recent_winner_weights,
        params=params_weak, xy_strategy='PRESERVE_XY'
    )

    print(f"  Initial: {len(points)} points")

    # 制約チェック・修復
    checker = ConstraintChecker(params)
    violations = checker.check_all(points, weights)

    if violations:
        print(f"  ⚠ Found {len(violations)} constraint violations, attempting repair...")
        repaired_points, repaired_weights, repair_log, success = repair_candidate(
            points, weights, params, max_iter=10
        )
        if success:
            points, weights = repaired_points, repaired_weights
            print(f"  ✅ Repair successful ({len(repair_log.actions)} actions)")
        else:
            print(f"  ❌ Repair failed")
    else:
        print(f"  ✅ All constraints satisfied")
        repair_log = None

    # Provenance作成
    provenance = create_mutation_provenance(
        cand_id=cand_id,
        gen_id=gen_id,
        parent_path=recent_winner_path,
        mutation_type="weak",
        xy_strategy="PRESERVE_XY",
        sigma_multiplier=0.5,
        seed=seed
    )

    if repair_log:
        for action in repair_log.actions:
            provenance.add_repair_action(action['issue'], action['action'], action['success'])

    population.append((cand_id, points, weights, provenance))

    # --- cand_01: mutate_strong ---
    cand_id = "cand_01"
    print(f"\nGenerating {cand_id} (mutate_strong)...")

    seed = random.randint(1, 2**31 - 1)
    np.random.seed(seed)
    random.seed(seed)

    params_strong = params.copy()
    params_strong['pos_mutation_sigma'] = params['pos_mutation_sigma'] * 1.5
    params_strong['weight_mutation_sigma'] = params['weight_mutation_sigma'] * 1.5
    params_strong['add_point_prob'] = params.get('add_point_prob', 0.1) * 1.5
    params_strong['remove_point_prob'] = params.get('remove_point_prob', 0.1) * 1.5

    points, weights = mutate_genotype(
        recent_winner_points, recent_winner_weights,
        params=params_strong, xy_strategy='PRESERVE_XY'
    )

    print(f"  Initial: {len(points)} points")

    # 制約チェック・修復
    checker = ConstraintChecker(params)
    violations = checker.check_all(points, weights)

    if violations:
        print(f"  ⚠ Found {len(violations)} constraint violations, attempting repair...")
        repaired_points, repaired_weights, repair_log, success = repair_candidate(
            points, weights, params, max_iter=10
        )
        if success:
            points, weights = repaired_points, repaired_weights
            print(f"  ✅ Repair successful ({len(repair_log.actions)} actions)")
        else:
            print(f"  ❌ Repair failed")
    else:
        print(f"  ✅ All constraints satisfied")
        repair_log = None

    # Provenance作成
    provenance = create_mutation_provenance(
        cand_id=cand_id,
        gen_id=gen_id,
        parent_path=recent_winner_path,
        mutation_type="strong",
        xy_strategy="BREAK_XY",
        sigma_multiplier=1.5,
        seed=seed
    )

    if repair_log:
        for action in repair_log.actions:
            provenance.add_repair_action(action['issue'], action['action'], action['success'])

    population.append((cand_id, points, weights, provenance))

    # --- cand_02: crossover_winner_archive (blend) ---
    cand_id = "cand_02"
    print(f"\nGenerating {cand_id} (crossover_winner_archive)...")

    seed = random.randint(1, 2**31 - 1)
    np.random.seed(seed)
    random.seed(seed)

    points, weights, crossover_info = crossover_genotypes(
    recent_winner_points, recent_winner_weights,
    archive_winner_points, archive_winner_weights,
    params=params,
    crossover_mode='xy_cluster_swap',
    preserve_xy_pairs=True
)

    print(f"  Initial: {len(points)} points (from {crossover_info.get('child_n_points', len(points))} total)")

    # 制約チェック・修復
    checker = ConstraintChecker(params)
    violations = checker.check_all(points, weights)

    if violations:
        print(f"  ⚠ Found {len(violations)} constraint violations, attempting repair...")
        repaired_points, repaired_weights, repair_log, success = repair_candidate(
            points, weights, params, max_iter=10
        )
        if success:
            points, weights = repaired_points, repaired_weights
            print(f"  ✅ Repair successful ({len(repair_log.actions)} actions)")
        else:
            print(f"  ❌ Repair failed")
    else:
        print(f"  ✅ All constraints satisfied")
        repair_log = None

    # Provenance作成
    provenance = create_crossover_provenance(
        cand_id=cand_id,
        gen_id=gen_id,
        parent1_path=recent_winner_path,
        parent2_path=archive_winner_path,
        crossover_type="winner_archive",
        crossover_mode='xy_cluster_swap',
        preserve_xy=True,
        seed=seed
    )

    if repair_log:
        for action in repair_log.actions:
            provenance.add_repair_action(action['issue'], action['action'], action['success'])

    population.append((cand_id, points, weights, provenance))

    # --- cand_03: crossover_archive_archive (uniform) ---
    cand_id = "cand_03"
    print(f"\nGenerating {cand_id} (crossover_archive_archive)...")

    seed = random.randint(1, 2**31 - 1)
    np.random.seed(seed)
    random.seed(seed)

    points, weights, crossover_info = crossover_genotypes(
    archive_a_points, archive_a_weights,
    archive_b_points, archive_b_weights,
    params=params,
    crossover_mode='xy_cluster_swap',
    preserve_xy_pairs=True
)

    print(f"  Initial: {len(points)} points (from {crossover_info.get('child_n_points', len(points))} total)")

    # 制約チェック・修復
    checker = ConstraintChecker(params)
    violations = checker.check_all(points, weights)

    if violations:
        print(f"  ⚠ Found {len(violations)} constraint violations, attempting repair...")
        repaired_points, repaired_weights, repair_log, success = repair_candidate(
            points, weights, params, max_iter=10
        )
        if success:
            points, weights = repaired_points, repaired_weights
            print(f"  ✅ Repair successful ({len(repair_log.actions)} actions)")
        else:
            print(f"  ❌ Repair failed")
    else:
        print(f"  ✅ All constraints satisfied")
        repair_log = None

    # Provenance作成
    provenance = create_crossover_provenance(
        cand_id=cand_id,
        gen_id=gen_id,
        parent1_path=archive_a_path,
        parent2_path=archive_b_path,
        crossover_type="archive_archive",
        crossover_mode='xy_cluster_swap',
        preserve_xy=True,
        seed=seed
    )

    if repair_log:
        for action in repair_log.actions:
            provenance.add_repair_action(action['issue'], action['action'], action['success'])

    population.append((cand_id, points, weights, provenance))

    # --- cand_04: random_baseline ---
    cand_id = "cand_04"
    print(f"\nGenerating {cand_id} (random_baseline)...")

    seed = random.randint(1, 2**31 - 1)
    np.random.seed(seed)
    random.seed(seed)

    target_pairs = params.get('target_pairs', 0)
    points, weights, gen_params = generate_random_genotype(params=params, target_pairs=target_pairs)

    print(f"  Initial: {len(points)} points, {gen_params.get('actual_pairs', 0)} XY-pairs")

    # 制約チェック・修復
    checker = ConstraintChecker(params)
    violations = checker.check_all(points, weights)

    if violations:
        print(f"  ⚠ Found {len(violations)} constraint violations, attempting repair...")
        repaired_points, repaired_weights, repair_log, success = repair_candidate(
            points, weights, params, max_iter=10
        )
        if success:
            points, weights = repaired_points, repaired_weights
            print(f"  ✅ Repair successful ({len(repair_log.actions)} actions)")
        else:
            print(f"  ❌ Repair failed")
    else:
        print(f"  ✅ All constraints satisfied")
        repair_log = None

    # Provenance作成
    provenance = create_random_provenance(
        cand_id=cand_id,
        gen_id=gen_id,
        random_type="baseline",
        target_pairs=target_pairs,
        seed=seed
    )

    if repair_log:
        for action in repair_log.actions:
            provenance.add_repair_action(action['issue'], action['action'], action['success'])

    population.append((cand_id, points, weights, provenance))

    # --- cand_05: random_extreme ---
    cand_id = "cand_05"
    print(f"\nGenerating {cand_id} (random_extreme)...")

    seed = random.randint(1, 2**31 - 1)
    np.random.seed(seed)
    random.seed(seed)

    # Rotate through extreme variants
    variant = gen_id % 4
    if variant == 0:
        random_type = "extreme"
        target_pairs = 30  # High pairs
        params_variant = params.copy()
        params_variant['target_pairs'] = target_pairs
    elif variant == 1:
        random_type = "extreme"
        target_pairs = params.get('target_pairs', 0)  # Use CLI argument
        params_variant = params.copy()
        params_variant['target_pairs'] = target_pairs
    elif variant == 2:
        random_type = "extreme"
        target_pairs = params.get('target_pairs', 0)
        params_variant = params.copy()
        params_variant['weight_min'] = 30
        params_variant['weight_max'] = 70
    else:
        random_type = "extreme"
        target_pairs = params.get('target_pairs', 0)
        params_variant = params.copy()
        params_variant['weight_min'] = 5
        params_variant['weight_max'] = 20

    points, weights, gen_params = generate_random_genotype(params=params_variant, target_pairs=target_pairs)

    print(f"  Initial: {len(points)} points, {gen_params.get('actual_pairs', 0)} XY-pairs")

    # 制約チェック・修復
    checker = ConstraintChecker(params)
    violations = checker.check_all(points, weights)

    if violations:
        print(f"  ⚠ Found {len(violations)} constraint violations, attempting repair...")
        repaired_points, repaired_weights, repair_log, success = repair_candidate(
            points, weights, params, max_iter=10
        )
        if success:
            points, weights = repaired_points, repaired_weights
            print(f"  ✅ Repair successful ({len(repair_log.actions)} actions)")
        else:
            print(f"  ❌ Repair failed")
    else:
        print(f"  ✅ All constraints satisfied")
        repair_log = None

    # Provenance作成
    provenance = create_random_provenance(
        cand_id=cand_id,
        gen_id=gen_id,
        random_type=random_type,
        target_pairs=target_pairs,
        seed=seed
    )

    if repair_log:
        for action in repair_log.actions:
            provenance.add_repair_action(action['issue'], action['action'], action['success'])

    population.append((cand_id, points, weights, provenance))

    print(f"\n{'='*60}")
    print(f"  Generation {gen_id}: {len(population)} candidates created")
    print(f"{'='*60}\n")

    return population


# ==============================================================================
# SAVE POPULATION
# ==============================================================================

def save_population(gen_id: int, population: List, manager: GenerationManager, params: Dict):
    """
    Save all candidates to disk with OBJ export.

    Args:
        gen_id: Generation ID
        population: List of (cand_id, points, weights, provenance) tuples
        manager: GenerationManager instance
        params: Parameter dictionary
    """
    print(f"\n{'='*60}")
    print(f"  SAVING GENERATION {gen_id}")
    print(f"{'='*60}\n")

    # Create generation structure
    manager.create_generation_structure(gen_id)

    bounds_min = np.array(params['bounds_min'])
    bounds_max = np.array(params['bounds_max'])

    for cand_id, points, weights, provenance in population:
        print(f"\nSaving {cand_id}...")

        # Get file paths
        cand_idx = int(cand_id.split('_')[1])
        file_paths = manager.get_candidate_files(gen_id, cand_idx)

        # Save metadata (genotype)
        save_genotype(
            points, weights,
            filepath=file_paths['meta'],
            parent_hash=None,
            iteration=gen_id,
            crossover_info=None,
            params=params,
            generation_params=None
        )
        print(f"  ✅ Saved meta.json")

        # Save provenance
        provenance.save(file_paths['provenance'])
        print(f"  ✅ Saved provenance.json")

        # Export OBJ (mesh)
        sites = np.column_stack([points, weights])
        compute_power_diagram(
            sites, bounds_min, bounds_max,
            output_path=file_paths['mesh'],
            export_spheres=False,
            export_mode='faces'
        )
        print(f"  ✅ Exported mesh.obj")

        # Export mesh_inner (boundary removed)
        compute_power_diagram(
            sites, bounds_min, bounds_max,
            output_path=file_paths['mesh_inner'],
            export_spheres=False,
            export_mode='faces',
            remove_boundary_cells=True
        )
        print(f"  ✅ Exported mesh_inner.obj")

        # Export XY-lines if target_pairs > 0
        target_pairs = params.get('target_pairs', 0)
        if target_pairs > 0:
            try:
                export_xy_pair_lines(points, file_paths['xy_lines'], tolerance=1.0)
                print(f"  ✅ Exported xy_lines.obj")
            except Exception as e:
                print(f"  ⚠ XY-lines export failed: {e}")

    print(f"\n✅ All candidates saved to gen_history/gen_{gen_id:03d}/")


# ==============================================================================
# GENERATION SUMMARY
# ==============================================================================

def compute_generation_summary(gen_id: int, population: List, params: Dict) -> Dict:
    """
    Compute generation summary statistics.

    Args:
        gen_id: Generation ID
        population: List of (cand_id, points, weights, provenance) tuples
        params: Parameter dictionary

    Returns:
        Summary dictionary
    """
    from generate_pair import count_xy_pairs, compute_pair_metrics
    from tools.extract_features import extract_features_from_genotype

    summary = create_initial_generation_summary(gen_id)

    # Count origin types
    origin_counts = {
        "mutate_weak": 0,
        "mutate_strong": 0,
        "crossover_winner_archive": 0,
        "crossover_archive_archive": 0,
        "random_baseline": 0,
        "random_extreme": 0
    }

    xy_pair_counts = []
    mean_pair_dzs = []
    n_points_list = []

    for cand_id, points, weights, provenance in population:
        # Count origins
        origin_type = provenance.origin_type
        if origin_type in origin_counts:
            origin_counts[origin_type] += 1

        # Compute metrics
        n_points_list.append(len(points))

        # XY-pair metrics
        pair_count = count_xy_pairs(points, tolerance=1.0)
        xy_pair_counts.append(pair_count)

        if pair_count > 0:
            metrics = compute_pair_metrics(points, tolerance=1.0)
            mean_pair_dzs.append(metrics['mean_pair_dz'])

    # Update summary
    summary['candidate_origins'] = origin_counts

    summary['population_metrics']['xy_pair_count'] = {
        "mean": float(np.mean(xy_pair_counts)) if xy_pair_counts else 0.0,
        "std": float(np.std(xy_pair_counts)) if xy_pair_counts else 0.0,
        "min": int(min(xy_pair_counts)) if xy_pair_counts else 0,
        "max": int(max(xy_pair_counts)) if xy_pair_counts else 0
    }

    summary['population_metrics']['mean_pair_dz'] = {
        "mean": float(np.mean(mean_pair_dzs)) if mean_pair_dzs else 0.0,
        "std": float(np.std(mean_pair_dzs)) if mean_pair_dzs else 0.0
    }

    summary['population_metrics']['n_points'] = {
        "mean": float(np.mean(n_points_list)),
        "std": float(np.std(n_points_list))
    }

    # Diversity score (simplified: std of n_points as proxy)
    summary['diversity_score'] = float(np.std(n_points_list)) if len(n_points_list) > 1 else 0.0

    return summary


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="6-Candidate Generation System"
    )
    parser.add_argument(
        '--gen-id',
        type=int,
        required=True,
        help="Generation ID (0 for bootstrap, 1+ for evolution)"
    )
    parser.add_argument(
        '--n-points',
        type=int,
        default=100,
        help="Number of points (excluding fixed points)"
    )
    parser.add_argument(
        '--target-pairs',
        type=int,
        default=40,
        help="Target number of XY-pairs"
    )
    parser.add_argument(
        '--base-dir',
        type=str,
        default='../gen_history',
        help="Base directory for generation history"
    )

    args = parser.parse_args()

    # Setup parameters
    params = DEFAULT_PARAMS.copy()
    params['n_points'] = args.n_points
    params['target_pairs'] = args.target_pairs

    # Initialize manager
    manager = GenerationManager(base_dir=args.base_dir)

    print(f"\n{'='*60}")
    print(f"  6-CANDIDATE GENERATION SYSTEM")
    print(f"{'='*60}")
    print(f"  Generation ID: {args.gen_id}")
    print(f"  n_points: {args.n_points} (+ 2 fixed)")
    print(f"  target_pairs: {args.target_pairs}")
    print(f"  Base directory: {os.path.abspath(args.base_dir)}")
    print(f"{'='*60}\n")

    # Generate population
    if args.gen_id == 0:
        # Bootstrap: all random
        population = generate_bootstrap_population(args.gen_id, params, manager)
    elif args.gen_id >= 1:
        # Evolution: GA4 + Random2
        population = generate_evolution_population(args.gen_id, params, manager)
    else:
        print("❌ Invalid gen_id")
        sys.exit(1)

    # Save population
    save_population(args.gen_id, population, manager, params)

    # Compute and save summary
    summary = compute_generation_summary(args.gen_id, population, params)
    manager.save_generation_summary(args.gen_id, summary)

    print(f"\n{'='*60}")
    print(f"  GENERATION SUMMARY")
    print(f"{'='*60}")
    print(json.dumps(summary, indent=2))
    print(f"\n{'='*60}")
    print(f"  ✅ GENERATION {args.gen_id} COMPLETE")
    print(f"{'='*60}\n")

    print("Next steps:")
    print(f"  1. View candidates in Rhino:")
    print(f"     gen_history/gen_{args.gen_id:03d}/population/cand_XX/mesh.obj")
    print(f"  2. Run Phase 2 comparison loop (not yet implemented)")


if __name__ == "__main__":
    main()
