#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_repair_xy_aware.py - Unit Tests for XY-Aware Repair Functions

Tests the new XY-pair preserving repair mechanism.
"""

import sys
import os
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../tools'))
from generate_pair import FIXED_POINTS, FIXED_WEIGHTS, detect_xy_clusters

sys.path.insert(0, os.path.dirname(__file__))

# Import directly from repair module (avoid relative imports)
import importlib.util
repair_spec = importlib.util.spec_from_file_location(
    "repair",
    os.path.join(os.path.dirname(__file__), "repair.py")
)
repair = importlib.util.module_from_spec(repair_spec)
repair_spec.loader.exec_module(repair)

classify_points_by_xy_structure = repair.classify_points_by_xy_structure
remove_points_xy_aware = repair.remove_points_xy_aware
adjust_n_points = repair.adjust_n_points
RepairLog = repair.RepairLog


def test_classify_points():
    """Test point classification into fixed/paired/singleton."""
    print("Testing classify_points_by_xy_structure()...")

    # Create test points with known structure
    points = np.array([
        [400.0, 350.0, 200.0],  # 0: Fixed
        [400.0, 350.0, -50.0],  # 1: Fixed
        [100.0, 100.0, 50.0],   # 2: Singleton
        [200.0, 200.0, 100.0],  # 3: Pair with 4
        [200.0, 200.0, 150.0],  # 4: Pair with 3
        [300.0, 300.0, 200.0],  # 5: Singleton
    ])

    fixed, paired, singletons = classify_points_by_xy_structure(points, tolerance=1.0)

    assert fixed == {0, 1}, f"Expected fixed {{0, 1}}, got {fixed}"
    assert 3 in paired and 4 in paired, f"Expected 3, 4 in paired, got {paired}"
    assert 2 in singletons and 5 in singletons, f"Expected [2, 5] in singletons, got {singletons}"

    print("✓ test_classify_points passed")


def test_remove_singletons_first():
    """Test that singletons are removed before pairs."""
    print("Testing remove_points_xy_aware() - singleton priority...")

    points = np.array([
        [400.0, 350.0, 200.0],  # 0: Fixed
        [400.0, 350.0, -50.0],  # 1: Fixed
        [100.0, 100.0, 50.0],   # 2: Singleton
        [200.0, 200.0, 100.0],  # 3: Pair
        [200.0, 200.0, 150.0],  # 4: Pair
        [300.0, 300.0, 200.0],  # 5: Singleton
    ])
    weights = np.array([100.0, 100.0, 30.0, 40.0, 45.0, 35.0])

    # Remove 2 points - should remove both singletons (2, 5)
    new_points, new_weights, stats = remove_points_xy_aware(points, weights, 2, tolerance=1.0)

    assert len(new_points) == 4, f"Expected 4 points, got {len(new_points)}"
    assert stats['singletons'] == 2, f"Expected 2 singletons removed, got {stats['singletons']}"
    assert stats['complete_pairs'] == 0, f"Expected 0 pairs removed, got {stats['complete_pairs']}"

    # Check that pair is preserved
    assert np.allclose(new_points[2, :2], new_points[3, :2], atol=1.0), "Pair should be preserved"

    print("✓ test_remove_singletons_first passed")


def test_remove_complete_pairs():
    """Test that complete pairs are removed when no singletons."""
    print("Testing remove_points_xy_aware() - complete pair removal...")

    points = np.array([
        [400.0, 350.0, 200.0],  # 0: Fixed
        [400.0, 350.0, -50.0],  # 1: Fixed
        [200.0, 200.0, 100.0],  # 2: Pair A
        [200.0, 200.0, 150.0],  # 3: Pair A
        [300.0, 300.0, 100.0],  # 4: Pair B
        [300.0, 300.0, 150.0],  # 5: Pair B
    ])
    weights = np.array([100.0, 100.0, 30.0, 40.0, 35.0, 45.0])

    # Remove 2 points - should remove 1 complete pair
    new_points, new_weights, stats = remove_points_xy_aware(points, weights, 2, tolerance=1.0)

    assert len(new_points) == 4, f"Expected 4 points, got {len(new_points)}"
    assert stats['singletons'] == 0, f"Expected 0 singletons removed, got {stats['singletons']}"
    assert stats['complete_pairs'] == 1, f"Expected 1 pair removed, got {stats['complete_pairs']}"

    print("✓ test_remove_complete_pairs passed")


def test_adjust_n_points_xy_aware():
    """Test adjust_n_points with XY-aware removal."""
    print("Testing adjust_n_points() with XY-aware removal...")

    params = {
        'n_points': 4,  # Target: 4 + 2 fixed = 6 total
        'bounds_min': [0, 0, -100],
        'bounds_max': [800, 700, 400],
        'weight_min': 10.0,
        'weight_max': 200.0,
        'exclusion_zone': None
    }

    # Start with 8 points (2 fixed + 4 singletons + 1 pair)
    points = np.array([
        [400.0, 350.0, 200.0],  # 0: Fixed
        [400.0, 350.0, -50.0],  # 1: Fixed
        [100.0, 100.0, 50.0],   # 2: Singleton
        [150.0, 150.0, 60.0],   # 3: Singleton
        [200.0, 200.0, 100.0],  # 4: Pair
        [200.0, 200.0, 150.0],  # 5: Pair
        [250.0, 250.0, 70.0],   # 6: Singleton
        [300.0, 300.0, 80.0],   # 7: Singleton
    ])
    weights = np.ones(8) * 30.0

    # Need to remove 2 points to reach target of 6
    new_points, new_weights, log = adjust_n_points(points, weights, 6, params)

    assert len(new_points) == 6, f"Expected 6 points, got {len(new_points)}"

    # Check that pair is still present
    clusters = detect_xy_clusters(new_points, tolerance=1.0)
    # Should have at least 1 cluster (the pair or fixed points)
    assert len(clusters) >= 1, f"Expected at least 1 XY-cluster, got {len(clusters)}"

    print("✓ test_adjust_n_points_xy_aware passed")


if __name__ == "__main__":
    print("Running XY-Aware Repair Tests...\n")

    try:
        test_classify_points()
        test_remove_singletons_first()
        test_remove_complete_pairs()
        test_adjust_n_points_xy_aware()

        print("\n✅ All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
