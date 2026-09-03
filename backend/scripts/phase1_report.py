"""Throwaway Phase 1 report — prints the seed batch summary + oracle-vs-baseline check.

    cd backend && python scripts/phase1_report.py [--seed 7]

No DB required (regenerates the batch in memory).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analysis import format_report, summarize  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    s = summarize(args.seed)
    print(format_report(s))
    return 0 if s["oracle"]["rate"] - s["baseline"]["rate"] > 0.10 else 1


if __name__ == "__main__":
    raise SystemExit(main())
