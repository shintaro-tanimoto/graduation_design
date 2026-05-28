# -*- coding: utf-8 -*-
"""
Tournament Manager for 6-Candidate Comparison System
Implements Swiss-system tournament for fair and efficient candidate comparison
"""

import json
import random
from typing import Dict, List, Tuple
from datetime import datetime


class TournamentManager:
    """
    Manages Swiss-system tournament for 6 candidates.

    Swiss-system tournament:
    - Round 0: Random pairings (3 matches)
    - Round 1+: Score-based pairings (3 matches)
    - Scoring: 1 point per win
    - Tiebreaker: Head-to-head record → Random

    Total matches: n_rounds × 3 (default: 3 rounds = 9 matches)
    """

    def __init__(self, candidates: List[Dict], n_rounds: int = 3):
        """
        Initialize tournament.

        Args:
            candidates: List of candidate dicts with at least 'cand_id' key
                       Example: [{'cand_id': 'cand_00', 'meta': {...}}, ...]
            n_rounds: Number of rounds to play (default: 3)
        """
        if len(candidates) != 6:
            raise ValueError(f"Tournament requires exactly 6 candidates, got {len(candidates)}")

        self.candidates = candidates
        self.n_rounds = n_rounds
        self.current_round = 0

        # Initialize scores
        self.scores = {cand['cand_id']: 0 for cand in candidates}

        # Match history: [(cand_a, cand_b, winner, round), ...]
        self.match_history = []

        # Head-to-head records: {(cand_a, cand_b): winner_id}
        self.head_to_head = {}

        # Tournament start time
        self.start_time = datetime.now()

    def generate_round_pairings(self) -> List[Tuple[str, str]]:
        """
        Generate pairings for current round (Swiss-system).

        Round 0: Random pairings
        Round 1+: Score-based pairings (pair similar scores, avoid rematches)

        Returns:
            List of pairings: [(cand_a_id, cand_b_id), ...]
        """
        if self.current_round == 0:
            # Round 0: Random pairings
            shuffled = list(self.candidates)
            random.shuffle(shuffled)

            pairings = [
                (shuffled[0]['cand_id'], shuffled[1]['cand_id']),
                (shuffled[2]['cand_id'], shuffled[3]['cand_id']),
                (shuffled[4]['cand_id'], shuffled[5]['cand_id'])
            ]

        else:
            # Round 1+: Score-based pairings (Swiss-system)
            # Sort by score (descending)
            sorted_cands = sorted(
                self.candidates,
                key=lambda c: self.scores[c['cand_id']],
                reverse=True
            )

            cand_ids = [c['cand_id'] for c in sorted_cands]

            # Try to pair: (0,1), (2,3), (4,5)
            # Avoid rematches if possible
            pairings = []
            used = set()

            # Greedy pairing: pair adjacent candidates in score order
            for i in range(0, 6, 2):
                if i >= len(cand_ids):
                    break

                cand_a = cand_ids[i]
                cand_b = cand_ids[i + 1]

                # Check if rematch
                pair_key = tuple(sorted([cand_a, cand_b]))
                if pair_key in self.head_to_head:
                    # Try swapping with next candidate to avoid rematch
                    if i + 2 < 6:
                        cand_b_alt = cand_ids[i + 2]
                        pair_key_alt = tuple(sorted([cand_a, cand_b_alt]))
                        if pair_key_alt not in self.head_to_head:
                            # Swap
                            cand_ids[i + 1], cand_ids[i + 2] = cand_ids[i + 2], cand_ids[i + 1]
                            cand_b = cand_b_alt

                pairings.append((cand_a, cand_b))
                used.add(cand_a)
                used.add(cand_b)

        return pairings

    def record_match_result(self, cand_a_id: str, cand_b_id: str, winner_id: str):
        """
        Record match result and update scores.

        Args:
            cand_a_id: First candidate ID
            cand_b_id: Second candidate ID
            winner_id: Winner's ID (must be cand_a_id or cand_b_id)

        Raises:
            ValueError: If winner_id is not one of the participants
        """
        if winner_id not in [cand_a_id, cand_b_id]:
            raise ValueError(f"Winner {winner_id} must be either {cand_a_id} or {cand_b_id}")

        # Update scores
        self.scores[winner_id] += 1

        # Record match
        match_record = {
            'round': self.current_round,
            'match_id': len(self.match_history),
            'cand_a': cand_a_id,
            'cand_b': cand_b_id,
            'winner': winner_id,
            'timestamp': datetime.now().isoformat()
        }
        self.match_history.append(match_record)

        # Update head-to-head
        pair_key = tuple(sorted([cand_a_id, cand_b_id]))
        self.head_to_head[pair_key] = winner_id

    def get_current_standings(self) -> List[Tuple[str, int]]:
        """
        Get current standings sorted by score.

        Returns:
            List of (cand_id, score) tuples, sorted by score (descending)
        """
        standings = [(cand_id, score) for cand_id, score in self.scores.items()]
        standings.sort(key=lambda x: x[1], reverse=True)
        return standings

    def get_winner(self) -> str:
        """
        Determine tournament winner with tiebreaker.

        Tiebreaker logic:
        1. Highest score
        2. Head-to-head record (if tied candidates played each other)
        3. Random selection

        Returns:
            Winner's cand_id
        """
        standings = self.get_current_standings()

        # Get all candidates with highest score
        max_score = standings[0][1]
        top_candidates = [cand_id for cand_id, score in standings if score == max_score]

        if len(top_candidates) == 1:
            # Clear winner
            return top_candidates[0]

        # Tiebreaker: head-to-head
        if len(top_candidates) == 2:
            pair_key = tuple(sorted(top_candidates))
            if pair_key in self.head_to_head:
                return self.head_to_head[pair_key]

        # Tiebreaker: random
        winner = random.choice(top_candidates)
        return winner

    def to_log_dict(self) -> Dict:
        """
        Export tournament results as JSON-serializable dict.

        Returns:
            Complete tournament log dict
        """
        duration_seconds = (datetime.now() - self.start_time).total_seconds()

        return {
            'n_rounds': self.n_rounds,
            'total_matches': len(self.match_history),
            'match_history': self.match_history,
            'final_scores': self.scores,
            'standings': self.get_current_standings(),
            'winner': self.get_winner(),
            'tournament_duration_seconds': duration_seconds
        }


# Unit test (run with: python generation/comparison_tournament.py)
if __name__ == "__main__":
    print("Tournament Manager Unit Test")
    print("=" * 60)

    # Create mock candidates
    mock_candidates = [
        {'cand_id': f'cand_{i:02d}', 'n_points': 100 + i * 10}
        for i in range(6)
    ]

    print(f"  Created {len(mock_candidates)} mock candidates")

    # Initialize tournament
    tournament = TournamentManager(mock_candidates, n_rounds=3)
    print("✓ Tournament initialized (3 rounds)")

    # Simulate tournament
    for round_num in range(3):
        print(f"\n=== Round {round_num} ===")

        pairings = tournament.generate_round_pairings()
        print(f"  Pairings: {pairings}")

        # Simulate matches (random winner)
        for cand_a, cand_b in pairings:
            winner = random.choice([cand_a, cand_b])
            tournament.record_match_result(cand_a, cand_b, winner)
            print(f"  Match: {cand_a} vs {cand_b} → Winner: {winner}")

        # Show current standings
        standings = tournament.get_current_standings()
        print("\n  Current Standings:")
        for rank, (cand_id, score) in enumerate(standings, 1):
            print(f"    {rank}. {cand_id}: {score} points")

        tournament.current_round += 1

    # Final results
    print("\n" + "=" * 60)
    print("Final Results:")
    print(f"  Winner: {tournament.get_winner()}")

    # Export log
    log = tournament.to_log_dict()
    print(f"  Total matches: {log['total_matches']}")
    print(f"  Duration: {log['tournament_duration_seconds']:.2f} seconds")

    print("\n✓ Tournament test complete!")
