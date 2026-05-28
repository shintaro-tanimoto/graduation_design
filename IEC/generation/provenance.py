"""
provenance.py - Provenance Tracking Utilities

Tracks the origin and transformation history of each candidate for
卒業設計 verifiability and analysis.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional


class ProvenanceTracker:
    """Tracks provenance information for a single candidate."""

    def __init__(self, cand_id: str, gen_id: int):
        """
        Initialize ProvenanceTracker.

        Args:
            cand_id: Candidate ID (e.g., "cand_00")
            gen_id: Generation number
        """
        self.cand_id = cand_id
        self.gen_id = gen_id
        self.timestamp = datetime.now().isoformat()
        self.origin_type = None
        self.parents = []
        self.operator_config = {}
        self.random_seed = None
        self.repair_log = []
        self.repair_iterations = 0
        self.generation_success = True
        self.regenerated = False
        self.original_seed = None

    def set_origin(self, origin_type: str, parents: Optional[List[str]] = None):
        """
        Set the origin type and parents.

        Args:
            origin_type: One of:
                - "mutate_weak"
                - "mutate_strong"
                - "crossover_winner_archive"
                - "crossover_archive_archive"
                - "random_baseline"
                - "random_extreme"
            parents: List of parent candidate paths (e.g., ["gen_000/cand_03"])
        """
        self.origin_type = origin_type
        self.parents = parents or []

    def set_operator_config(self, **kwargs):
        """
        Set operator configuration parameters.

        Args:
            **kwargs: Operator-specific parameters
                - mutation_mode: For mutate (e.g., "weak_z", "strong_pairs")
                - crossover_mode: For crossover (e.g., "xy_cluster_swap", "uniform")
                - xy_strategy: XY-pair handling (e.g., "PRESERVE_XY", "BREAK_XY")
                - target_pairs: Target XY-pair count
                - sigma_multiplier: Mutation strength multiplier
        """
        self.operator_config.update(kwargs)

    def set_seed(self, seed: int):
        """Set random seed for reproducibility."""
        self.random_seed = seed

    def add_repair_action(self, issue: str, action: str, success: bool):
        """
        Add a repair action to the log.

        Args:
            issue: Constraint issue (e.g., "bbox_violation", "n_points_mismatch")
            action: Repair action taken (e.g., "clipped_3_points", "added_2_points")
            success: Whether the repair was successful
        """
        self.repair_log.append({
            "issue": issue,
            "action": action,
            "success": success
        })
        self.repair_iterations = len(self.repair_log)

    def mark_regenerated(self, original_seed: int):
        """
        Mark candidate as regenerated due to repair failure.

        Args:
            original_seed: Original random seed that failed
        """
        self.regenerated = True
        self.original_seed = original_seed

    def mark_failed(self):
        """Mark generation as failed."""
        self.generation_success = False

    def to_dict(self) -> Dict:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Provenance dictionary
        """
        data = {
            "cand_id": self.cand_id,
            "gen_id": self.gen_id,
            "timestamp": self.timestamp,
            "origin_type": self.origin_type,
            "parents": self.parents,
            "operator_config": self.operator_config,
            "random_seed": self.random_seed,
            "repair_log": self.repair_log,
            "repair_iterations": self.repair_iterations,
            "generation_success": self.generation_success
        }

        if self.regenerated:
            data["regenerated"] = True
            data["original_seed"] = self.original_seed

        return data

    def save(self, filepath: str):
        """
        Save provenance to JSON file.

        Args:
            filepath: Path to provenance.json
        """
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> 'ProvenanceTracker':
        """
        Load provenance from JSON file.

        Args:
            filepath: Path to provenance.json

        Returns:
            ProvenanceTracker instance
        """
        with open(filepath, 'r') as f:
            data = json.load(f)

        tracker = cls(data["cand_id"], data["gen_id"])
        tracker.timestamp = data.get("timestamp", "")
        tracker.origin_type = data.get("origin_type")
        tracker.parents = data.get("parents", [])
        tracker.operator_config = data.get("operator_config", {})
        tracker.random_seed = data.get("random_seed")
        tracker.repair_log = data.get("repair_log", [])
        tracker.repair_iterations = data.get("repair_iterations", 0)
        tracker.generation_success = data.get("generation_success", True)
        tracker.regenerated = data.get("regenerated", False)
        tracker.original_seed = data.get("original_seed")

        return tracker


def create_mutation_provenance(cand_id: str, gen_id: int, parent_path: str,
                                mutation_type: str, xy_strategy: str,
                                sigma_multiplier: float, seed: int) -> ProvenanceTracker:
    """
    Create provenance for mutation-based candidate.

    Args:
        cand_id: Candidate ID
        gen_id: Generation number
        parent_path: Parent candidate path
        mutation_type: "weak" or "strong"
        xy_strategy: XY-pair handling strategy
        sigma_multiplier: Mutation strength multiplier
        seed: Random seed

    Returns:
        ProvenanceTracker instance
    """
    tracker = ProvenanceTracker(cand_id, gen_id)

    origin_type = f"mutate_{mutation_type}"
    tracker.set_origin(origin_type, parents=[parent_path])
    tracker.set_operator_config(
        mutation_mode=mutation_type,
        xy_strategy=xy_strategy,
        sigma_multiplier=sigma_multiplier
    )
    tracker.set_seed(seed)

    return tracker


def create_crossover_provenance(cand_id: str, gen_id: int,
                                  parent1_path: str, parent2_path: str,
                                  crossover_type: str, crossover_mode: str,
                                  preserve_xy: bool, seed: int) -> ProvenanceTracker:
    """
    Create provenance for crossover-based candidate.

    Args:
        cand_id: Candidate ID
        gen_id: Generation number
        parent1_path: First parent path
        parent2_path: Second parent path
        crossover_type: "winner_archive" or "archive_archive"
        crossover_mode: Crossover algorithm ("xy_cluster_swap", "uniform", etc.)
        preserve_xy: Whether XY-pairs are preserved
        seed: Random seed

    Returns:
        ProvenanceTracker instance
    """
    tracker = ProvenanceTracker(cand_id, gen_id)

    origin_type = f"crossover_{crossover_type}"
    tracker.set_origin(origin_type, parents=[parent1_path, parent2_path])
    tracker.set_operator_config(
        crossover_mode=crossover_mode,
        preserve_xy=preserve_xy
    )
    tracker.set_seed(seed)

    return tracker


def create_random_provenance(cand_id: str, gen_id: int,
                               random_type: str, target_pairs: int,
                               weight_range: Optional[tuple] = None,
                               seed: int = None) -> ProvenanceTracker:
    """
    Create provenance for random-generated candidate.

    Args:
        cand_id: Candidate ID
        gen_id: Generation number
        random_type: "baseline" or "extreme"
        target_pairs: Target XY-pair count
        weight_range: Optional (weight_min, weight_max) for extreme variants
        seed: Random seed

    Returns:
        ProvenanceTracker instance
    """
    tracker = ProvenanceTracker(cand_id, gen_id)

    origin_type = f"random_{random_type}"
    tracker.set_origin(origin_type, parents=[])

    config = {"target_pairs": target_pairs}
    if weight_range:
        config["weight_min"] = weight_range[0]
        config["weight_max"] = weight_range[1]

    tracker.set_operator_config(**config)
    if seed is not None:
        tracker.set_seed(seed)

    return tracker


if __name__ == "__main__":
    # Test provenance tracking
    print("Testing ProvenanceTracker...")

    # Test mutation provenance
    tracker = create_mutation_provenance(
        cand_id="cand_00",
        gen_id=1,
        parent_path="gen_000/cand_03",
        mutation_type="weak",
        xy_strategy="PRESERVE_XY",
        sigma_multiplier=0.5,
        seed=123456
    )

    # Simulate repair
    tracker.add_repair_action("bbox_violation", "clipped_3_points", True)
    tracker.add_repair_action("n_points_mismatch", "added_2_points", True)

    print("\nMutation Provenance:")
    print(json.dumps(tracker.to_dict(), indent=2))

    # Test crossover provenance
    tracker2 = create_crossover_provenance(
        cand_id="cand_02",
        gen_id=1,
        parent1_path="gen_000/cand_03",
        parent2_path="archive/meta_abc12345.json",
        crossover_type="winner_archive",
        crossover_mode="xy_cluster_swap",
        preserve_xy=True,
        seed=789012
    )

    print("\nCrossover Provenance:")
    print(json.dumps(tracker2.to_dict(), indent=2))

    # Test random provenance
    tracker3 = create_random_provenance(
        cand_id="cand_04",
        gen_id=0,
        random_type="baseline",
        target_pairs=20,
        seed=345678
    )

    print("\nRandom Provenance:")
    print(json.dumps(tracker3.to_dict(), indent=2))
