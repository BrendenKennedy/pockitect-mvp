#!/usr/bin/env python3
"""
Generate ambiguous/vague training data for Pockitect.

This CLI is a thin wrapper around tools/training_data_generator.py.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from training_data_generator import generate_vague_examples


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate vague training data for Pockitect.")
    parser.add_argument("--count", type=int, default=50, help="Number of examples to generate")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/training"),
        help="Output directory (default: data/training)",
    )
    parser.add_argument(
        "--tool-simulation-ratio",
        type=float,
        default=0.2,
        help="Fraction of prompts with tool simulation annotations",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for repeatable output",
    )

    args = parser.parse_args()
    created = generate_vague_examples(
        count=args.count,
        output_dir=args.output_dir,
        tool_simulation_ratio=args.tool_simulation_ratio,
        seed=args.seed,
    )
    print(f"✅ Generated {created} vague training examples in {args.output_dir}")


if __name__ == "__main__":
    main()
