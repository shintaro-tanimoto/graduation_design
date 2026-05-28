#!/usr/bin/env python3
"""
test_p0_integration.py - Integration test for P0 features

Tests the complete workflow of XY-pair generation and evolution.
"""

import sys
import os
import subprocess
import json
import shutil

# Test directory
TEST_DIR = "/tmp/iec_test_p0"


def setup_test_environment():
    """Create clean test directory."""
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)
    print(f"Created test directory: {TEST_DIR}")


def run_command(cmd):
    """Run command and return output."""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd="/home/shint/py_code/IEC"
    )
    return result.returncode, result.stdout, result.stderr


def load_metadata(filepath):
    """Load metadata from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data['metadata']


def test_initial_generation_with_pairs():
    """Test P0.0: Initial generation with target pairs."""
    print("\n" + "="*60)
    print("P0.0: Initial Generation with --target-pairs")
    print("="*60)

    # Generate with 5 target pairs
    cmd = f"python tools/generate_pair.py --init --target-pairs 5 --output {TEST_DIR}/gen"
    returncode, stdout, stderr = run_command(cmd)

    assert returncode == 0, f"Command failed: {stderr}"
    print(stdout)

    # Check metadata
    meta_A = load_metadata(f"{TEST_DIR}/gen/meta_A.json")
    meta_B = load_metadata(f"{TEST_DIR}/gen/meta_B.json")

    # Should have 6 pairs total (1 fixed + 5 generated)
    assert meta_A['metrics']['xy_pair_count'] == 6, \
        f"Expected 6 pairs in A, got {meta_A['metrics']['xy_pair_count']}"
    assert meta_B['metrics']['xy_pair_count'] == 6, \
        f"Expected 6 pairs in B, got {meta_B['metrics']['xy_pair_count']}"

    print(f"✓ A: {meta_A['n_points']} points, {meta_A['metrics']['xy_pair_count']} pairs")
    print(f"✓ B: {meta_B['n_points']} points, {meta_B['metrics']['xy_pair_count']} pairs")
    print(f"✓ Mean dz A: {meta_A['metrics']['mean_pair_dz']:.1f}mm")
    print(f"✓ Mean dz B: {meta_B['metrics']['mean_pair_dz']:.1f}mm")


def test_xy_aware_mutation():
    """Test P0.2: XY-aware mutation operators."""
    print("\n" + "="*60)
    print("P0.2: XY-Aware Mutation (from parent with pairs)")
    print("="*60)

    # Generate child from parent
    cmd = f"python tools/generate_pair.py --parent {TEST_DIR}/gen/meta_A.json --output {TEST_DIR}/gen2"
    returncode, stdout, stderr = run_command(cmd)

    assert returncode == 0, f"Command failed: {stderr}"
    print(stdout)

    # Check that XY strategy was applied
    assert "XY strategy A:" in stdout, "XY strategy A not shown"
    assert "XY strategy B:" in stdout, "XY strategy B not shown"

    # Check metadata
    meta_A = load_metadata(f"{TEST_DIR}/gen2/meta_A.json")
    meta_B = load_metadata(f"{TEST_DIR}/gen2/meta_B.json")

    print(f"✓ Child A: {meta_A['n_points']} points, {meta_A['metrics']['xy_pair_count']} pairs")
    print(f"✓ Child B: {meta_B['n_points']} points, {meta_B['metrics']['xy_pair_count']} pairs")
    print(f"✓ Mean dz A: {meta_A['metrics']['mean_pair_dz']:.1f}mm")
    print(f"✓ Mean dz B: {meta_B['metrics']['mean_pair_dz']:.1f}mm")


def test_metrics_persistence():
    """Test P1: Metrics are persisted in all generations."""
    print("\n" + "="*60)
    print("P1: Metrics Persistence Across Generations")
    print("="*60)

    # Run 3 generations
    parent_path = f"{TEST_DIR}/gen/meta_A.json"
    for i in range(3):
        output_dir = f"{TEST_DIR}/gen_iter{i+1}"
        cmd = f"python tools/generate_pair.py --parent {parent_path} --output {output_dir}"
        returncode, stdout, stderr = run_command(cmd)

        assert returncode == 0, f"Generation {i+1} failed: {stderr}"

        # Check metadata
        meta_A = load_metadata(f"{output_dir}/meta_A.json")
        meta_B = load_metadata(f"{output_dir}/meta_B.json")

        # Metrics should always be present
        assert 'metrics' in meta_A, f"Iteration {i+1} A missing metrics"
        assert 'metrics' in meta_B, f"Iteration {i+1} B missing metrics"
        assert 'xy_pair_count' in meta_A['metrics'], f"Iteration {i+1} A missing xy_pair_count"
        assert 'mean_pair_dz' in meta_A['metrics'], f"Iteration {i+1} A missing mean_pair_dz"

        print(f"  Iteration {i+1}: A={meta_A['metrics']['xy_pair_count']} pairs, B={meta_B['metrics']['xy_pair_count']} pairs")

        # Use A as parent for next iteration
        parent_path = f"{output_dir}/meta_A.json"

    print("✓ Metrics persisted across 3 generations")


def run_all_tests():
    """Run all P0 integration tests."""
    print("\n" + "="*60)
    print("P0 Integration Tests - Full Workflow")
    print("="*60)

    try:
        setup_test_environment()
        test_initial_generation_with_pairs()
        test_xy_aware_mutation()
        test_metrics_persistence()

        print("\n" + "="*60)
        print("✓ ALL P0 INTEGRATION TESTS PASSED")
        print("="*60)
        print(f"\nTest artifacts saved in: {TEST_DIR}")

    except AssertionError as e:
        print("\n" + "="*60)
        print("✗ TEST FAILED")
        print("="*60)
        print(f"Error: {e}")
        raise


if __name__ == '__main__':
    run_all_tests()
