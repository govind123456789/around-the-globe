"""Run the whole pipeline: fetch (cached) → data release → website.

    python -m pipeline.build            # local build, warns on unchecked licences
    python -m pipeline.build --strict   # release build: unchecked licences fail
    python -m pipeline.build --refresh  # re-download sources first
    python -m pipeline.build --site-only  # re-render pages from the last data build
"""
from __future__ import annotations

import argparse
import pickle
import sys
import time

from . import build_data, build_site, fetch
from .config import BUILD


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--skip-fetch", action="store_true")
    ap.add_argument("--site-only", action="store_true", help="reuse the last data build (build/model.pkl)")
    args = ap.parse_args(argv)
    t0 = time.time()
    if args.site_only:
        print("== Site (reusing last data build)")
        with open(BUILD / "model.pkl", "rb") as f:
            build_site.build(pickle.load(f))
        return 0
    if not args.skip_fetch:
        print("== Fetch")
        fetch.main(["--refresh"] if args.refresh else [])
    print("== Data")
    try:
        model = build_data.build(strict=args.strict)
    except build_data.GateError as e:
        print(f"\nBUILD FAILED: {e}", file=sys.stderr)
        return 1
    with open(BUILD / "model.pkl", "wb") as f:
        pickle.dump(model, f)
    print("== Site")
    build_site.build(model)
    print(f"Done in {time.time() - t0:.0f}s. Preview: python -m http.server -d dist 8000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
