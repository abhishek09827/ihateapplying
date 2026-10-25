#!/usr/bin/env python3
"""
Autonomous AI Outreach Engine - Setup & Configuration CLI
Run: python setup.py
"""

import sys
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.setup_wizard import main, print_status_summary

if __name__ == "__main__":
    if "--status" in sys.argv or "--verify" in sys.argv or "--check" in sys.argv:
        print_status_summary()
    else:
        main()
