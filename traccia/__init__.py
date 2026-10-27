"""Tracciabilità dei materiali da carpenteria metallica, dai documenti alla tabella con le prove."""

import tomllib
from pathlib import Path

VERSIONE_APP = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8"))[
    "project"
]["version"]
