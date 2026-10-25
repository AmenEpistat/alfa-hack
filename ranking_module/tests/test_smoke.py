"""Smoke test: run pipeline on fixture and validate output contract."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from alfa_insights.api import run_ranking, validate_payload
from alfa_insights.config import load_config
from alfa_insights.data import extract_watchlist, load_ranking_input

FIXTURES = Path(__file__).parent / "fixtures"
INPUT = FIXTURES / "ranking_input_full_example.json"
COMPANIES = FIXTURES / "companies.txt"


def test_extract_watchlist() -> None:
    payload = load_ranking_input(INPUT)
    wl = extract_watchlist(payload)
    assert len(wl) == 1
    assert wl[0].id == "watch-example"
    assert wl[0].enabled is True
    assert wl[0].domain == "robotics.example"
    assert wl[0].relationship == "industry_peer"
    assert wl[0].origin == "industry_agent"


def test_validate_payload() -> None:
    raw = json.loads(INPUT.read_text(encoding="utf-8"))
    warnings = validate_payload(raw)
    # no news/pdf missing in fixture
    assert warnings == []


def test_smoke_run(tmp_path: Path) -> None:
    cfg = load_config("config.yaml", overrides={
        "paths": {"cache_dir": str(tmp_path / "cache"),
                  "news_cache": str(tmp_path / "cache/news"),
                  "analytics_cache": str(tmp_path / "cache/analytics"),
                  "runs_dir": str(tmp_path / "runs")},
        "recall": {"top_k_dense": 4, "top_k_cross": 4},
        "sets": {"min_news": 1, "max_news": 3, "max_sets": 2},
    })
    df = pd.read_csv(COMPANIES, sep=",", on_bad_lines="skip") if COMPANIES.suffix == ".txt" else pd.read_csv(COMPANIES)
    result = run_ranking(INPUT, df, config=cfg)
    assert result["schema_version"] == "1.0"
    assert result["status"] in {"ok", "partial"}
    assert 0 <= len(result["sets"]) <= 2
    for s in result["sets"]:
        assert 1 <= len(s["news"]) <= 3