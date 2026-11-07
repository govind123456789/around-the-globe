"""Paths and YAML loaders shared by every pipeline stage."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = ROOT / "raw"            # cached source downloads (not committed)
BUILD = ROOT / "build"        # intermediate tables (not committed)
DIST = ROOT / "dist"          # the deployable static site
SITE = ROOT / "site"
CONTENT = ROOT / "content"

# Release label: the date the pipeline ran, overridable for reproducible rebuilds.
RELEASE = os.environ.get("RELEASE_DATE")


def load_yaml(name: str) -> dict:
    with open(DATA / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def site_config() -> dict:
    return load_yaml("site.yaml")
