#!/usr/bin/env python3
"""
iec_terminal_ui.py - Terminal-based Interactive Evolutionary Computation UI

This script provides a command-line interface for:
1. Displaying information about generated forms A and B
2. Selecting preferred form (A or B)
3. Logging selection to choices.csv
4. Triggering next generation cycle

Usage:
    python iec_terminal_ui.py
"""

import os
import sys
import json
import csv
import subprocess
import shutil
from datetime import datetime
import numpy as np

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
GEN_DIR = os.path.join(PROJECT_ROOT, 'gen')
LOG_DIR = os.path.join(PROJECT_ROOT, 'log')
ELITE_DIR = os.path.join(PROJECT_ROOT, 'elite')  # Elite archive
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, 'archive')  # Genotype archive for preference learning
MODEL_DIR = os.path.join(PROJECT_ROOT, 'model')  # Trained preference model
GNN_MODEL_DIR = os.path.join(PROJECT_ROOT, 'model', 'gnn')  # Trained GNN preference model

OBJ_A_PATH = os.path.join(GEN_DIR, 'A.obj')
OBJ_B_PATH = os.path.join(GEN_DIR, 'B.obj')
OBJ_A_INNER_PATH = os.path.join(GEN_DIR, 'A_inner.obj')
OBJ_B_INNER_PATH = os.path.join(GEN_DIR, 'B_inner.obj')
META_A_PATH = os.path.join(GEN_DIR, 'meta_A.json')
META_B_PATH = os.path.join(GEN_DIR, 'meta_B.json')
CHOICES_CSV = os.path.join(LOG_DIR, 'choices.csv')
GENERATE_SCRIPT = os.path.join(SCRIPT_DIR, 'generate_pair.py')

# Session management (Issue 8)
MAX_ITERATIONS_PER_SESSION = 15


# ===== Helper Functions =====

def should_trigger_training(num_choices):
    """
    Determine if training should be triggered based on number of choices.

    Training schedule:
    - First: 20 selections
    - Then: Every 5 selections (25, 30, 35, 40, ...)

    Args:
        num_choices: Total number of selections made

    Returns:
        bool: True if training should be triggered
    """
    if num_choices == 20:
        return True  # First training at 20 selections
    elif num_choices > 20 and (num_choices - 20) % 5 == 0:
        return True  # Subsequent training every 5 selections
    else:
        return False


def load_metadata(meta_path):
    """Load metadata from JSON file."""
    try:
        with open(meta_path, 'r') as f:
            data = json.load(f)
            return data.get('metadata', {}), data.get('points', [])
    except Exception as e:
        print(f"Error loading metadata: {e}")
        return {}, []


def count_obj_stats(obj_path):
    """Count vertices and faces in OBJ file."""
    vertices = 0
    faces = 0
    groups = set()

    try:
        with open(obj_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('v '):
                    vertices += 1
                elif line.startswith('f '):
                    faces += 1
                elif line.startswith('g '):
                    groups.add(line.split()[1] if len(line.split()) > 1 else 'default')
    except Exception as e:
        print(f"Error reading OBJ: {e}")

    return vertices, faces, len(groups)


def display_form_info(label, meta_path, obj_path):
    """Display information about a form."""
    meta, points = load_metadata(meta_path)
    vertices, faces, groups = count_obj_stats(obj_path)

    print(f"\n{'='*50}")
    print(f"  CANDIDATE {label}")
    print(f"{'='*50}")
    print(f"  Hash:       {meta.get('hash', 'N/A')}")
    print(f"  Points:     {meta.get('n_points', 0)}")
    print(f"  Vertices:   {vertices}")
    print(f"  Faces:      {faces}")
    print(f"  Cells:      {groups}")

    # Display point summary
    if points:
        weights = [p['weight'] for p in points]
        positions = [p['position'] for p in points]

        print(f"\n  Weight stats (mm):")
        print(f"    Min:  {min(weights):.1f}")
        print(f"    Max:  {max(weights):.1f}")
        print(f"    Avg:  {sum(weights)/len(weights):.1f}")

        # Display coordinate ranges
        if positions:
            pos_array = np.array(positions)
            print(f"\n  Coordinate range (mm):")
            print(f"    X: {pos_array[:, 0].min():.1f} - {pos_array[:, 0].max():.1f}")
            print(f"    Y: {pos_array[:, 1].min():.1f} - {pos_array[:, 1].max():.1f}")
            print(f"    Z: {pos_array[:, 2].min():.1f} - {pos_array[:, 2].max():.1f}")

    # Display file size
    size_kb = os.path.getsize(obj_path) / 1024
    print(f"\n  File size:  {size_kb:.1f} KB")
    print(f"{'='*50}")


def log_choice(selected, meta_A, meta_B):
    """Log user's choice to choices.csv."""
    os.makedirs(LOG_DIR, exist_ok=True)

    file_exists = os.path.isfile(CHOICES_CSV)

    with open(CHOICES_CSV, 'a', newline='') as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(['timestamp', 'iteration', 'selected', 'parent_hash',
                           'hash_A', 'hash_B', 'n_points_A', 'n_points_B'])

        timestamp = datetime.now().isoformat()
        iteration = meta_A.get('iteration', 0)
        parent_hash = meta_A.get('parent_hash', 'null')
        hash_A = meta_A.get('hash', '')
        hash_B = meta_B.get('hash', '')
        n_points_A = meta_A.get('n_points', 0)
        n_points_B = meta_B.get('n_points', 0)

        writer.writerow([timestamp, iteration, selected, parent_hash,
                        hash_A, hash_B, n_points_A, n_points_B])

    print(f"\n✓ Logged choice: {selected} (iteration {iteration})")
    print(f"  Log file: {CHOICES_CSV}")


def archive_genotypes(meta_A, meta_B):
    """
    Archive current genotypes for preference learning.

    Saves meta_A.json and meta_B.json to archive/ directory
    with hash-based filenames for later retrieval by train_preference_model.py

    Args:
        meta_A: Metadata dict for candidate A
        meta_B: Metadata dict for candidate B
    """
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    hash_A = meta_A.get('hash', 'unknown')
    hash_B = meta_B.get('hash', 'unknown')

    # Copy meta_A.json
    archive_A = os.path.join(ARCHIVE_DIR, f'meta_{hash_A}.json')
    if not os.path.exists(archive_A):
        shutil.copy2(META_A_PATH, archive_A)

    # Copy meta_B.json
    archive_B = os.path.join(ARCHIVE_DIR, f'meta_{hash_B}.json')
    if not os.path.exists(archive_B):
        shutil.copy2(META_B_PATH, archive_B)


def check_ai_mode_available():
    """
    Check if AI-assisted mode is available.

    Requirements:
        1. Model files exist (preference_model.pkl, scaler.pkl)
        2. At least 10 choices logged in choices.csv

    Returns:
        bool: True if AI mode can be enabled
    """
    # Check model files
    model_path = os.path.join(MODEL_DIR, 'preference_model.pkl')
    scaler_path = os.path.join(MODEL_DIR, 'scaler.pkl')

    if not os.path.exists(model_path) or not os.path.exists(scaler_path):
        return False

    # Check number of logged choices
    if not os.path.exists(CHOICES_CSV):
        return False

    try:
        with open(CHOICES_CSV, 'r') as f:
            # Count lines (subtract 1 for header)
            num_choices = sum(1 for line in f) - 1

        # Require at least 10 choices for stable model
        return num_choices >= 10
    except:
        return False


def check_gnn_mode_available():
    """
    Check if GNN-assisted mode is available.

    Requirements:
        1. GNN model files exist (training_config.json, preference_gnn.pt, scalers)
        2. At least 10 choices logged in choices.csv

    Returns:
        bool: True if GNN mode can be enabled
    """
    # Check GNN model files
    config_path = os.path.join(GNN_MODEL_DIR, 'training_config.json')
    model_path = os.path.join(GNN_MODEL_DIR, 'preference_gnn.pt')
    node_scaler_path = os.path.join(GNN_MODEL_DIR, 'node_scaler.pkl')
    global_scaler_path = os.path.join(GNN_MODEL_DIR, 'global_scaler.pkl')

    if not all([os.path.exists(p) for p in [config_path, model_path, node_scaler_path, global_scaler_path]]):
        return False

    # Check number of logged choices
    if not os.path.exists(CHOICES_CSV):
        return False

    try:
        with open(CHOICES_CSV, 'r') as f:
            # Count lines (subtract 1 for header)
            num_choices = sum(1 for line in f) - 1

        # Require at least 10 choices for stable model
        return num_choices >= 10
    except:
        return False


def trigger_next_generation(selected):
    """
    Generate next generation from selected parent.

    Automatically uses AI-assisted mode if:
        - Model is trained and available
        - At least 10 choices have been logged

    Automatically uses --remove-boundary-cells if:
        - Parent has corresponding inner.obj file
    """
    parent_path = META_A_PATH if selected == 'A' else META_B_PATH
    parent_inner_path = OBJ_A_INNER_PATH if selected == 'A' else OBJ_B_INNER_PATH

    print(f"\n{'='*50}")
    print(f"  Generating next generation from {selected}...")
    print(f"{'='*50}\n")

    # Build command
    cmd = [sys.executable, GENERATE_SCRIPT, '--parent', parent_path]

    # Read and pass inherited generation parameters
    try:
        with open(parent_path, 'r') as f:
            parent_data = json.load(f)

        generation_config = parent_data.get('metadata', {}).get('generation_config')

        if generation_config:
            n_points = generation_config.get('n_points')
            target_pairs = generation_config.get('target_pairs', 0)

            if n_points is not None:
                cmd.extend(['--n-points', str(n_points)])
            if target_pairs > 0:
                cmd.extend(['--target-pairs', str(target_pairs)])
                cmd.append('--export-xy-lines')  # Auto-export XY lines when target_pairs > 0

            print(f"📊 継承パラメータ:")
            print(f"   n_points: {n_points} (固定点除く)")
            print(f"   target_pairs: {target_pairs}\n")
    except Exception as e:
        print(f"⚠ 設定の読み込み失敗: {e}")
        print(f"  デフォルト値を使用します\n")

    # Check if parent has inner.obj (boundary cells removed version)
    use_remove_boundary = os.path.exists(parent_inner_path)
    if use_remove_boundary:
        cmd.append('--remove-boundary-cells')
        print("🔲 Boundary Removal: Enabled")
        print("   (Parent has inner version, continuing with boundary removal)\n")

    # Check if GNN or AI mode is available (prioritize GNN)
    use_gnn = check_gnn_mode_available()
    use_ai = check_ai_mode_available()

    if use_gnn:
        cmd.extend(['--use-gnn-model', '--gnn-model-dir', GNN_MODEL_DIR])
        print("🧠 GNN-Assisted Mode: Enabled")
        print("   (GNN will generate 100 candidates and select best 2)\n")
    elif use_ai:
        cmd.extend(['--use-model', '--model-dir', MODEL_DIR])
        print("🤖 AI-Assisted Mode: Enabled")
        print("   (AI will generate 100 candidates and select best 2)\n")
    else:
        print("👤 Traditional Mode: Pure human selection")
        print("   (Tip: After 10+ selections, AI mode will activate)\n")

    try:
        result = subprocess.run(cmd, cwd=SCRIPT_DIR, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)

        return result.returncode == 0
    except Exception as e:
        print(f"Error: {e}")
        return False


def get_user_choice():
    """Prompt user to select A, B, save to elite, or quit."""
    while True:
        choice = input("\nSelect [A/B/S=Save to Elite/Q=Quit]: ").strip().upper()
        if choice in ['A', 'B', 'S', 'Q']:
            return choice
        print("Invalid input. Please enter A, B, S, or Q.")


def save_elite(meta_path, obj_path, inner_obj_path=None):
    """
    Copy current candidate to elite archive.

    Elite archive preserves favorite forms across evolution sessions,
    addressing human fatigue (Issue 8).

    Args:
        meta_path: Path to metadata JSON
        obj_path: Path to OBJ file
        inner_obj_path: Path to inner OBJ file (optional, if boundary cells removed)
    """
    os.makedirs(ELITE_DIR, exist_ok=True)

    # Load metadata to get hash for filename
    meta, _ = load_metadata(meta_path)
    gen_hash = meta.get('hash', 'unknown')
    iteration = meta.get('iteration', 0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Copy files with descriptive names
    elite_meta = os.path.join(ELITE_DIR, f'elite_iter{iteration:03d}_{gen_hash}_{timestamp}.json')
    elite_obj = os.path.join(ELITE_DIR, f'elite_iter{iteration:03d}_{gen_hash}_{timestamp}.obj')

    shutil.copy(meta_path, elite_meta)
    shutil.copy(obj_path, elite_obj)

    print(f"\n✓ Saved to elite archive:")
    print(f"  {os.path.basename(elite_meta)}")
    print(f"  {os.path.basename(elite_obj)}")

    # Copy inner.obj if it exists
    if inner_obj_path and os.path.exists(inner_obj_path):
        elite_inner_obj = os.path.join(ELITE_DIR, f'elite_iter{iteration:03d}_{gen_hash}_{timestamp}_inner.obj')
        shutil.copy(inner_obj_path, elite_inner_obj)
        print(f"  {os.path.basename(elite_inner_obj)}")

    print(f"  Location: {ELITE_DIR}/")

    return elite_meta, elite_obj


def display_header(iteration, parent_hash):
    """Display session header."""
    print("\n" + "="*60)
    print("  INTERACTIVE EVOLUTIONARY COMPUTATION - TERMINAL UI")
    print("="*60)
    print(f"  Iteration:       {iteration}")
    if parent_hash and parent_hash != 'null':
        print(f"  Parent hash:     {parent_hash}")
    else:
        print(f"  Parent:          Initial generation")
    print(f"  Bounding box:    800mm x 700mm x 400mm")
    print("="*60)


# ===== Main Functions =====

def display_pair():
    """Display information about current A/B pair."""
    if not os.path.exists(OBJ_A_PATH) or not os.path.exists(OBJ_B_PATH):
        print("\n✗ Error: No generation found!")
        print(f"\nPlease run:")
        print(f"  cd {SCRIPT_DIR}")
        print(f"  python generate_pair.py --init")
        return None, None

    meta_A, _ = load_metadata(META_A_PATH)
    meta_B, _ = load_metadata(META_B_PATH)

    # Display header
    iteration = meta_A.get('iteration', 0)
    parent_hash = meta_A.get('parent_hash', 'null')
    display_header(iteration, parent_hash)

    # Display both forms
    display_form_info('A', META_A_PATH, OBJ_A_PATH)
    display_form_info('B', META_B_PATH, OBJ_B_PATH)

    return meta_A, meta_B


def run_evolution_loop():
    """Main evolution loop with session management (Issue 8)."""
    print("\n" + "="*60)
    print("  Starting IEC Evolution Session")
    print("="*60)
    print("\n  You can open the OBJ files in any 3D viewer:")
    print(f"    - A: {OBJ_A_PATH}")
    print(f"    - B: {OBJ_B_PATH}")
    print("\n  Suggested viewers:")
    print("    - Rhino")
    print("    - Blender")
    print("    - MeshLab")
    print("    - Online: https://3dviewer.net/")
    print(f"\n  Session limit: {MAX_ITERATIONS_PER_SESSION} iterations")
    print("  (to prevent evaluation fatigue)")

    # Check GNN/AI mode status
    gnn_available = check_gnn_mode_available()
    ai_available = check_ai_mode_available()

    if gnn_available:
        print(f"\n  🧠 GNN Mode: ENABLED")
        print(f"     GNN will suggest best candidates from 100 options")
        print(f"     (Using advanced Graph Neural Network model)")
    elif ai_available:
        print(f"\n  🤖 AI Mode: ENABLED")
        print(f"     AI will suggest best candidates from 100 options")
    else:
        # Count current choices
        num_choices = 0
        if os.path.exists(CHOICES_CSV):
            try:
                with open(CHOICES_CSV, 'r') as f:
                    num_choices = sum(1 for line in f) - 1
            except:
                pass

        print(f"\n  👤 AI Mode: Not yet available")
        print(f"     Choices logged: {num_choices}/10 (need 10+ to enable AI)")
        if num_choices > 0:
            remaining = max(0, 10 - num_choices)
            print(f"     {remaining} more selections until AI mode activates!")

    generation_count = 0

    while True:
        # Display current pair
        meta_A, meta_B = display_pair()

        if meta_A is None:
            break

        # Get user selection
        choice = get_user_choice()

        if choice == 'Q':
            print("\n" + "="*60)
            print("  Evolution session ended by user")
            print(f"  Total generations: {generation_count}")
            print(f"  Log: {CHOICES_CSV}")
            if os.path.exists(ELITE_DIR):
                elite_count = len([f for f in os.listdir(ELITE_DIR) if f.endswith('.obj')])
                print(f"  Elite archive: {elite_count} forms saved")
            print("="*60 + "\n")
            break

        # === IMPROVEMENT: Issue 8 - Elite Archive ===
        if choice == 'S':
            which = input("Save A or B to elite archive? [A/B]: ").strip().upper()
            if which == 'A':
                save_elite(META_A_PATH, OBJ_A_PATH, OBJ_A_INNER_PATH)
            elif which == 'B':
                save_elite(META_B_PATH, OBJ_B_PATH, OBJ_B_INNER_PATH)
            else:
                print("Invalid choice. Nothing saved.")
            continue  # Return to selection without advancing generation

        # Log selection (only for A/B, not S)
        log_choice(choice, meta_A, meta_B)

        # Archive genotypes for preference learning
        archive_genotypes(meta_A, meta_B)

        # Check if we should prompt for model training
        if os.path.exists(CHOICES_CSV):
            with open(CHOICES_CSV, 'r') as f:
                num_choices = sum(1 for line in f) - 1

            # Prompt to train model with new schedule: 20 -> 5 -> 5 -> ...
            if should_trigger_training(num_choices):
                gnn_exists = check_gnn_mode_available()
                model_exists = check_ai_mode_available()

                # Calculate next training milestone
                if num_choices == 20:
                    next_training = 25
                else:
                    next_training = num_choices + 5

                if not gnn_exists and not model_exists:
                    print(f"\n{'='*60}")
                    print(f"  🎓 MILESTONE: {num_choices} selections completed!")
                    print(f"  Next training: {next_training} selections")
                    print(f"{'='*60}")
                    print(f"\n  You can now train preference learning models.")
                    print(f"  This will enable AI-assisted candidate selection.\n")
                    print(f"  Option 1 - GNN Model (recommended):")
                    print(f"    pytorch_project/.venv/bin/python pytorch_project/training/train_pref_gnn.py log/choices.csv --verbose\n")
                    print(f"  Option 2 - LogisticRegression Model:")
                    print(f"    python tools/train_preference_model.py log/choices.csv --verbose\n")
                    print(f"  After training, AI mode will activate automatically.")
                    print(f"{'='*60}\n")
                elif not gnn_exists and model_exists:
                    print(f"\n  💡 Tip: You can train the GNN model for better performance:")
                    print(f"      pytorch_project/.venv/bin/python pytorch_project/training/train_pref_gnn.py log/choices.csv --verbose\n")
                elif num_choices > 10:
                    print(f"\n  💡 Tip: You can retrain the models with {num_choices} selections for better accuracy.")
                    print(f"      GNN: pytorch_project/.venv/bin/python pytorch_project/training/train_pref_gnn.py log/choices.csv --verbose")
                    print(f"      LR:  python tools/train_preference_model.py log/choices.csv --verbose\n")

        # Ask if continue
        cont = input("\nGenerate next generation? [Y/n]: ").strip().upper()
        if cont == 'N':
            print("\n" + "="*60)
            print("  Evolution paused")
            print(f"  Total generations: {generation_count}")
            print("\n  To resume, run:")
            print(f"    python {os.path.basename(__file__)}")
            print("="*60 + "\n")
            break

        # Generate next generation
        success = trigger_next_generation(choice)

        if not success:
            print("\n✗ Generation failed. Stopping.")
            break

        generation_count += 1

        # === IMPROVEMENT: Issue 8 - Session Limit Warning ===
        if generation_count >= MAX_ITERATIONS_PER_SESSION:
            print("\n" + "="*60)
            print("  ⚠️  SESSION LIMIT REACHED")
            print(f"  You have completed {generation_count} iterations.")
            print("  ")
            print("  Human evaluation quality may degrade beyond this point.")
            print("  Recommendation: Take a break and resume later.")
            print("  ")
            print("  Your progress has been saved. You can:")
            print("    - Save current favorites to elite archive (S)")
            print("    - Continue anyway (not recommended)")
            print("    - Quit and resume in a fresh session")
            print("="*60)

            cont_anyway = input("\nContinue anyway? [y/N]: ").strip().upper()
            if cont_anyway != 'Y':
                print("\n" + "="*60)
                print("  Session ended at recommended limit")
                print(f"  Total generations: {generation_count}")
                print(f"  Log: {CHOICES_CSV}")
                if os.path.exists(ELITE_DIR):
                    elite_count = len([f for f in os.listdir(ELITE_DIR) if f.endswith('.obj')])
                    print(f"  Elite archive: {elite_count} forms saved")
                print("="*60 + "\n")
                break

        print("\n" + "-"*60)
        print("  Next generation ready!")
        print("-"*60)
        input("\nPress Enter to view next generation...")


def show_help():
    """Show help message."""
    print("\nIEC Terminal UI - Usage:")
    print("\n  python iec_terminal_ui.py          # Start evolution loop")
    print("\nWorkflow:")
    print("  1. View form statistics in terminal")
    print("  2. Open OBJ files in your preferred 3D viewer")
    print("  3. Select preferred form (A or B)")
    print("  4. Next generation is automatically created")
    print("  5. Repeat until satisfied")
    print("\nOBJ file locations:")
    print(f"  {OBJ_A_PATH}")
    print(f"  {OBJ_B_PATH}")


# ===== Entry Point =====

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        show_help()
        return

    run_evolution_loop()


if __name__ == '__main__':
    main()
