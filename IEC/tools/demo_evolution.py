#!/usr/bin/env python3
"""
Automated demo of evolution loop (for testing purposes)
This simulates user selections to test the full system
"""

import sys
import os
import random

sys.path.insert(0, os.path.dirname(__file__))

from iec_terminal_ui import (
    display_pair,
    log_choice,
    trigger_next_generation
)

def run_demo(num_generations=3):
    """Run automated demo with random selections."""
    print("\n" + "="*60)
    print("  AUTOMATED EVOLUTION DEMO")
    print(f"  Running {num_generations} generations with random selection")
    print("="*60)

    for gen in range(num_generations):
        print(f"\n{'#'*60}")
        print(f"  GENERATION {gen + 1}/{num_generations}")
        print(f"{'#'*60}")

        # Display current pair
        meta_A, meta_B = display_pair()

        if meta_A is None:
            print("\n✗ No generation found. Run: python generate_pair.py --init")
            return

        # Random selection
        selected = random.choice(['A', 'B'])
        print(f"\n🎲 Random selection: {selected}")

        # Log selection
        log_choice(selected, meta_A, meta_B)

        # Generate next generation
        if gen < num_generations - 1:  # Don't generate after last
            print(f"\n⏳ Generating next generation...")
            success = trigger_next_generation(selected)

            if not success:
                print("\n✗ Generation failed")
                return

    print("\n" + "="*60)
    print("  DEMO COMPLETE!")
    print(f"  Generated {num_generations} generations")
    print("  Check log/choices.csv for selection history")
    print("="*60 + "\n")

if __name__ == '__main__':
    num_gens = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    run_demo(num_gens)
