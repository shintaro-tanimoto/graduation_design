#!/usr/bin/env python3
"""
test_xy_pairs.py - Test XY-pair detection and metrics computation

Tests the implementation of XY-pair clustering and metrics for the
evolutionary system.
"""

import sys
import os
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from generate_pair import detect_xy_clusters, count_xy_pairs, compute_pair_metrics


def test_detect_xy_clusters_basic():
    """Test basic XY cluster detection with known pairs."""
    print("\n" + "="*60)
    print("Test 1: Basic XY Cluster Detection")
    print("="*60)

    # Create test data: 2 pairs + 1 singleton
    points = np.array([
        [100.0, 200.0, 50.0],   # Point 0
        [100.0, 200.0, 150.0],  # Point 1 - Pair with 0
        [300.0, 400.0, 80.0],   # Point 2
        [300.0, 400.0, 220.0],  # Point 3 - Pair with 2
        [500.0, 600.0, 100.0]   # Point 4 - Singleton
    ])

    clusters = detect_xy_clusters(points, tolerance=1.0)

    print(f"Points:\n{points}")
    print(f"\nDetected clusters: {clusters}")
    print(f"Number of clusters: {len(clusters)}")

    # Verify
    assert len(clusters) == 2, f"Expected 2 clusters, got {len(clusters)}"
    assert [0, 1] in clusters or [1, 0] in clusters[:1], "Cluster [0,1] not found"
    assert [2, 3] in clusters or [3, 2] in clusters[-1:], "Cluster [2,3] not found"

    print("✓ Test passed: 2 pairs detected correctly")


def test_count_xy_pairs():
    """Test counting XY-pairs."""
    print("\n" + "="*60)
    print("Test 2: Count XY-Pairs")
    print("="*60)

    points = np.array([
        [100.0, 200.0, 50.0],
        [100.0, 200.0, 150.0],  # Pair 1
        [300.0, 400.0, 80.0],
        [300.0, 400.0, 220.0],  # Pair 2
        [500.0, 600.0, 100.0]   # Singleton
    ])

    pair_count = count_xy_pairs(points, tolerance=1.0)

    print(f"XY-pair count: {pair_count}")

    assert pair_count == 2, f"Expected 2 pairs, got {pair_count}"

    print("✓ Test passed: Pair count correct")


def test_compute_pair_metrics():
    """Test metric computation."""
    print("\n" + "="*60)
    print("Test 3: Compute Pair Metrics")
    print("="*60)

    points = np.array([
        [100.0, 200.0, 50.0],
        [100.0, 200.0, 150.0],  # Pair 1: dz = 100
        [300.0, 400.0, 80.0],
        [300.0, 400.0, 220.0],  # Pair 2: dz = 140
        [500.0, 600.0, 100.0]   # Singleton (ignored)
    ])

    metrics = compute_pair_metrics(points, tolerance=1.0)

    print(f"Metrics: {metrics}")

    # Expected values
    expected_mean_dz = (100.0 + 140.0) / 2  # 120.0

    assert metrics['xy_pair_count'] == 2
    assert abs(metrics['mean_pair_dz'] - expected_mean_dz) < 0.01
    assert abs(metrics['max_pair_dz'] - 140.0) < 0.01
    assert abs(metrics['min_pair_dz'] - 100.0) < 0.01

    print(f"✓ Test passed: mean_pair_dz = {metrics['mean_pair_dz']:.1f} (expected {expected_mean_dz:.1f})")


def test_no_pairs():
    """Test with no XY-pairs (all singletons)."""
    print("\n" + "="*60)
    print("Test 4: No XY-Pairs (All Singletons)")
    print("="*60)

    points = np.array([
        [100.0, 200.0, 50.0],
        [200.0, 300.0, 100.0],
        [300.0, 400.0, 150.0],
        [400.0, 500.0, 200.0]
    ])

    metrics = compute_pair_metrics(points, tolerance=1.0)

    print(f"Metrics: {metrics}")

    assert metrics['xy_pair_count'] == 0
    assert metrics['mean_pair_dz'] == 0.0
    assert metrics['max_pair_dz'] == 0.0
    assert metrics['min_pair_dz'] == 0.0

    print("✓ Test passed: No pairs detected, all metrics = 0")


def test_triplet_cluster():
    """Test with 3 points sharing same XY (triplet)."""
    print("\n" + "="*60)
    print("Test 5: Triplet Cluster (3 points at same XY)")
    print("="*60)

    points = np.array([
        [100.0, 200.0, 50.0],
        [100.0, 200.0, 150.0],
        [100.0, 200.0, 250.0],  # Triplet at (100, 200)
        [300.0, 400.0, 80.0],
        [300.0, 400.0, 180.0]   # Pair at (300, 400)
    ])

    clusters = detect_xy_clusters(points, tolerance=1.0)
    metrics = compute_pair_metrics(points, tolerance=1.0)

    print(f"Clusters: {clusters}")
    print(f"Metrics: {metrics}")

    # Triplet: dz = 250 - 50 = 200
    # Pair: dz = 180 - 80 = 100
    # Mean: (200 + 100) / 2 = 150

    assert metrics['xy_pair_count'] == 2
    assert abs(metrics['mean_pair_dz'] - 150.0) < 0.01
    assert abs(metrics['max_pair_dz'] - 200.0) < 0.01
    assert abs(metrics['min_pair_dz'] - 100.0) < 0.01

    print(f"✓ Test passed: Triplet handled correctly (dz = {metrics['max_pair_dz']:.1f})")


def test_tolerance():
    """Test tolerance parameter for near-XY-aligned points."""
    print("\n" + "="*60)
    print("Test 6: Tolerance Parameter")
    print("="*60)

    # Points slightly offset in XY (0.5mm apart)
    points = np.array([
        [100.0, 200.0, 50.0],
        [100.5, 200.0, 150.0],  # 0.5mm offset in X
    ])

    # Strict tolerance: should NOT be detected as pair
    clusters_strict = detect_xy_clusters(points, tolerance=0.1)
    print(f"Tolerance=0.1mm: {len(clusters_strict)} pairs detected")
    assert len(clusters_strict) == 0

    # Relaxed tolerance: should be detected as pair
    clusters_relaxed = detect_xy_clusters(points, tolerance=1.0)
    print(f"Tolerance=1.0mm: {len(clusters_relaxed)} pairs detected")
    assert len(clusters_relaxed) == 1

    print("✓ Test passed: Tolerance parameter works correctly")


def test_fixed_points():
    """Test with actual fixed points from the system."""
    print("\n" + "="*60)
    print("Test 7: Fixed Points (400, 350, ±200)")
    print("="*60)

    # The system has fixed points at (400, 350, 200) and (400, 350, -200)
    points = np.array([
        [400.0, 350.0, 200.0],   # Fixed point 1
        [400.0, 350.0, -200.0],  # Fixed point 2 (pair with 1)
        [100.0, 200.0, 50.0],
        [300.0, 400.0, 80.0]
    ])

    metrics = compute_pair_metrics(points, tolerance=1.0)

    print(f"Metrics: {metrics}")

    # Fixed points: dz = 200 - (-200) = 400
    assert metrics['xy_pair_count'] == 1
    assert abs(metrics['mean_pair_dz'] - 400.0) < 0.01

    print(f"✓ Test passed: Fixed points detected as pair (dz = {metrics['mean_pair_dz']:.1f}mm)")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("XY-Pair Detection and Metrics - Test Suite")
    print("="*60)

    try:
        test_detect_xy_clusters_basic()
        test_count_xy_pairs()
        test_compute_pair_metrics()
        test_no_pairs()
        test_triplet_cluster()
        test_tolerance()
        test_fixed_points()

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
    run_all_tests()
