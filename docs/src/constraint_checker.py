"""
constraint_checker.py - Constraint Validation

Checks 6 types of constraints for generated candidates:
1. Fixed points present
2. Bounding box compliance
3. Exclusion zone avoidance
4. Point count target
5. XY-pair count target
6. Weight range compliance
"""

import sys
import os
import numpy as np
from typing import Dict, List, Tuple

# Import from parent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../tools'))
from generate_pair import (
    FIXED_POINTS,
    is_fixed_point,
    is_in_exclusion_zone,
    count_xy_pairs
)


class ConstraintViolation:
    """Represents a single constraint violation."""

    def __init__(self, constraint_type: str, description: str, severity: str = "error"):
        """
        Initialize ConstraintViolation.

        Args:
            constraint_type: Type of constraint violated
            description: Human-readable description
            severity: "error" or "warning"
        """
        self.constraint_type = constraint_type
        self.description = description
        self.severity = severity

    def __repr__(self):
        return f"<ConstraintViolation: {self.constraint_type} - {self.description}>"

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "type": self.constraint_type,
            "description": self.description,
            "severity": self.severity
        }


class ConstraintChecker:
    """Checks all constraints for a candidate."""

    def __init__(self, params: Dict):
        """
        Initialize ConstraintChecker.

        Args:
            params: Parameter dictionary containing:
                - bounds_min: [xmin, ymin, zmin]
                - bounds_max: [xmax, ymax, zmax]
                - weight_min: Minimum weight
                - weight_max: Maximum weight
                - n_points: Target point count (excluding fixed points)
                - target_pairs: Target XY-pair count
                - n_points_tolerance: Tolerance for point count (default: 2)
                - target_pairs_tolerance: Tolerance for pair count (default: 3)
        """
        self.params = params
        self.bounds_min = np.array(params['bounds_min'])
        self.bounds_max = np.array(params['bounds_max'])
        self.weight_min = params['weight_min']
        self.weight_max = params['weight_max']
        self.target_n_points = params.get('n_points', 10) + 2  # +2 for fixed points
        self.target_pairs = params.get('target_pairs', 0)
        self.n_points_tolerance = params.get('n_points_tolerance', 2)
        self.pairs_tolerance = params.get('target_pairs_tolerance', 3)

    def check_all(self, points: np.ndarray, weights: np.ndarray) -> List[ConstraintViolation]:
        """
        Check all constraints.

        Args:
            points: (N, 3) array of point coordinates
            weights: (N,) array of weights

        Returns:
            List of ConstraintViolation objects (empty if all pass)
        """
        violations = []

        # Check each constraint
        violations.extend(self.check_fixed_points(points, weights))
        violations.extend(self.check_bounding_box(points))
        violations.extend(self.check_exclusion_zone(points))
        violations.extend(self.check_point_count(points))
        violations.extend(self.check_target_pairs(points))
        violations.extend(self.check_weight_range(weights))

        return violations

    def check_fixed_points(self, points: np.ndarray, weights: np.ndarray) -> List[ConstraintViolation]:
        """
        Check that fixed points are present at indices 0 and 1.

        Args:
            points: (N, 3) array
            weights: (N,) array

        Returns:
            List of violations
        """
        violations = []

        if len(points) < 2:
            violations.append(ConstraintViolation(
                "fixed_points_missing",
                f"Need at least 2 points for fixed points, got {len(points)}"
            ))
            return violations

        # Check first two points are fixed
        for i in range(2):
            if not is_fixed_point(points[i]):
                violations.append(ConstraintViolation(
                    "fixed_point_mismatch",
                    f"Point {i} is not a fixed point: {points[i]}"
                ))

        return violations

    def check_bounding_box(self, points: np.ndarray) -> List[ConstraintViolation]:
        """
        Check that all points are within bounding box.

        Args:
            points: (N, 3) array

        Returns:
            List of violations
        """
        violations = []

        # Check lower bounds
        below_min = points < self.bounds_min
        if np.any(below_min):
            count = np.sum(np.any(below_min, axis=1))
            violations.append(ConstraintViolation(
                "bbox_violation",
                f"{count} points below minimum bounds"
            ))

        # Check upper bounds
        above_max = points > self.bounds_max
        if np.any(above_max):
            count = np.sum(np.any(above_max, axis=1))
            violations.append(ConstraintViolation(
                "bbox_violation",
                f"{count} points above maximum bounds"
            ))

        return violations

    def check_exclusion_zone(self, points: np.ndarray) -> List[ConstraintViolation]:
        """
        Check that no points are in exclusion zone.

        Exclusion zone: X[200-600], Y[200-500], Z[0-300]

        Args:
            points: (N, 3) array

        Returns:
            List of violations
        """
        violations = []

        exclusion_count = 0
        for i, point in enumerate(points):
            if is_in_exclusion_zone(point):
                exclusion_count += 1

        if exclusion_count > 0:
            violations.append(ConstraintViolation(
                "exclusion_violation",
                f"{exclusion_count} points in exclusion zone"
            ))

        return violations

    def check_point_count(self, points: np.ndarray) -> List[ConstraintViolation]:
        """
        Check that point count is within tolerance of target.

        Args:
            points: (N, 3) array

        Returns:
            List of violations
        """
        violations = []

        actual_count = len(points)
        diff = abs(actual_count - self.target_n_points)

        if diff > self.n_points_tolerance:
            violations.append(ConstraintViolation(
                "n_points_mismatch",
                f"Point count {actual_count} differs from target {self.target_n_points} by {diff} (tolerance: {self.n_points_tolerance})"
            ))

        return violations

    def check_target_pairs(self, points: np.ndarray) -> List[ConstraintViolation]:
        """
        Check that XY-pair count is within tolerance of target.

        Args:
            points: (N, 3) array

        Returns:
            List of violations
        """
        violations = []

        if self.target_pairs == 0:
            # No target pairs specified, skip check
            return violations

        actual_pairs = count_xy_pairs(points, tolerance=1.0)
        diff = abs(actual_pairs - self.target_pairs)

        if diff > self.pairs_tolerance:
            violations.append(ConstraintViolation(
                "target_pairs_mismatch",
                f"XY-pair count {actual_pairs} differs from target {self.target_pairs} by {diff} (tolerance: {self.pairs_tolerance})"
            ))

        return violations

    def check_weight_range(self, weights: np.ndarray) -> List[ConstraintViolation]:
        """
        Check that all weights are within [weight_min, weight_max].

        Args:
            weights: (N,) array

        Returns:
            List of violations
        """
        violations = []

        # Check lower bound
        below_min = weights < self.weight_min
        if np.any(below_min):
            count = np.sum(below_min)
            violations.append(ConstraintViolation(
                "weight_violation",
                f"{count} weights below minimum {self.weight_min}"
            ))

        # Check upper bound
        above_max = weights > self.weight_max
        if np.any(above_max):
            count = np.sum(above_max)
            violations.append(ConstraintViolation(
                "weight_violation",
                f"{count} weights above maximum {self.weight_max}"
            ))

        return violations

    def is_valid(self, points: np.ndarray, weights: np.ndarray) -> bool:
        """
        Check if candidate passes all constraints.

        Args:
            points: (N, 3) array
            weights: (N,) array

        Returns:
            True if all constraints pass
        """
        violations = self.check_all(points, weights)
        return len(violations) == 0


def check_constraints(points: np.ndarray, weights: np.ndarray, params: Dict) -> List[ConstraintViolation]:
    """
    Convenience function to check all constraints.

    Args:
        points: (N, 3) array
        weights: (N,) array
        params: Parameter dictionary

    Returns:
        List of violations (empty if all pass)
    """
    checker = ConstraintChecker(params)
    return checker.check_all(points, weights)


if __name__ == "__main__":
    # Test constraint checker
    from generate_pair import DEFAULT_PARAMS, generate_random_genotype

    print("Testing ConstraintChecker...")

    # Generate a random genotype
    params = DEFAULT_PARAMS.copy()
    params['n_points'] = 10
    params['target_pairs'] = 5

    points, weights, gen_params = generate_random_genotype(params, target_pairs=5)

    print(f"\nGenerated candidate:")
    print(f"  Points: {len(points)}")
    print(f"  Weights range: [{weights.min():.1f}, {weights.max():.1f}]")
    print(f"  XY-pairs: {count_xy_pairs(points)}")

    # Check constraints
    checker = ConstraintChecker(params)
    violations = checker.check_all(points, weights)

    if violations:
        print(f"\n❌ Found {len(violations)} violations:")
        for v in violations:
            print(f"  - {v.constraint_type}: {v.description}")
    else:
        print("\n✅ All constraints passed!")

    # Test with intentionally violated constraints
    print("\n\nTesting with violations...")

    # Violate bounding box
    bad_points = points.copy()
    bad_points[5] = [1000, 1000, 1000]  # Way outside bounds

    # Violate weight range
    bad_weights = weights.copy()
    bad_weights[6] = 200  # Way above max

    violations = checker.check_all(bad_points, bad_weights)
    print(f"\n❌ Found {len(violations)} violations (expected 2):")
    for v in violations:
        print(f"  - {v.constraint_type}: {v.description}")
