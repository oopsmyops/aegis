"""
CLI interface module for AEGIS.
Handles command-line interface and user interactions.
"""

from .main import main
from .commands import (
    DiscoverCommand,
    QuestionnaireCommand,
    CatalogCommand,
    RecommendCommand,
)

__all__ = [
    "main",
    "DiscoverCommand",
    "QuestionnaireCommand",
    "CatalogCommand",
    "RecommendCommand",
]
