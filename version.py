"""
version.py — single source of truth for the zcoder application version.

Lives outside interfaces/ so every front end (CLI dispatcher/parser, TUI,
webapp FastAPI) reads the same string without importing presentation-layer
code from each other. Extracted 2026-08-22 from interfaces/cli/dispatcher.py.
"""

VERSION = "1.43.0"
