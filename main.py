#!/usr/bin/env python3
"""
AEGIS CLI Tool Entry Point
AI Enabled Governance Insights & Suggestions for Kubernetes
"""

import sys
import os

# Add the current directory to Python path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli import main

if __name__ == "__main__":
    sys.exit(main())