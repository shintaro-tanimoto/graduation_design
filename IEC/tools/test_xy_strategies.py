#!/usr/bin/env python3
"""
test_xy_strategies.py - Test XY-structure mutation strategies

Tests that PRESERVE_XY, BREAK_XY, and INCREASE_XY strategies work correctly.
"""

import sys
import os
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from generate_pair import (
    mutate_xy_structure,
    detect_xy_clusters,
    compute_pair_metrics,
    DEFAULT_PARAMS
)


def test_preserve_xy():
    """Test PRESERVE_XY: XY coords should remain identical, Z should change."""
    print("\n" + "="*60)
    print("Test 1: PRESERVE_XY Strategy")
    print("="*60)

    # Create points with 2 pairs
    points = np.array([
        [100.0, 200.0, 50.0],   # Pair 1
        [100.0, 200.0, 150.0],  # Pair 1
        [300.0, 400.0, 80.0],   # Pair 2
        [300.0, 400.0, 220.0],  # Pair 2
        [500.0, 600.0, 100.0]   # Singleton
    ])
    weights = np.array([30.0, 40.0, 25.0, 35.0, 20.0])

    print(f"Original pairs: {detect_xy_clusters(points, tolerance=1.0)}")
    print(f"Original metrics: {compute_pair_metrics(points, tolerance=1.0)}")

    # Apply PRESERVE_XY
    points_mutated, weights_mutated = mutate_xy_structure(
        points, weights, strategy='PRESERVE_XY', params=DEFAULT_PARAMS
    )

    print(f"\nMutated pairs: {detect_xy_clusters(points_mutated, tolerance=1.0)}")
    print(f"Mutated metrics: {compute_pair_metrics(points_mutated, tolerance=1.0)}")

    # Verify XY coords are preserved
    for i in [0, 1]:  # Pair 1
        assert np.allclose(points_mutated[i, :2], [100.0, 200.0], atol=0.1), \
            f"Point {i} XY changed!"
    for i in [2, 3]:  # Pair 2
        assert np.allclose(points_mutated[i, :2], [300.0, 400.0], atol=0.1), \
            f"Point {i} XY changed!"

    # Verify pairs still exist
    clusters = detect_xy_clusters(points_mutated, tolerance=1.0)
    assert len(clusters) == 2, f"Expected 2 pairs, got {len(clusters)}"

    print("✓ Test passed: XY coords preserved, pairs intact")


def test_break_xy():
    """Test BREAK_XY: Some pairs should be broken."""
    print("\n" + "="*60)
    print("Test 2: BREAK_XY Strategy (probabilistic)")
    print("="*60)

    # Create points with 5 pairs
    points = np.array([
        [100.0, 200.0, 50.0],
        [100.0, 200.0, 150.0],
        [200.0, 300.0, 60.0],
        [200.0, 300.0, 160.0],
        [300.0, 400.0, 70.0],
        [300.0, 400.0, 170.0],
        [400.0, 500.0, 80.0],
        [400.0, 500.0, 180.0],
        [500.0, 600.0, 90.0],
        [500.0, 600.0, 190.0],
    ])
    weights = np.ones(10) * 30.0

    initial_pair_count = len(detect_xy_clusters(points, tolerance=1.0))
    print(f"Initial pairs: {initial_pair_count}")

    # Try multiple times (probabilistic, 30% chance per pair)
    broke_at_least_once = False
    for trial in range(10):
        points_mutated, weights_mutated = mutate_xy_structure(
            points.copy(), weights.copy(), strategy='BREAK_XY', params=DEFAULT_PARAMS
        )

        final_pair_count = len(detect_xy_clusters(points_mutated, tolerance=1.0))

        if final_pair_count < initial_pair_count:
            broke_at_least_once = True
            print(f"  Trial {trial+1}: {initial_pair_count} → {final_pair_count} pairs (broke {initial_pair_count - final_pair_count})")
            break

    assert broke_at_least_once, "BREAK_XY never broke a pair in 10 trials"
    print("✓ Test passed: At least one pair was broken")


def test_increase_xy():
    """Test INCREASE_XY: New pairs should be created."""
    print("\n" + "="*60)
    print("Test 3: INCREASE_XY Strategy")
    print("="*60)

    # Create points with 1 pair and 4 singletons
    points = np.array([
        [100.0, 200.0, 50.0],   # Pair
        [100.0, 200.0, 150.0],  # Pair
        [200.0, 300.0, 60.0],   # Singleton 1
        [300.0, 400.0, 70.0],   # Singleton 2
        [400.0, 500.0, 80.0],   # Singleton 3
        [500.0, 600.0, 90.0],   # Singleton 4
    ])
    weights = np.ones(6) * 30.0

    initial_pair_count = len(detect_xy_clusters(points, tolerance=1.0))
    print(f"Initial pairs: {initial_pair_count}")

    # Apply INCREASE_XY
    points_mutated, weights_mutated = mutate_xy_structure(
        points, weights, strategy='INCREASE_XY', params=DEFAULT_PARAMS
    )

    final_pair_count = len(detect_xy_clusters(points_mutated, tolerance=1.0))
    print(f"Final pairs: {final_pair_count}")

    # At least one new pair should be created
    assert final_pair_count > initial_pair_count, \
        f"Expected more pairs, got {final_pair_count} (was {initial_pair_count})"

    print(f"✓ Test passed: New pair created ({initial_pair_count} → {final_pair_count})")


def test_none_strategy():
    """Test NONE: No XY-specific mutation."""
    print("\n" + "="*60)
    print("Test 4: NONE Strategy (pass-through)")
    print("="*60)

    points = np.array([
        [100.0, 200.0, 50.0],
        [100.0, 200.0, 150.0],
        [300.0, 400.0, 80.0],
    ])
    weights = np.array([30.0, 40.0, 25.0])

    # Apply NONE
    points_mutated, weights_mutated = mutate_xy_structure(
        points, weights, strategy='NONE', params=DEFAULT_PARAMS
    )

    # Should be identical (copy)
    assert np.allclose(points_mutated, points), "NONE strategy modified points!"
    assert np.allclose(weights_mutated, weights), "NONE strategy modified weights!"

    print("✓ Test passed: NONE strategy is pass-through")


def run_all_tests():
    """Run all XY-strategy tests."""
    print("\n" + "="*60)
    print("XY-Structure Mutation Strategies - Test Suite")
    print("="*60)

    try:
        test_preserve_xy()
        test_break_xy()
        test_increase_xy()
        test_none_strategy()

        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED")
        print("="*60)

    except AssertionError as e:
        print("\n" + "="*60)
        print("✗ TEST FAILED")
        print("="*60)
        print(f"Error: {e}")
        raise


if __name__ == '__main__':
    # Set random seed for reproducibility
    np.random.seed(42)
    run_all_tests()
