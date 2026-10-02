"""Run every registered metric over a snapshot and write dashboard JSON.

    python scripts/compute_metrics.py                 # all metrics
    python scripts/compute_metrics.py --only overtime # a single metric
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metrics.export import write_all  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "dashboard" / "public" / "metrics")
    parser.add_argument("--only", action="append", metavar="KEY", help="metric key to compute (repeatable)")
    args = parser.parse_args(argv)

    for path in write_all(args.data_dir, args.out_dir, args.only):
        print(f"wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
