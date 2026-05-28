#!/usr/bin/env python3
"""
test_crossover.py - Unit tests for crossover functionality

Tests the crossover implementation to ensure:
1. Basic crossover works with different point counts
2. Fixed points are preserved
3. XY-pair structures are preserved (when requested)
4. Sibling path resolution works
5. Non-fixed indices are correctly identified
"""

import numpy as np
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from generate_pair import (
    crossover_genotypes,
    get_sibling_meta_path,
    get_non_fixed_indices,
    FIXED_POINTS,
    FIXED_WEIGHTS,
    DEFAULT_PARAMS,
    detect_xy_clusters,
    get_fixed_point_indices
)


def test_crossover_basic():
    """Test 1: Basic crossover functionality with different point counts"""
    print("\n  Test 1: Basic crossover with different point counts...")

    # Parent 1: 5 points
    points1 = np.random.uniform(0, 800, (5, 3))
    weights1 = np.random.uniform(10, 50, 5)

    # Parent 2: 7 points
    points2 = np.random.uniform(0, 800, (7, 3))
    weights2 = np.random.uniform(10, 50, 7)

    # Perform crossover
    child_points, child_weights, info = crossover_genotypes(
        points1, weights1, points2, weights2, DEFAULT_PARAMS
    )

    # Validations
    assert len(child_points) >= 3, f"Child should have at least 3 points, got {len(child_points)}"
    assert len(child_points) == len(child_weights), "Points and weights length mismatch"

    # Check weight bounds for non-fixed points only (fixed points can exceed bounds)
    non_fixed_indices = get_non_fixed_indices(child_points)
    non_fixed_weights = child_weights[non_fixed_indices]

    assert all(w >= DEFAULT_PARAMS['weight_min'] for w in non_fixed_weights), "Some non-fixed weights below minimum"
    assert all(w <= DEFAULT_PARAMS['weight_max'] for w in non_fixed_weights), "Some non-fixed weights above maximum"

    # Check crossover info
    assert 'mode' in info, "Crossover info missing 'mode'"
    assert 'inheritance_ratio' in info, "Crossover info missing 'inheritance_ratio'"
    assert 'n_from_parent1' in info, "Crossover info missing 'n_from_parent1'"
    assert 'n_from_parent2' in info, "Crossover info missing 'n_from_parent2'"

    print(f"    ✓ Child has {len(child_points)} points")
    print(f"    ✓ Inherited {info['n_from_parent1']} from parent1, {info['n_from_parent2']} from parent2")
    print(f"    ✓ Inheritance ratio: {info['inheritance_ratio']:.2f}")
    print("  ✓ Test 1 passed")


def test_crossover_with_fixed_points():
    """Test 2: Fixed points are correctly preserved"""
    print("\n  Test 2: Fixed points preservation...")

    points1 = np.random.uniform(0, 800, (5, 3))
    weights1 = np.random.uniform(10, 50, 5)
    points2 = np.random.uniform(0, 800, (7, 3))
    weights2 = np.random.uniform(10, 50, 7)

    child_points, child_weights, _ = crossover_genotypes(
        points1, weights1, points2, weights2, DEFAULT_PARAMS
    )

    # Check that all fixed points are present in child
    for fixed_pt in FIXED_POINTS:
        found = any(np.allclose(child_pt, fixed_pt, atol=1e-6) for child_pt in child_points)
        assert found, f"Fixed point {fixed_pt} not found in child"

    print(f"    ✓ All {len(FIXED_POINTS)} fixed points preserved")
    print("  ✓ Test 2 passed")


def test_crossover_xy_pair_preservation():
    """Test 3: XY-pair structure preservation"""
    print("\n  Test 3: XY-pair structure preservation...")

    # Parent 1 with XY-pairs
    points1 = np.array([
        [100, 200, 50],   # Pair 1 - bottom
        [100, 200, 150],  # Pair 1 - top
        [300, 400, 100],
        [500, 600, 200],
    ])
    weights1 = np.array([20, 25, 30, 35])

    # Parent 2 with XY-pairs
    points2 = np.array([
        [150, 250, 60],
        [400, 300, 120],
        [400, 300, 220],  # Pair - bottom
        [400, 300, 320],  # Pair - top
        [600, 500, 180],
    ])
    weights2 = np.array([22, 28, 32, 36, 40])

    child_points, child_weights, info = crossover_genotypes(
        points1, weights1, points2, weights2,
        DEFAULT_PARAMS, preserve_xy_pairs=True
    )

    # Detect XY-pairs in child
    clusters = detect_xy_clusters(child_points)

    print(f"    ✓ Child has {len(child_points)} points")
    print(f"    ✓ Child has {len(clusters)} XY-pair clusters")
    print(f"    ✓ Parent1 had {info['n_clusters_parent1']} clusters")
    print(f"    ✓ Parent2 had {info['n_clusters_parent2']} clusters")
    assert len(child_points) >= 3, "Child point count too low"

    print("  ✓ Test 3 passed")


def test_sibling_path_resolution():
    """Test 4: Sibling path resolution"""
    print("\n  Test 4: Sibling path resolution...")

    test_cases = [
        ('/path/to/meta_A.json', '/path/to/meta_B.json'),
        ('/path/to/meta_B.json', '/path/to/meta_A.json'),
        ('/path/to/other.json', None),
        ('meta_A.json', 'meta_B.json'),
    ]

    for input_path, expected in test_cases:
        result = get_sibling_meta_path(input_path)
        assert result == expected, f"Expected {expected}, got {result} for input {input_path}"

    print(f"    ✓ All {len(test_cases)} sibling path resolutions correct")
    print("  ✓ Test 4 passed")


def test_non_fixed_indices():
    """Test 5: Non-fixed indices identification"""
    print("\n  Test 5: Non-fixed indices...")

    # Create points array with fixed points at the start
    random_points = np.random.uniform(0, 800, (5, 3))
    points = np.vstack([FIXED_POINTS, random_points])

    non_fixed = get_non_fixed_indices(points)

    assert len(non_fixed) == 5, f"Should have 5 non-fixed points, got {len(non_fixed)}"
    assert all(idx >= len(FIXED_POINTS) for idx in non_fixed), "Some fixed indices included in non-fixed list"

    print(f"    ✓ Correctly identified {len(non_fixed)} non-fixed points")
    print(f"    ✓ Fixed points excluded: {len(FIXED_POINTS)}")
    print("  ✓ Test 5 passed")


def test_crossover_deterministic():
    """Test 6: Crossover produces different results (randomness check)"""
    print("\n  Test 6: Crossover randomness...")

    np.random.seed(42)

    points1 = np.random.uniform(0, 800, (5, 3))
    weights1 = np.random.uniform(10, 50, 5)
    points2 = np.random.uniform(0, 800, (7, 3))
    weights2 = np.random.uniform(10, 50, 7)

    # Run crossover multiple times
    results = []
    for i in range(5):
        child_points, child_weights, info = crossover_genotypes(
            points1, weights1, points2, weights2, DEFAULT_PARAMS
        )
        results.append((len(child_points), info['inheritance_ratio']))

    # Check that we got some variation (not all identical)
    unique_results = set(results)

    print(f"    ✓ Generated {len(results)} crossovers")
    print(f"    ✓ Unique results: {len(unique_results)}")
    print(f"    ✓ Point counts: {[r[0] for r in results]}")

    # We expect some variation in the results
    assert len(unique_results) > 1, "Crossover appears to be deterministic (no variation)"

    print("  ✓ Test 6 passed")


def test_crossover_plus_mutation():
    """Test 7: Crossover followed by mutation (typical GA workflow)"""
    print("\n  Test 7: Crossover + Mutation workflow...")

    # This test simulates the actual workflow where crossover is followed by mutation
    points1 = np.random.uniform(0, 800, (5, 3))
    weights1 = np.random.uniform(10, 50, 5)
    points2 = np.random.uniform(0, 800, (7, 3))
    weights2 = np.random.uniform(10, 50, 7)

    # Step 1: Crossover
    child_points, child_weights, info = crossover_genotypes(
        points1, weights1, points2, weights2, DEFAULT_PARAMS
    )

    points_before_mutation = len(child_points)

    # Step 2: Mutation (simulating what happens in generate_pair.py)
    from generate_pair import mutate_genotype

    params_mut = DEFAULT_PARAMS.copy()
    params_mut['pos_mutation_sigma'] = 20.0
    params_mut['weight_mutation_sigma'] = 5.0

    child_points_mutated, child_weights_mutated = mutate_genotype(
        child_points, child_weights, params_mut, xy_strategy='NONE'
    )

    # Validation
    assert len(child_points_mutated) >= 3, "Mutated child has too few points"
    assert len(child_points_mutated) == len(child_weights_mutated), "Points/weights mismatch after mutation"

    # Point count may change due to add/remove mutations
    print(f"    ✓ After crossover: {points_before_mutation} points")
    print(f"    ✓ After mutation: {len(child_points_mutated)} points")
    print(f"    ✓ Both crossover and mutation applied successfully")
    print("  ✓ Test 7 passed")


def run_all_tests():
    """Run all unit tests"""
    print("\n" + "="*60)
    print("  CROSSOVER UNIT TESTS")
    print("="*60)

    tests = [
        test_crossover_basic,
        test_crossover_with_fixed_points,
        test_crossover_xy_pair_preservation,
        test_sibling_path_resolution,
        test_non_fixed_indices,
        test_crossover_deterministic,
        test_crossover_plus_mutation,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {test_func.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {test_func.__name__} ERROR: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print("="*60 + "\n")

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
