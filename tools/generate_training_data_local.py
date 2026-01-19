#!/usr/bin/env python3
"""
Generate training data locally using deterministic prompt parsing.

This CLI is a thin wrapper around tools/training_data_generator.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from training_data_generator import generate_template_examples


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate training data locally (no API calls)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of examples to generate (default: 50)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Specific scenario to generate (default: all scenarios)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/training"),
        help="Output directory (default: data/training)",
    )

    args = parser.parse_args()

    try:
        generate_template_examples(
            count=args.count,
            output_dir=args.output_dir,
            scenario=args.scenario,
        )
    except Exception as exc:
        print(f"\n❌ Error: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
