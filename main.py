#!/usr/bin/env python3
"""
main.py — AI Model Coder CLI (entry-point stub)
AI Model Coder CLI v1.44.0

Delegates to interfaces/cli/parser.py and interfaces/cli/dispatcher.py.
Extracted 2026-08-21 (Phase E).
"""

from interfaces.cli.dispatcher import dispatch
from interfaces.cli.parser import build_parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    dispatch(args)


if __name__ == "__main__":
    main()
