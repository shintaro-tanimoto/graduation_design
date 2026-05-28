# -*- coding: utf-8 -*-
"""
Archive Manager for 6-Candidate Generation System
Manages archive metadata including win counts, comparison tracking, and diversity scores
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import numpy as np


class ArchiveManager:
    """
    Manages archive candidates with extended metadata tracking.

    Extended metadata includes:
    - win_count: Number of times this candidate won tournaments
    - comparison_count: Number of times this candidate appeared in comparisons
    - quality_score: win_count / comparison_count (0 if never compared)
    - diversity_score: Average L2 distance to other archive candidates
    - last_win_gen: Generation ID where this candidate last won
    - first_archived: Timestamp when first added to archive
    - last_compared: Timestamp of last comparison appearance
    """

    def __init__(self, archive_dir: str = '../archive'):
        """
        Initialize Archive Manager.

        Args:
            archive_dir: Path to archive directory (relative or absolute)
        """
        self.archive_dir = Path(archive_dir)
        if not self.archive_dir.exists():
            raise ValueError(f"Archive directory does not exist: {archive_dir}")

    def _get_archive_files(self) -> List[Path]:
        """Get list of all meta_*.json files in archive."""
        return sorted(self.archive_dir.glob('meta_*.json'))

    def _extract_hash_from_path(self, path: Path) -> str:
        """Extract hash from meta_HASH.json filename."""
        return path.stem.replace('meta_', '')

    def load_archive_metadata(self, hash_id: str) -> Dict:
        """
        Load archive metadata with migration for old format.

        Args:
            hash_id: Hash identifier (without 'meta_' prefix or '.json' suffix)

        Returns:
            Complete metadata dict with archive_metadata populated

        Raises:
            FileNotFoundError: If archive file doesn't exist
        """
        meta_path = self.archive_dir / f'meta_{hash_id}.json'

        if not meta_path.exists():
            raise FileNotFoundError(f"Archive file not found: {meta_path}")

        with open(meta_path, 'r') as f:
            data = json.load(f)

        # Migrate old format if needed
        if 'metadata' not in data:
            data['metadata'] = {}

        if 'archive_metadata' not in data['metadata']:
            # Initialize with default values
            data['metadata']['archive_metadata'] = {
                'win_count': 0,
                'comparison_count': 0,
                'quality_score': 0.0,
                'diversity_score': None,
                'last_win_gen': None,
                'first_archived': data['metadata'].get('timestamp', datetime.now().isoformat()),
                'last_compared': None
            }

        return data

    def _save_archive_metadata(self, hash_id: str, data: Dict):
        """Save archive metadata back to file."""
        meta_path = self.archive_dir / f'meta_{hash_id}.json'

        with open(meta_path, 'w') as f:
            json.dump(data, f, indent=2)

    def update_winner(self, winner_hash: str, gen_id: int):
        """
        Update archive metadata for tournament winner.

        Args:
            winner_hash: Hash of winning candidate
            gen_id: Generation ID where candidate won
        """
        try:
            data = self.load_archive_metadata(winner_hash)
        except FileNotFoundError:
            print(f"  ⚠ Winner {winner_hash} not in archive, skipping win update")
            return

        archive_meta = data['metadata']['archive_metadata']

        # Increment win count
        archive_meta['win_count'] = archive_meta.get('win_count', 0) + 1
        archive_meta['last_win_gen'] = gen_id

        # Recalculate quality score
        comp_count = archive_meta.get('comparison_count', 0)
        if comp_count > 0:
            archive_meta['quality_score'] = archive_meta['win_count'] / comp_count
        else:
            archive_meta['quality_score'] = 0.0

        self._save_archive_metadata(winner_hash, data)

    def record_comparison(self, candidate_hash: str):
        """
        Record that a candidate appeared in a comparison.

        Args:
            candidate_hash: Hash of candidate that was compared
        """
        try:
            data = self.load_archive_metadata(candidate_hash)
        except FileNotFoundError:
            print(f"  ⚠ Candidate {candidate_hash} not in archive, skipping comparison record")
            return

        archive_meta = data['metadata']['archive_metadata']

        # Increment comparison count
        archive_meta['comparison_count'] = archive_meta.get('comparison_count', 0) + 1
        archive_meta['last_compared'] = datetime.now().isoformat()

        # Recalculate quality score
        win_count = archive_meta.get('win_count', 0)
        archive_meta['quality_score'] = win_count / archive_meta['comparison_count']

        self._save_archive_metadata(candidate_hash, data)

    def compute_diversity_scores(self):
        """
        Compute diversity scores for all archive candidates.

        Diversity score = average L2 distance of meta-features to all other candidates.
        Uses extract_features_from_genotype for consistent feature extraction.
        """
        from tools.extract_features import extract_features_from_genotype

        archive_files = self._get_archive_files()

        if len(archive_files) < 2:
            print(f"  ℹ Only {len(archive_files)} candidates in archive, skipping diversity computation")
            return

        # Extract features for all candidates
        features_list = []
        hashes = []

        for archive_file in archive_files:
            hash_id = self._extract_hash_from_path(archive_file)
            data = self.load_archive_metadata(hash_id)

            # Extract points and weights
            points_data = data.get('points', [])
            points = np.array([[p['position'][0], p['position'][1], p['position'][2]]
                              for p in points_data])
            weights = np.array([p['weight'] for p in points_data])

            # Extract meta-features (without volume to avoid computation cost)
            features = extract_features_from_genotype(points, weights, include_volume=False)
            features_list.append(features)
            hashes.append(hash_id)

        features_matrix = np.array(features_list)

        # Compute pairwise L2 distances and average
        for i, hash_id in enumerate(hashes):
            distances = []
            for j in range(len(features_list)):
                if i != j:
                    dist = np.linalg.norm(features_matrix[i] - features_matrix[j])
                    distances.append(dist)

            avg_distance = np.mean(distances) if distances else 0.0

            # Update diversity score
            data = self.load_archive_metadata(hash_id)
            data['metadata']['archive_metadata']['diversity_score'] = float(avg_distance)
            self._save_archive_metadata(hash_id, data)

    def select_by_quality(self, n: int = 1) -> List[Tuple[np.ndarray, np.ndarray, str]]:
        """
        Select n candidates by quality score (highest first).

        Args:
            n: Number of candidates to select

        Returns:
            List of tuples: [(points, weights, archive_path), ...]

        Raises:
            ValueError: If archive has fewer than n candidates
        """
        archive_files = self._get_archive_files()

        if len(archive_files) < n:
            raise ValueError(f"Archive has only {len(archive_files)} candidates, need {n}")

        # Load all with quality scores
        candidates = []
        for archive_file in archive_files:
            hash_id = self._extract_hash_from_path(archive_file)
            data = self.load_archive_metadata(hash_id)

            quality_score = data['metadata'].get('archive_metadata', {}).get('quality_score', 0.0)
            candidates.append((hash_id, quality_score, data))

        # Sort by quality score (descending)
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Select top n
        selected = []
        for i in range(n):
            hash_id, _, data = candidates[i]

            # Extract points and weights
            points_data = data.get('points', [])
            points = np.array([[p['position'][0], p['position'][1], p['position'][2]]
                              for p in points_data])
            weights = np.array([p['weight'] for p in points_data])

            archive_path = f"archive/meta_{hash_id}.json"
            selected.append((points, weights, archive_path))

        return selected

    def select_by_diversity(self, reference_points: np.ndarray, reference_weights: np.ndarray,
                           n: int = 1) -> List[Tuple[np.ndarray, np.ndarray, str]]:
        """
        Select n candidates most diverse from reference candidate.

        Args:
            reference_points: Reference candidate's points (N, 3)
            reference_weights: Reference candidate's weights (N,)
            n: Number of candidates to select

        Returns:
            List of tuples: [(points, weights, archive_path), ...]

        Raises:
            ValueError: If archive has fewer than n candidates
        """
        from tools.extract_features import extract_features_from_genotype

        archive_files = self._get_archive_files()

        if len(archive_files) < n:
            raise ValueError(f"Archive has only {len(archive_files)} candidates, need {n}")

        # Extract reference features
        ref_features = extract_features_from_genotype(reference_points, reference_weights,
                                                     include_volume=False)

        # Compute distances to all archive candidates
        candidates = []
        for archive_file in archive_files:
            hash_id = self._extract_hash_from_path(archive_file)
            data = self.load_archive_metadata(hash_id)

            # Extract points and weights
            points_data = data.get('points', [])
            points = np.array([[p['position'][0], p['position'][1], p['position'][2]]
                              for p in points_data])
            weights = np.array([p['weight'] for p in points_data])

            # Compute distance
            features = extract_features_from_genotype(points, weights, include_volume=False)
            distance = np.linalg.norm(ref_features - features)

            candidates.append((hash_id, distance, points, weights))

        # Sort by distance (descending - most diverse first)
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Select top n
        selected = []
        for i in range(n):
            hash_id, _, points, weights = candidates[i]
            archive_path = f"archive/meta_{hash_id}.json"
            selected.append((points, weights, archive_path))

        return selected

    def archive_candidate(self, meta_path: str, gen_id: int):
        """
        Add candidate to archive with initialized metadata.

        Args:
            meta_path: Path to candidate's meta.json file
            gen_id: Generation ID

        Note:
            This copies the candidate to archive and initializes archive_metadata.
            If candidate already exists (by hash), it's skipped.
        """
        from tools.generate_pair import compute_genotype_hash

        # Load source metadata
        with open(meta_path, 'r') as f:
            data = json.load(f)

        # Extract points and weights for hash computation
        points_data = data.get('points', [])
        points = np.array([[p['position'][0], p['position'][1], p['position'][2]]
                          for p in points_data])
        weights = np.array([p['weight'] for p in points_data])

        # Compute hash
        genotype_hash = compute_genotype_hash(points, weights)

        # Check if already in archive
        dest_path = self.archive_dir / f'meta_{genotype_hash}.json'
        if dest_path.exists():
            # Already archived, just ensure metadata exists
            try:
                self.load_archive_metadata(genotype_hash)  # Will migrate if needed
            except Exception:
                pass
            return genotype_hash

        # Initialize archive_metadata
        if 'metadata' not in data:
            data['metadata'] = {}

        data['metadata']['archive_metadata'] = {
            'win_count': 0,
            'comparison_count': 0,
            'quality_score': 0.0,
            'diversity_score': None,
            'last_win_gen': None,
            'first_archived': datetime.now().isoformat(),
            'last_compared': None
        }

        # Save to archive
        with open(dest_path, 'w') as f:
            json.dump(data, f, indent=2)

        return genotype_hash


# Unit test (run with: python generation/archive_manager.py)
if __name__ == "__main__":
    print("Archive Manager Unit Test")
    print("=" * 60)

    # Test initialization
    try:
        mgr = ArchiveManager('../archive')
        print("✓ ArchiveManager initialized")
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        exit(1)

    # Test loading existing archive
    archive_files = mgr._get_archive_files()
    if archive_files:
        test_hash = mgr._extract_hash_from_path(archive_files[0])
        print(f"  Testing with archive file: meta_{test_hash}.json")

        try:
            data = mgr.load_archive_metadata(test_hash)
            archive_meta = data.get('metadata', {}).get('archive_metadata', {})
            print(f"✓ Loaded metadata: {archive_meta}")
        except Exception as e:
            print(f"✗ Load failed: {e}")
    else:
        print("  ⚠ No archive files found for testing")

    # Test diversity score computation
    if len(archive_files) >= 2:
        print("\n  Computing diversity scores...")
        try:
            mgr.compute_diversity_scores()

            # Verify scores were computed
            data = mgr.load_archive_metadata(test_hash)
            div_score = data['metadata']['archive_metadata'].get('diversity_score')
            print(f"✓ Diversity score computed: {div_score}")
        except Exception as e:
            print(f"✗ Diversity computation failed: {e}")

    # Test selection by quality
    if archive_files:
        print("\n  Testing quality-based selection...")
        try:
            selected = mgr.select_by_quality(n=min(2, len(archive_files)))
            print(f"✓ Selected {len(selected)} candidates by quality")
            for points, weights, path in selected:
                print(f"    - {path}: {len(points)} points")
        except Exception as e:
            print(f"✗ Quality selection failed: {e}")

    print("\n" + "=" * 60)
    print("Archive Manager tests complete!")
