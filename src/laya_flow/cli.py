"""Command-line entry point for the standalone flow."""

from __future__ import annotations

import argparse
import json
import sys

from .laya import FixtureLayaClient
from .pipeline import build_real_laya_pipeline, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run rules -> Laya typed decision -> policy merge")
    parser.add_argument("question", nargs="?", help="Question to classify")
    parser.add_argument("--backend", choices=("fixture", "laya"), default="fixture")
    parser.add_argument("--threshold", type=float, default=0.6)
    parser.add_argument("--timeout", type=float, default=1.5)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    question = args.question
    if question is None:
        question = input("question> ").strip()
    backend = FixtureLayaClient() if args.backend == "fixture" else build_real_laya_pipeline()
    result = run_pipeline(
        question,
        backend=backend,
        threshold=args.threshold,
        timeout_seconds=args.timeout,
    )
    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent, sort_keys=bool(indent)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
