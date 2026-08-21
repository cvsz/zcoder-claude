#!/usr/bin/env python3
"""
main.py — AI Model Coder CLI (entry-point stub)
AI Model Coder CLI v1.41.0

Delegates to interfaces/cli/parser.py and interfaces/cli/dispatcher.py.
Extracted 2026-08-21 (Phase E).
"""

from interfaces.cli.dispatcher import (
    VERSION, BANNER, AGENT_SYSTEM_PROMPTS,
    _api_key, _model, _read_file,
)
from interfaces.cli.parser import build_parser
from interfaces.cli.dispatcher import dispatch


def main():
    parser = build_parser()
    args = parser.parse_args()
    dispatch(args)


if __name__ == "__main__":
    main()
