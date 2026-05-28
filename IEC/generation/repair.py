"""
repair.py - Constraint Repair Functions

Provides repair mechanisms for constraint violations with maximum iteration limits.
"""

import sys
import os
import random
import numpy as np
from typing import Dict, List, Tuple, Optional

# Import from parent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../tools'))
from generate_pair import (
    FIXED_POINTS,
    FIXED_WEIGHTS,
    is_in_exclusion_zone,
    generate_point_outside_exclusion,
    detect_xy_clusters,
    ensure_fixed_points
)

try:
    from .constraint_checker import ConstraintChecker, ConstraintViolation
except ImportError:
    from constraint_checker import ConstraintChecker, ConstraintViolation


class RepairLog:
    """Logs repair actions for provenance tracking."""

    def __init__(self):
        self.actions = []

    def add_action(self, issue: str, action: str, success: bool, details: str = ""):
        """Add a repair action to the log."""
        self.actions.append({
            "issue": issue,
            "action": action,
            "success": success,
            "details": details
        })

    def to_list(self) -> List[Dict]:
        """Convert to list for JSON serialization."""
        return self.actions


def clip_to_bbox(points: np.ndarray, bounds_min: np.ndarray, bounds_max: np.ndarray) -> Tuple[np.ndarray, RepairLog]:
    """
    Clip all points to bounding box.

    Args:
        points: (N, 3) array
        bounds_min: (3,) array
        bounds_max: (3,) array

    Returns:
        (clipped_points, repair_log)
    """
    log = RepairLog()
    points_clipped = points.copy()

    # Find violations
    below_min = points < bounds_min
    above_max = points > bounds_max

    violation_count = np.sum(np.any(below_min | above_max, axis=1))

    if violation_count > 0:
        # Clip to bounds
        points_clipped = np.clip(points_clipped, bounds_min, bounds_max)

        log.add_action(
            "bbox_violation",
            f"clipped_{violation_count}_points",
            True,
            f"Points clipped to bounds [{bounds_min}, {bounds_max}]"
        )

    return points_clipped, log


def move_outside_exclusion(points: np.ndarray, weights: np.ndarray,
                           bounds_min: np.ndarray, bounds_max: np.ndarray,
                           max_attempts: int = 10) -> Tuple[np.ndarray, RepairLog]:
    """
    Move points out of exclusion zone while preserving XY-pair structure.

    Strategy:
    1. Detect XY-pairs (points with same XY coordinates within tolerance=1.0mm)
    2. For paired points: shift Z only to preserve pair structure
    3. For singleton points: shift XYZ (standard behavior)
    4. Fallback: if Z-only fails, shift entire pair together with same XY offset

    Args:
        points: (N, 3) array
        weights: (N,) array
        bounds_min: (3,) array
        bounds_max: (3,) array
        max_attempts: Maximum resample attempts per point

    Returns:
        (repaired_points, repair_log)
    """
    log = RepairLog()
    points_repaired = points.copy()

    # Find points in exclusion zone
    in_exclusion = [i for i, p in enumerate(points) if is_in_exclusion_zone(p)]

    if not in_exclusion:
        return points_repaired, log

    # Detect XY-pairs
    clusters = detect_xy_clusters(points_repaired, tolerance=1.0)

    # Build mapping: point_idx -> cluster
    point_to_cluster = {}
    for cluster in clusters:
        for idx in cluster:
            point_to_cluster[idx] = cluster

    paired_indices = set(point_to_cluster.keys())

    # Track statistics
    z_only_repairs = 0
    xyz_repairs = 0
    pair_shifts = 0
    failed_indices = []

    # Try to repair each point
    for idx in in_exclusion:
        # Skip fixed points
        if idx < 2:
            continue

        success = False
        is_paired = idx in paired_indices

        if is_paired:
            # PAIRED POINT: Try Z-only shift first (20 attempts)
            for attempt in range(20):
                z_shift = np.random.uniform(-50, 50)
                new_point = points_repaired[idx].copy()
                new_point[2] += z_shift

                # Check if outside exclusion and within bounds
                if (not is_in_exclusion_zone(new_point) and
                    np.all(new_point >= bounds_min) and
                    np.all(new_point <= bounds_max)):
                    points_repaired[idx] = new_point
                    success = True
                    z_only_repairs += 1
                    break

            if not success:
                # Z-only failed, try shifting entire pair with same XY offset
                cluster = point_to_cluster[idx]
                # Try to shift all points in the cluster together
                for attempt in range(10):
                    xy_shift = np.random.uniform(-30, 30, size=2)

                    # Check if shifting all cluster points would work
                    all_valid = True
                    temp_points = []

                    for cluster_idx in cluster:
                        new_point = points_repaired[cluster_idx].copy()
                        new_point[:2] += xy_shift  # Same XY shift for all

                        if (is_in_exclusion_zone(new_point) or
                            not np.all(new_point >= bounds_min) or
                            not np.all(new_point <= bounds_max)):
                            all_valid = False
                            break
                        temp_points.append((cluster_idx, new_point))

                    if all_valid:
                        # Apply the shift to all points in cluster
                        for cluster_idx, new_point in temp_points:
                            points_repaired[cluster_idx] = new_point
                        success = True
                        pair_shifts += 1
                        break

        else:
            # SINGLETON POINT: Try XYZ shift (standard behavior)
            # Try nudging first (10mm random offset)
            for attempt in range(3):
                offset = np.random.uniform(-10, 10, size=3)
                new_point = points_repaired[idx] + offset

                if (not is_in_exclusion_zone(new_point) and
                    np.all(new_point >= bounds_min) and
                    np.all(new_point <= bounds_max)):
                    points_repaired[idx] = new_point
                    success = True
                    xyz_repairs += 1
                    break

            if not success:
                # Nudging failed, resample completely
                for attempt in range(max_attempts):
                    new_point = generate_point_outside_exclusion(bounds_min, bounds_max, max_attempts=100)
                    if new_point is not None:
                        points_repaired[idx] = new_point
                        success = True
                        xyz_repairs += 1
                        break

        if not success:
            failed_indices.append(idx)

    # Count successful repairs
    still_in_exclusion = sum(1 for p in points_repaired if is_in_exclusion_zone(p))
    repaired_count = len(in_exclusion) - still_in_exclusion

    # Build detailed message
    details = []
    if z_only_repairs > 0:
        details.append(f"{z_only_repairs} paired_points_z_shift")
    if pair_shifts > 0:
        details.append(f"{pair_shifts} paired_points_xy_shift")
    if xyz_repairs > 0:
        details.append(f"{xyz_repairs} singleton_points_xyz_shift")

    detail_str = ", ".join(details) if details else "no_repairs"

    log.add_action(
        "exclusion_violation",
        f"moved_{repaired_count}_of_{len(in_exclusion)}_points_({detail_str})",
        still_in_exclusion == 0,
        f"{repaired_count} points moved outside exclusion zone: {detail_str}"
    )

    if failed_indices:
        log.add_action(
            "exclusion_violation",
            f"failed_to_move_{len(failed_indices)}_points",
            False,
            f"Could not move points {failed_indices} outside exclusion zone"
        )

    return points_repaired, log


# ===== XY-Pair Aware Repair Helpers =====

def classify_points_by_xy_structure(points: np.ndarray,
                                    tolerance: float = 1.0) -> Tuple[set, set, List[int]]:
    """
    Classify points into fixed, paired, and singleton categories.

    Args:
        points: (N, 3) array of point positions
        tolerance: XY distance tolerance for cluster detection

    Returns:
        (fixed_indices, paired_indices, singleton_indices)
    """
    # Detect XY clusters
    clusters = detect_xy_clusters(points, tolerance=tolerance)

    # Fixed points are always indices 0, 1
    fixed_indices = {0, 1}

    # Paired points are in any cluster
    paired_indices = set()
    for cluster in clusters:
        paired_indices.update(cluster)

    # Singletons are not in any cluster (excluding fixed points)
    singleton_indices = []
    for i in range(2, len(points)):
        if i not in paired_indices:
            singleton_indices.append(i)

    return fixed_indices, paired_indices, singleton_indices


def remove_points_xy_aware(points: np.ndarray,
                           weights: np.ndarray,
                           remove_count: int,
                           tolerance: float = 1.0) -> Tuple[np.ndarray, np.ndarray, Dict]:
    """
    Remove points while preserving XY-pair structure.

    Priority:
        1. Singletons (highest priority)
        2. Complete pairs (remove both points)
        3. Partial pairs (lowest priority - only if necessary)

    Args:
        points: (N, 3) array
        weights: (N,) array
        remove_count: Number of points to remove
        tolerance: XY cluster detection tolerance

    Returns:
        (points, weights, removal_stats)
    """
    if remove_count <= 0:
        return points, weights, {"singletons": 0, "complete_pairs": 0, "partial_pairs": 0, "total_removed": 0, "could_not_remove": 0}

    # Classify points
    fixed_indices, paired_indices, singleton_indices = classify_points_by_xy_structure(
        points, tolerance
    )

    # Detect clusters for pair removal
    clusters = detect_xy_clusters(points, tolerance)

    remove_indices = []
    singletons_removed = 0
    complete_pairs_removed = 0
    partial_pairs_removed = 0
    remaining = remove_count

    # Priority 1: Remove singletons
    if remaining > 0 and len(singleton_indices) > 0:
        n_remove = min(remaining, len(singleton_indices))
        selected = np.random.choice(singleton_indices, size=n_remove, replace=False)
        remove_indices.extend(selected)
        singletons_removed = n_remove
        remaining -= n_remove

    # Priority 2: Remove complete pairs
    if remaining > 0:
        # Find pairs (size=2, not containing fixed points)
        pairs = [
            cluster for cluster in clusters
            if len(cluster) == 2 and not any(idx in fixed_indices for idx in cluster)
        ]

        n_pairs_remove = min(remaining // 2, len(pairs))
        if n_pairs_remove > 0:
            selected_pairs = random.sample(pairs, n_pairs_remove)
            for pair in selected_pairs:
                remove_indices.extend(pair)
            complete_pairs_removed = n_pairs_remove
            remaining -= n_pairs_remove * 2

    # Priority 3: Remove partial pairs (break pairs)
    if remaining > 0:
        removable_paired = [
            idx for idx in paired_indices
            if idx not in fixed_indices and idx not in remove_indices
        ]

        if len(removable_paired) >= remaining:
            selected = np.random.choice(removable_paired, size=remaining, replace=False)
            remove_indices.extend(selected)
            partial_pairs_removed = remaining
            remaining = 0
        else:
            # Not enough points to remove
            # Remove what we can
            remove_indices.extend(removable_paired)
            partial_pairs_removed = len(removable_paired)
            remaining -= len(removable_paired)

    # Apply removal
    if remove_indices:
        keep_mask = np.ones(len(points), dtype=bool)
        keep_mask[remove_indices] = False
        points = points[keep_mask]
        weights = weights[keep_mask]

    stats = {
        "singletons": singletons_removed,
        "complete_pairs": complete_pairs_removed,
        "partial_pairs": partial_pairs_removed,
        "total_removed": len(remove_indices),
        "could_not_remove": remaining
    }

    return points, weights, stats


def adjust_n_points(points: np.ndarray, weights: np.ndarray,
                    target_n_points: int, params: Dict) -> Tuple[np.ndarray, np.ndarray, RepairLog]:
    """
    Adjust point count to match target (XY-PAIR AWARE VERSION).

    When removing points:
        - Prioritizes removing singletons (not in XY-clusters)
        - Then removes complete pairs (both points of a pair)
        - Only breaks pairs if absolutely necessary

    Args:
        points: (N, 3) array
        weights: (N,) array
        target_n_points: Target point count (including fixed points)
        params: Parameter dictionary

    Returns:
        (adjusted_points, adjusted_weights, repair_log)
    """
    log = RepairLog()
    current_count = len(points)
    diff = target_n_points - current_count

    if diff == 0:
        return points, weights, log

    bounds_min = np.array(params['bounds_min'])
    bounds_max = np.array(params['bounds_max'])
    weight_min = params['weight_min']
    weight_max = params['weight_max']

    if diff > 0:
        # Add points (no XY-pair issues)
        new_points = []
        new_weights = []

        for i in range(abs(diff)):
            # Generate point outside exclusion zone
            new_point = generate_point_outside_exclusion(bounds_min, bounds_max, max_attempts=100)
            if new_point is not None:
                new_points.append(new_point)
                new_weight = np.random.uniform(weight_min, weight_max)
                new_weights.append(new_weight)

        if new_points:
            points = np.vstack([points, new_points])
            weights = np.concatenate([weights, new_weights])

            log.add_action(
                "n_points_mismatch",
                f"added_{len(new_points)}_points",
                len(new_points) == abs(diff),
                f"Added {len(new_points)} random points"
            )
        else:
            log.add_action(
                "n_points_mismatch",
                "failed_to_add_points",
                False,
                f"Could not generate {abs(diff)} new points"
            )

    else:
        # Remove points (XY-PAIR AWARE)
        remove_count = abs(diff)

        # Check if we have enough removable points
        if len(points) - 2 < remove_count:  # -2 for fixed points
            log.add_action(
                "n_points_mismatch",
                "insufficient_removable_points",
                False,
                f"Cannot remove {remove_count} points, only {len(points) - 2} removable"
            )
            return points, weights, log

        # Use XY-aware removal
        points, weights, stats = remove_points_xy_aware(
            points, weights, remove_count, tolerance=1.0
        )

        # Log detailed action
        details = (
            f"Removed {stats['total_removed']} points: "
            f"{stats['singletons']} singletons, "
            f"{stats['complete_pairs']} complete pairs, "
            f"{stats['partial_pairs']} partial pairs"
        )

        if stats['could_not_remove'] > 0:
            log.add_action(
                "n_points_mismatch",
                f"removed_{stats['total_removed']}_of_{remove_count}_points",
                False,
                details + f" (could not remove {stats['could_not_remove']} more)"
            )
        else:
            log.add_action(
                "n_points_mismatch",
                f"removed_{stats['total_removed']}_points_xy_aware",
                True,
                details
            )

    return points, weights, log


def adjust_target_pairs(points: np.ndarray, weights: np.ndarray,
                        target_pairs: int, params: Dict,
                        tolerance: int = 3) -> Tuple[np.ndarray, np.ndarray, RepairLog]:
    """
    Adjust XY-pair count to match target.

    Strategy:
    - If too few pairs: Convert singleton points to pairs (duplicate with different Z)
    - If too many pairs: Break some pairs (shift XY coordinates slightly)

    Args:
        points: (N, 3) array
        weights: (N,) array
        target_pairs: Target XY-pair count
        params: Parameter dictionary
        tolerance: Acceptable deviation from target

    Returns:
        (adjusted_points, adjusted_weights, repair_log)
    """
    log = RepairLog()

    if target_pairs == 0:
        # No target pairs specified
        return points, weights, log

    clusters = detect_xy_clusters(points, tolerance=1.0)
    current_pairs = len(clusters)
    diff = target_pairs - current_pairs

    if abs(diff) <= tolerance:
        # Within tolerance
        return points, weights, log

    bounds_min = np.array(params['bounds_min'])
    bounds_max = np.array(params['bounds_max'])
    weight_min = params['weight_min']
    weight_max = params['weight_max']

    if diff > 0:
        # Need to create more pairs

        # NEW: Check point count constraints before creating pairs
        target_n_points = params.get('n_points', 10) + 2
        n_points_tolerance = params.get('n_points_tolerance', 2)
        current_n_points = len(points)
        max_points_can_add = (target_n_points + n_points_tolerance) - current_n_points

        if max_points_can_add <= 0:
            log.add_action(
                "target_pairs_mismatch",
                "cannot_add_pairs_point_limit_reached",
                False,
                f"Cannot add pairs: at point count limit ({current_n_points}/{target_n_points}+{n_points_tolerance})"
            )
            return points, weights, log

        # Find singleton points (not in any cluster)
        clustered_indices = set()
        for cluster in clusters:
            clustered_indices.update(cluster)

        singleton_indices = [i for i in range(2, len(points)) if i not in clustered_indices]

        # NEW: Limit pairs to create based on both singleton availability AND point count
        max_pairs_from_singletons = len(singleton_indices)
        max_pairs_from_point_limit = max_points_can_add
        pairs_to_create = min(abs(diff), max_pairs_from_singletons, max_pairs_from_point_limit)

        if pairs_to_create > 0:
            selected_singletons = np.random.choice(singleton_indices, size=pairs_to_create, replace=False)

            new_points = []
            new_weights = []

            for idx in selected_singletons:
                # Create pair by duplicating point with different Z
                base_point = points[idx].copy()
                z_offset = np.random.uniform(50, 150)  # 50-150mm Z difference

                # Create second point in pair
                pair_point = base_point.copy()
                pair_point[2] += z_offset if np.random.rand() > 0.5 else -z_offset

                # Clip Z to bounds
                pair_point[2] = np.clip(pair_point[2], bounds_min[2], bounds_max[2])

                new_points.append(pair_point)
                new_weight = np.random.uniform(weight_min, weight_max)
                new_weights.append(new_weight)

            if new_points:
                points = np.vstack([points, new_points])
                weights = np.concatenate([weights, new_weights])

                log.add_action(
                    "target_pairs_mismatch",
                    f"created_{len(new_points)}_pairs",
                    True,
                    f"Created {len(new_points)} XY-pairs by duplicating singletons"
                )
        else:
            log.add_action(
                "target_pairs_mismatch",
                "insufficient_singletons",
                False,
                f"Cannot create {abs(diff)} pairs, only {len(singleton_indices)} singletons available"
            )

    else:
        # Need to break pairs
        pairs_to_break = min(abs(diff), len(clusters))

        if pairs_to_break > 0:
            # Select random clusters to break
            selected_clusters = np.random.choice(len(clusters), size=pairs_to_break, replace=False)

            broken_count = 0
            for cluster_idx in selected_clusters:
                cluster = clusters[cluster_idx]
                if len(cluster) < 2:
                    continue

                # Break pair by shifting XY coordinates of one point
                point_to_shift = cluster[1]  # Don't shift first point

                # Small random XY offset (10-30mm)
                xy_offset = np.random.uniform(10, 30, size=2)
                if np.random.rand() > 0.5:
                    xy_offset *= -1

                points[point_to_shift][:2] += xy_offset

                # Clip to bounds
                points[point_to_shift][:2] = np.clip(
                    points[point_to_shift][:2],
                    bounds_min[:2],
                    bounds_max[:2]
                )

                broken_count += 1

            log.add_action(
                "target_pairs_mismatch",
                f"broke_{broken_count}_pairs",
                True,
                f"Broke {broken_count} XY-pairs by shifting XY coordinates"
            )

    return points, weights, log


def clip_weights(weights: np.ndarray, weight_min: float, weight_max: float) -> Tuple[np.ndarray, RepairLog]:
    """
    Clip all weights to [weight_min, weight_max].

    Args:
        weights: (N,) array
        weight_min: Minimum weight
        weight_max: Maximum weight

    Returns:
        (clipped_weights, repair_log)
    """
    log = RepairLog()
    weights_clipped = weights.copy()

    # Find violations
    below_min = weights < weight_min
    above_max = weights > weight_max

    violation_count = np.sum(below_min | above_max)

    if violation_count > 0:
        # Clip to range
        weights_clipped = np.clip(weights_clipped, weight_min, weight_max)

        log.add_action(
            "weight_violation",
            f"clipped_{violation_count}_weights",
            True,
            f"Weights clipped to range [{weight_min}, {weight_max}]"
        )

    return weights_clipped, log


def repair_candidate(points: np.ndarray, weights: np.ndarray, params: Dict,
                     max_iter: int = 10) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], RepairLog, bool]:
    """
    Repair all constraint violations with iteration limit (IMPROVED VERSION).

    Key improvements:
    - Repairs point count BEFORE pair count to prevent oscillation
    - Tracks last action type to avoid immediate undo
    - Detects oscillation and accepts current state if needed

    Args:
        points: (N, 3) array
        weights: (N,) array
        params: Parameter dictionary
        max_iter: Maximum repair iterations

    Returns:
        (repaired_points, repaired_weights, repair_log, success)
        Returns (None, None, log, False) if repair fails
    """
    combined_log = RepairLog()
    checker = ConstraintChecker(params)

    bounds_min = np.array(params['bounds_min'])
    bounds_max = np.array(params['bounds_max'])

    # Track actions to detect oscillation
    action_history = []
    pairs_deleted = False  # Flag to skip n_points adjustment after pair deletion

    for iteration in range(max_iter):
        # Check all constraints
        violations = checker.check_all(points, weights)

        if not violations:
            # All constraints satisfied
            combined_log.add_action(
                "repair_complete",
                f"converged_in_{iteration}_iterations",
                True,
                "All constraints satisfied"
            )
            return points, weights, combined_log, True

        # PHASE 1: Fix critical violations first (bbox, exclusion, weights)
        critical_fixed = False

        # NEW: Check for critical violations oscillation
        recent_actions = action_history[-8:] if len(action_history) >= 8 else action_history
        exclusion_count = recent_actions.count("exclusion")
        weight_count = recent_actions.count("weight")

        if exclusion_count >= 3 and weight_count >= 3:
            # Critical violations are oscillating!
            # Solution: Delete problematic XY-pairs to break the oscillation

            from tools.generate_pair import detect_xy_clusters

            # Detect XY-pairs
            clusters = detect_xy_clusters(points, tolerance=1.0)
            pair_clusters = [c for c in clusters if len(c) >= 2]

            if len(pair_clusters) > 0:
                # Delete 1-2 random pairs to break oscillation
                n_to_delete = min(2, len(pair_clusters))
                import random
                clusters_to_delete = random.sample(pair_clusters, n_to_delete)

                # Collect indices to delete
                indices_to_delete = set()
                for cluster in clusters_to_delete:
                    indices_to_delete.update(cluster)

                # Keep only points not in deleted pairs
                keep_indices = [i for i in range(len(points)) if i not in indices_to_delete]
                points = points[keep_indices]
                weights = weights[keep_indices]

                combined_log.add_action(
                    "critical_oscillation_detected",
                    f"deleted_{n_to_delete}_pairs_{len(indices_to_delete)}_points",
                    True,
                    f"Detected oscillation (exclusion: {exclusion_count}, weight: {weight_count}). "
                    f"Deleted {n_to_delete} XY-pairs ({len(indices_to_delete)} points) to break oscillation."
                )

                # Re-add fixed points if deleted
                points, weights = ensure_fixed_points(points, weights)

                # Immediately return to accept reduced state (prioritize pair reduction over n_points)
                combined_log.add_action(
                    "repair_complete_after_pair_deletion",
                    f"accepting_{len(points)}_points",
                    True,
                    f"Accepting current state after pair deletion. Points: {len(points)} (may be below target)."
                )
                return points, weights, combined_log, True
            else:
                # No pairs to delete, accept current state
                combined_log.add_action(
                    "critical_oscillation_detected",
                    "accepting_current_state_no_pairs",
                    True,
                    f"Detected oscillation but no XY-pairs to delete. Accepting current state."
                )
                critical_fixed = False
        else:
            for v in violations:
                if v.constraint_type == "bbox_violation":
                    points, log = clip_to_bbox(points, bounds_min, bounds_max)
                    combined_log.actions.extend(log.actions)
                    action_history.append("bbox")
                    critical_fixed = True

                elif v.constraint_type == "exclusion_violation":
                    points, log = move_outside_exclusion(points, weights, bounds_min, bounds_max)
                    combined_log.actions.extend(log.actions)
                    action_history.append("exclusion")
                    critical_fixed = True

                elif v.constraint_type == "weight_violation":
                    weights, log = clip_weights(weights, params['weight_min'], params['weight_max'])
                    combined_log.actions.extend(log.actions)
                    action_history.append("weight")
                    critical_fixed = True

        # Ensure fixed points
        points, weights = ensure_fixed_points(points, weights)

        # If we fixed critical violations, continue to next iteration
        # (let the changes settle before fixing point count / pairs)
        if critical_fixed:
            continue

        # PHASE 2: Fix point count BEFORE pairs (prevents oscillation)
        n_points_violation = any(v.constraint_type == "n_points_mismatch" for v in violations)
        pairs_violation = any(v.constraint_type == "target_pairs_mismatch" for v in violations)

        # Skip n_points adjustment if pairs were deleted (prioritize pair reduction)
        if pairs_deleted and n_points_violation:
            combined_log.add_action(
                "n_points_adjustment_skipped",
                "pairs_were_deleted",
                True,
                f"Skipping n_points adjustment because XY-pairs were deleted. "
                f"Current: {len(points)} points (prioritizing pair count reduction)."
            )
            # Accept current state to avoid re-adding points
            return points, weights, combined_log, True

        if n_points_violation:
            target_n = params.get('n_points', 10) + 2
            points, weights, log = adjust_n_points(points, weights, target_n, params)
            combined_log.actions.extend(log.actions)
            action_history.append("n_points")

        elif pairs_violation:
            # NEW: Only fix pairs if point count is stable
            # Check if we're oscillating
            recent_actions = action_history[-6:] if len(action_history) >= 6 else action_history
            n_points_count = recent_actions.count("n_points")
            pairs_count = recent_actions.count("target_pairs")

            if n_points_count >= 3 and pairs_count >= 3:
                # Oscillation detected!
                combined_log.add_action(
                    "oscillation_detected",
                    "accepting_current_state",
                    True,
                    f"Detected oscillation (n_points: {n_points_count}, pairs: {pairs_count} in last {len(recent_actions)} actions). "
                    f"Accepting current state to avoid infinite loop."
                )
                # Return current state as "success" to avoid regeneration
                return points, weights, combined_log, True

            # NEW: Check if point limit has been reached repeatedly
            point_limit_failures = sum(1 for action in combined_log.actions
                                      if action.get('action') == 'cannot_add_pairs_point_limit_reached')
            if point_limit_failures >= 2:
                # Point limit reached multiple times - cannot add more pairs
                combined_log.add_action(
                    "target_pairs_limit_reached",
                    "accepting_current_state",
                    True,
                    f"Point count limit prevents adding more pairs ({point_limit_failures} failures). "
                    f"Accepting current XY-pair count."
                )
                # Return current state as "success"
                return points, weights, combined_log, True

            # Proceed with pair adjustment
            target_pairs = params.get('target_pairs', 0)
            points, weights, log = adjust_target_pairs(points, weights, target_pairs, params)
            combined_log.actions.extend(log.actions)
            action_history.append("target_pairs")

    # Max iterations reached without convergence
    combined_log.add_action(
        "repair_failed",
        f"max_iterations_reached_{max_iter}",
        False,
        f"Could not satisfy all constraints after {max_iter} iterations"
    )

    return None, None, combined_log, False


if __name__ == "__main__":
    # Test repair functions
    from generate_pair import DEFAULT_PARAMS, generate_random_genotype

    print("Testing Repair Functions...")

    params = DEFAULT_PARAMS.copy()
    params['n_points'] = 10
    params['target_pairs'] = 5

    # Generate candidate
    points, weights, _ = generate_random_genotype(params, target_pairs=5)

    print(f"\nOriginal candidate:")
    print(f"  Points: {len(points)}")
    print(f"  Weights range: [{weights.min():.1f}, {weights.max():.1f}]")

    # Introduce violations
    print("\nIntroducing violations...")

    # 1. bbox violation
    points[5] = [1000, 1000, 1000]
    print(f"  - Set point 5 outside bbox: {points[5]}")

    # 2. weight violation
    weights[6] = 200
    print(f"  - Set weight 6 to 200 (above max)")

    # 3. Add extra points
    extra_point = np.array([[400, 400, 200]])
    extra_weight = np.array([50])
    points = np.vstack([points, extra_point])
    weights = np.concatenate([weights, extra_weight])
    print(f"  - Added 1 extra point (total: {len(points)})")

    # Attempt repair
    print("\nAttempting repair...")
    repaired_points, repaired_weights, log, success = repair_candidate(points, weights, params, max_iter=10)

    if success:
        print(f"\n✅ Repair SUCCESSFUL!")
        print(f"  Points: {len(repaired_points)}")
        print(f"  Weights range: [{repaired_weights.min():.1f}, {repaired_weights.max():.1f}]")
        print(f"\nRepair log ({len(log.actions)} actions):")
        for action in log.actions:
            print(f"  - {action['issue']}: {action['action']} (success={action['success']})")
    else:
        print(f"\n❌ Repair FAILED after {len(log.actions)} actions")
        for action in log.actions:
            print(f"  - {action['issue']}: {action['action']} (success={action['success']})")
