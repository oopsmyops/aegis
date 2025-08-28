#!/usr/bin/env python3
"""
AEGIS CLI Tool Entry Point
AI Enabled Governance Insights & Suggestions for Kubernetes
"""

import sys
import os

# Add the current directory to Python path so we can import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Also add parent directory for aegis.* imports
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from cli.main import cli
except ImportError:
    try:
        from aegis.cli.main import cli
    except ImportError:
        # Final fallback - try to import from current directory
        sys.path.insert(0, os.path.join(current_dir, "cli"))
        from main import cli

if __name__ == "__main__":
    cli()
