"""
CLI interface module for AEGIS.
Handles command-line interface and user interactions.
"""

try:
    from .main import cli
    from .commands import (
        DiscoverCommand,
        QuestionnaireCommand,
        CatalogCommand,
        RecommendCommand,
    )
except ImportError:
    # Fallback for binary execution
    import sys
    import os

    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    try:
        from main import cli
        from commands import (
            DiscoverCommand,
            QuestionnaireCommand,
            CatalogCommand,
            RecommendCommand,
        )
    except ImportError:
        # Final fallback - define minimal exports
        cli = None
        DiscoverCommand = None
        QuestionnaireCommand = None
        CatalogCommand = None
        RecommendCommand = None

__all__ = [
    "cli",
    "DiscoverCommand",
    "QuestionnaireCommand",
    "CatalogCommand",
    "RecommendCommand",
]
