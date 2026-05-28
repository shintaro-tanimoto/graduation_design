#!/usr/bin/env python3
"""
train_preference_model.py - Preference Learning from Pairwise Comparisons

Trains a binary classifier to predict which form the user prefers,
based on genotype features extracted from selection history.

Usage:
    python train_preference_model.py log/choices.csv
    python train_preference_model.py log/choices.csv --verbose
    python train_preference_model.py log/choices.csv --model-dir model/
"""

import sys
import os
import json
import argparse
import pandas as pd
import numpy as np
import pickle
from datetime import datetime
from pathlib import Path

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score, LeaveOneOut
from sklearn.metrics import accuracy_score, classification_report

# Import feature extraction
from extract_features import extract_features_from_genotype


# ===== Configuration =====

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_MODEL_DIR = PROJECT_ROOT / 'model'
GEN_ARCHIVE_DIR = PROJECT_ROOT / 'archive'  # Where old genotypes are stored


# ===== Data Loading =====

def load_genotype_from_hash(hash_value, search_dirs=['gen', 'archive', 'elite']):
    """
    Find and load genotype JSON file by hash.

    Searches in multiple directories for meta_*.json files.

    Args:
        hash_value: 8-character hash string
        search_dirs: List of directory names to search

    Returns:
        (points, weights) or (None, None) if not found
    """
    # Try to find file with this hash in metadata
    for dir_name in search_dirs:
        dir_path = PROJECT_ROOT / dir_name
        if not dir_path.exists():
            continue

        # Search all JSON files in directory
        for json_file in dir_path.glob('*.json'):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)

                # Check if hash matches
                meta_hash = data.get('metadata', {}).get('hash', '')
                if meta_hash == hash_value:
                    # Found it!
                    points = np.array([p['position'] for p in data['points']])
                    weights = np.array([p['weight'] for p in data['points']])
                    return points, weights

            except (json.JSONDecodeError, KeyError):
                continue

    # Not found
    return None, None


def prepare_training_data(choices_csv, verbose=False, include_volume=False):
    """
    Prepare training dataset from choices.csv.

    Process:
        1. Load choices.csv
        2. For each row: load features for A and B
        3. Compute feature difference: features_A - features_B
        4. Label: 1 if A selected, 0 if B selected

    Args:
        choices_csv: Path to choices.csv file
        verbose: Print progress
        include_volume: Include volume features

    Returns:
        X: (N, d) feature differences
        y: (N,) binary labels (1=A, 0=B)
        valid_count: Number of successfully loaded pairs
    """
    # Load CSV
    df = pd.read_csv(choices_csv)

    if verbose:
        print(f"Loaded {len(df)} choice records from {choices_csv}")

    X_list = []
    y_list = []
    skipped = 0

    for idx, row in df.iterrows():
        hash_A = row['hash_A']
        hash_B = row['hash_B']
        selected = row['selected']

        # Load genotypes
        points_A, weights_A = load_genotype_from_hash(hash_A)
        points_B, weights_B = load_genotype_from_hash(hash_B)

        # Skip if either not found
        if points_A is None or points_B is None:
            if verbose:
                print(f"  ⚠ Row {idx}: Skipping (genotype not found: A={hash_A[:6]}, B={hash_B[:6]})")
            skipped += 1
            continue

        # Extract features
        from extract_features import extract_features_from_genotype
        features_A = extract_features_from_genotype(points_A, weights_A, include_volume=include_volume)
        features_B = extract_features_from_genotype(points_B, weights_B, include_volume=include_volume)

        # Compute difference (A - B)
        feature_diff = features_A - features_B

        # Label: 1 if A selected, 0 if B selected
        label = 1 if selected == 'A' else 0

        X_list.append(feature_diff)
        y_list.append(label)

    # Convert to arrays
    X = np.array(X_list)
    y = np.array(y_list)

    if verbose:
        print(f"\nTraining data prepared:")
        print(f"  Valid pairs: {len(X)}")
        print(f"  Skipped (missing files): {skipped}")
        if len(X) > 0:
            print(f"  Feature dimensions: {X.shape[1]}")
            print(f"  Class balance: A={y.sum()}, B={len(y)-y.sum()}")

    return X, y, len(X)


# ===== Model Training =====

def train_preference_model(X, y, verbose=False):
    """
    Train logistic regression model on pairwise preference data.

    Args:
        X: (N, d) feature differences
        y: (N,) binary labels
        verbose: Print training details

    Returns:
        model: Trained LogisticRegression
        scaler: Fitted StandardScaler
        metrics: dict with accuracy, cross-val score, etc.
    """
    if len(X) < 3:
        raise ValueError(f"Need at least 3 training samples, got {len(X)}")

    # Normalize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Train logistic regression
    model = LogisticRegression(
        C=1.0,
        max_iter=1000,
        random_state=42,
        solver='lbfgs'
    )
    model.fit(X_scaled, y)

    # Evaluate
    y_pred = model.predict(X_scaled)
    train_accuracy = accuracy_score(y, y_pred)

    # Cross-validation
    # Use Leave-One-Out for small datasets, otherwise use stratified k-fold
    if len(X) < 10:
        # Leave-One-Out for very small datasets
        loo = LeaveOneOut()
        cv_scores = cross_val_score(model, X_scaled, y, cv=loo, scoring='accuracy')
        cv_mean = cv_scores.mean()
        cv_std = cv_scores.std()
    else:
        # Stratified K-Fold for larger datasets
        # Ensure k <= min class count
        from sklearn.model_selection import StratifiedKFold
        import numpy as np
        min_class_count = min(np.bincount(y))
        n_splits = min(5, min_class_count)

        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        cv_scores = cross_val_score(model, X_scaled, y, cv=skf, scoring='accuracy')
        cv_mean = cv_scores.mean()
        cv_std = cv_scores.std()

    metrics = {
        'train_accuracy': train_accuracy,
        'cv_mean': cv_mean,
        'cv_std': cv_std,
        'n_samples': len(X),
        'n_features': X.shape[1],
    }

    if verbose:
        print(f"\n{'='*60}")
        print("  MODEL TRAINING RESULTS")
        print(f"{'='*60}")
        print(f"Training accuracy: {train_accuracy:.3f}")
        print(f"Cross-val accuracy: {cv_mean:.3f} ± {cv_std:.3f}")
        print(f"Samples used: {len(X)}")
        print(f"Feature dimensions: {X.shape[1]}")
        print(f"\nClassification Report:")
        print(classification_report(y, y_pred, target_names=['Prefer B', 'Prefer A']))

        # Feature importance (coefficients)
        print(f"\nFeature Importance (Logistic Regression Coefficients):")
        feature_names = [
            'n_points', 'weight_mean', 'weight_std', 'weight_min', 'weight_max',
            'point_density_mean', 'point_density_std', 'centrality_mean',
            'boundary_proximity', 'weight_range'
        ]
        if X.shape[1] > 10:
            feature_names += ['volume_mean', 'volume_max', 'volume_std', 'volume_cv']

        coeffs = model.coef_[0]
        for name, coef in zip(feature_names, coeffs):
            direction = "→ Prefer A" if coef > 0 else "→ Prefer B"
            print(f"  {name:20s}: {coef:+7.3f}  {direction}")

    return model, scaler, metrics


# ===== Model Persistence =====

def save_model(model, scaler, metrics, model_dir, verbose=False):
    """
    Save trained model, scaler, and training log.

    Outputs:
        model_dir/preference_model.pkl
        model_dir/scaler.pkl
        model_dir/training_log.txt
    """
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    # Save model
    model_path = model_dir / 'preference_model.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)

    # Save scaler
    scaler_path = model_dir / 'scaler.pkl'
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)

    # Save training log
    log_path = model_dir / 'training_log.txt'
    with open(log_path, 'w') as f:
        f.write("="*60 + "\n")
        f.write("PREFERENCE MODEL TRAINING LOG\n")
        f.write("="*60 + "\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"\nTraining Data:\n")
        f.write(f"  Samples: {metrics['n_samples']}\n")
        f.write(f"  Features: {metrics['n_features']}\n")
        f.write(f"\nModel Performance:\n")
        f.write(f"  Training Accuracy: {metrics['train_accuracy']:.3f}\n")
        f.write(f"  Cross-val Accuracy: {metrics['cv_mean']:.3f} ± {metrics['cv_std']:.3f}\n")
        f.write(f"\nModel Type: LogisticRegression\n")
        f.write(f"  Penalty: L2\n")
        f.write(f"  C: 1.0\n")
        f.write(f"  Solver: lbfgs\n")

    if verbose:
        print(f"\n{'='*60}")
        print("  MODEL SAVED")
        print(f"{'='*60}")
        print(f"Model: {model_path}")
        print(f"Scaler: {scaler_path}")
        print(f"Log: {log_path}")


def load_model(model_dir):
    """
    Load saved model and scaler.

    Returns:
        model: LogisticRegression
        scaler: StandardScaler
    """
    model_dir = Path(model_dir)

    model_path = model_dir / 'preference_model.pkl'
    scaler_path = model_dir / 'scaler.pkl'

    with open(model_path, 'rb') as f:
        model = pickle.load(f)

    with open(scaler_path, 'rb') as f:
        scaler = pickle.load(f)

    return model, scaler


# ===== CLI Interface =====

def main():
    parser = argparse.ArgumentParser(
        description='Train preference learning model from selection history'
    )
    parser.add_argument('choices_csv', type=str,
                       help='Path to choices.csv file')
    parser.add_argument('--model-dir', type=str, default=str(DEFAULT_MODEL_DIR),
                       help=f'Directory to save model (default: {DEFAULT_MODEL_DIR})')
    parser.add_argument('--include-volume', action='store_true', default=True,
                       help='Include volume estimation features (default: True)')
    parser.add_argument('--no-volume', dest='include_volume', action='store_false',
                       help='Disable volume estimation features')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Print detailed training info')
    parser.add_argument('--min-samples', type=int, default=3,
                       help='Minimum number of valid samples required (default: 3)')

    args = parser.parse_args()

    print(f"{'='*60}")
    print("  PREFERENCE MODEL TRAINING")
    print(f"{'='*60}\n")

    # Prepare data
    print("Step 1: Loading training data...")
    X, y, valid_count = prepare_training_data(
        args.choices_csv,
        verbose=args.verbose,
        include_volume=args.include_volume
    )

    # Check minimum samples
    if valid_count < args.min_samples:
        print(f"\n❌ ERROR: Need at least {args.min_samples} valid samples, but only {valid_count} found.")
        print(f"\nPossible reasons:")
        print(f"  - Meta JSON files not archived (only gen/meta_A.json and gen/meta_B.json exist)")
        print(f"  - Hash values in choices.csv don't match available files")
        print(f"\nSolution:")
        print(f"  - Run more IEC iterations to collect new data")
        print(f"  - Ensure genotypes are archived (see archive/ or elite/ directories)")
        sys.exit(1)

    # Train model
    print(f"\nStep 2: Training logistic regression model...")
    model, scaler, metrics = train_preference_model(X, y, verbose=args.verbose)

    # Save model
    print(f"\nStep 3: Saving model...")
    save_model(model, scaler, metrics, args.model_dir, verbose=args.verbose)

    print(f"\n{'='*60}")
    print("✓ TRAINING COMPLETE")
    print(f"{'='*60}")
    print(f"\nModel is ready to use for AI-assisted candidate selection.")
    print(f"Next: Run generate_pair.py with --use-model flag\n")


if __name__ == '__main__':
    main()
