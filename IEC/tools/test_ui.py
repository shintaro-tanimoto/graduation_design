#!/usr/bin/env python3
"""
Test script to demonstrate terminal UI display functionality
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from iec_terminal_ui import display_pair

# Display current pair
print("\nDisplaying current generation information:")
meta_A, meta_B = display_pair()

if meta_A and meta_B:
    print("\n✓ Display test successful!")
    print(f"\nTo run full interactive session:")
    print(f"  python iec_terminal_ui.py")
else:
    print("\n✗ No generation found")
