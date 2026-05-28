#!/bin/bash
# clear_logs.sh - Remove all log files and directories for IEC project
# WARNING: This will permanently delete selection history and genotype archives

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "  IEC Log Removal Script"
echo "============================================================"
echo ""
echo "⚠️  WARNING: This will DELETE the following files/directories:"
echo ""
echo "  - log/choices.csv          (selection history)"
echo "  - log/iteration_counter.txt (generation counter)"
echo "  - gen_log/                 (generation history)"
echo "  - archive/                 (~60 genotype files)"
echo ""
echo "PRESERVED (will NOT be deleted):"
echo "  - elite/                   (user favorites)"
echo "  - model/                   (trained GNN models)"
echo "  - gen/                     (current generation)"
echo ""
echo "⚠️  This action CANNOT be undone. No backup will be created."
echo ""
read -p "Continue? [y/N]: " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Cancelled. No files were deleted."
    exit 0
fi

echo ""
echo "============================================================"
echo "  Deleting log files..."
echo "============================================================"

# Delete log/choices.csv
if [ -f "log/choices.csv" ]; then
    rm -f "log/choices.csv"
    echo "✓ Deleted: log/choices.csv"
else
    echo "  (not found: log/choices.csv)"
fi

# Delete log/iteration_counter.txt
if [ -f "log/iteration_counter.txt" ]; then
    rm -f "log/iteration_counter.txt"
    echo "✓ Deleted: log/iteration_counter.txt"
else
    echo "  (not found: log/iteration_counter.txt)"
fi

# Delete gen_log/ directory
if [ -d "gen_log" ]; then
    FILE_COUNT=$(find gen_log -type f | wc -l)
    rm -rf "gen_log"
    echo "✓ Deleted: gen_log/ ($FILE_COUNT files removed)"
else
    echo "  (not found: gen_log/)"
fi

# Delete archive/ directory
if [ -d "archive" ]; then
    FILE_COUNT=$(find archive -type f | wc -l)
    rm -rf "archive"
    echo "✓ Deleted: archive/ ($FILE_COUNT files removed)"
else
    echo "  (not found: archive/)"
fi

echo ""
echo "============================================================"
echo "  ✓ Log removal complete!"
echo "============================================================"
echo ""
echo "To start a fresh evolution session:"
echo "  python tools/generate_pair.py --init"
echo ""
