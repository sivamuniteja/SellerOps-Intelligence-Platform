#!/usr/bin/env python3
"""CLI script to generate synthetic dataset for SellerOps Intelligence Platform."""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generate import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic marketplace dataset.")
    parser.add_argument(
        "--target",
        choices=["starter", "full"],
        default="full",
        help="Target dataset scale (starter: 10k orders, full: 100k orders). Default: full."
    )
    parser.add_argument("--db-path", type=str, default=None, help="Custom database output path.")
    parser.add_argument("--seed", type=int, default=20261022, help="Deterministic random seed.")

    args = parser.parse_args()
    run_pipeline(target_mode=args.target, db_path=args.db_path, seed=args.seed)


if __name__ == "__main__":
    main()
