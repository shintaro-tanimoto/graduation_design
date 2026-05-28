"""
generation_manager.py - Generation Directory Structure Management

Manages the gen_history/ directory structure for 6-candidate generation system.
Each generation has its own directory with population, pairs, and summary.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional


class GenerationManager:
    """Manages generation directory structure and metadata."""

    def __init__(self, base_dir: str = "../gen_history"):
        """
        Initialize GenerationManager.

        Args:
            base_dir: Base directory for generation history (default: ../gen_history)
        """
        self.base_dir = os.path.abspath(base_dir)
        self.ensure_base_dir()

    def ensure_base_dir(self):
        """Create base directory if it doesn't exist."""
        os.makedirs(self.base_dir, exist_ok=True)

    def get_generation_dir(self, gen_id: int) -> str:
        """
        Get path to generation directory.

        Args:
            gen_id: Generation number (0, 1, 2, ...)

        Returns:
            Absolute path to gen_XXX/ directory
        """
        return os.path.join(self.base_dir, f"gen_{gen_id:03d}")

    def get_population_dir(self, gen_id: int) -> str:
        """Get path to population directory for a generation."""
        return os.path.join(self.get_generation_dir(gen_id), "population")

    def get_candidate_dir(self, gen_id: int, cand_id: int) -> str:
        """
        Get path to candidate directory.

        Args:
            gen_id: Generation number
            cand_id: Candidate number (0-5)

        Returns:
            Absolute path to gen_XXX/population/cand_XX/ directory
        """
        return os.path.join(self.get_population_dir(gen_id), f"cand_{cand_id:02d}")

    def create_generation_structure(self, gen_id: int) -> Dict[str, str]:
        """
        Create complete directory structure for a generation.

        Args:
            gen_id: Generation number

        Returns:
            Dictionary mapping component names to paths
        """
        gen_dir = self.get_generation_dir(gen_id)
        pop_dir = self.get_population_dir(gen_id)

        # Create main directories
        os.makedirs(gen_dir, exist_ok=True)
        os.makedirs(pop_dir, exist_ok=True)

        # Create 6 candidate directories
        cand_dirs = {}
        for cand_id in range(6):
            cand_dir = self.get_candidate_dir(gen_id, cand_id)
            os.makedirs(cand_dir, exist_ok=True)
            cand_dirs[f"cand_{cand_id:02d}"] = cand_dir

        return {
            "gen_dir": gen_dir,
            "population_dir": pop_dir,
            **cand_dirs
        }

    def get_candidate_files(self, gen_id: int, cand_id: int) -> Dict[str, str]:
        """
        Get paths to all files for a candidate.

        Args:
            gen_id: Generation number
            cand_id: Candidate number (0-5)

        Returns:
            Dictionary mapping file types to paths
        """
        cand_dir = self.get_candidate_dir(gen_id, cand_id)

        return {
            "dir": cand_dir,
            "meta": os.path.join(cand_dir, "meta.json"),
            "provenance": os.path.join(cand_dir, "provenance.json"),
            "mesh": os.path.join(cand_dir, "mesh.obj"),
            "mesh_inner": os.path.join(cand_dir, "mesh_inner.obj"),
            "xy_lines": os.path.join(cand_dir, "xy_lines.obj")
        }

    def save_generation_summary(self, gen_id: int, summary: Dict):
        """
        Save generation summary to gen_summary.json.

        Args:
            gen_id: Generation number
            summary: Summary dictionary
        """
        gen_dir = self.get_generation_dir(gen_id)
        summary_path = os.path.join(gen_dir, "gen_summary.json")

        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

    def load_generation_summary(self, gen_id: int) -> Optional[Dict]:
        """
        Load generation summary from gen_summary.json.

        Args:
            gen_id: Generation number

        Returns:
            Summary dictionary or None if not found
        """
        gen_dir = self.get_generation_dir(gen_id)
        summary_path = os.path.join(gen_dir, "gen_summary.json")

        if not os.path.exists(summary_path):
            return None

        with open(summary_path, 'r') as f:
            return json.load(f)

    def get_latest_generation_id(self) -> int:
        """
        Get the latest (highest) generation ID.

        Returns:
            Latest generation ID, or -1 if no generations exist
        """
        if not os.path.exists(self.base_dir):
            return -1

        gen_dirs = [
            d for d in os.listdir(self.base_dir)
            if d.startswith("gen_") and os.path.isdir(os.path.join(self.base_dir, d))
        ]

        if not gen_dirs:
            return -1

        # Extract generation numbers
        gen_ids = []
        for d in gen_dirs:
            try:
                gen_id = int(d.split("_")[1])
                gen_ids.append(gen_id)
            except (IndexError, ValueError):
                continue

        return max(gen_ids) if gen_ids else -1

    def generation_exists(self, gen_id: int) -> bool:
        """Check if a generation directory exists."""
        return os.path.exists(self.get_generation_dir(gen_id))

    def list_generations(self) -> List[int]:
        """
        List all generation IDs in chronological order.

        Returns:
            Sorted list of generation IDs
        """
        if not os.path.exists(self.base_dir):
            return []

        gen_dirs = [
            d for d in os.listdir(self.base_dir)
            if d.startswith("gen_") and os.path.isdir(os.path.join(self.base_dir, d))
        ]

        gen_ids = []
        for d in gen_dirs:
            try:
                gen_id = int(d.split("_")[1])
                gen_ids.append(gen_id)
            except (IndexError, ValueError):
                continue

        return sorted(gen_ids)


def create_initial_generation_summary(gen_id: int) -> Dict:
    """
    Create initial generation summary structure.

    Args:
        gen_id: Generation number

    Returns:
        Initial summary dictionary
    """
    return {
        "gen_id": gen_id,
        "timestamp": datetime.now().isoformat(),
        "population_size": 6,
        "invalid_count": 0,
        "candidate_origins": {
            "mutate_weak": 0,
            "mutate_strong": 0,
            "crossover_winner_archive": 0,
            "crossover_archive_archive": 0,
            "random_baseline": 0,
            "random_extreme": 0
        },
        "population_metrics": {
            "xy_pair_count": {"mean": 0.0, "std": 0.0, "min": 0, "max": 0},
            "mean_pair_dz": {"mean": 0.0, "std": 0.0},
            "n_points": {"mean": 0.0, "std": 0.0}
        },
        "diversity_score": 0.0
    }


if __name__ == "__main__":
    # Test generation manager
    manager = GenerationManager("../gen_history")

    # Create generation 0 structure
    print("Creating generation 0 structure...")
    structure = manager.create_generation_structure(0)

    print("\nGeneration structure created:")
    for key, path in structure.items():
        print(f"  {key}: {path}")

    # Create initial summary
    summary = create_initial_generation_summary(0)
    manager.save_generation_summary(0, summary)
    print(f"\nGeneration summary saved to gen_000/gen_summary.json")

    # Test retrieval
    latest = manager.get_latest_generation_id()
    print(f"\nLatest generation ID: {latest}")

    all_gens = manager.list_generations()
    print(f"All generations: {all_gens}")
