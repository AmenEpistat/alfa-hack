"""Public API contract for backend integration."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .config import AppConfig, load_config
from .data import RankingInput, load_companies, load_ranking_input
from .pipeline import run as run_pipeline

log = logging.getLogger(__name__)


def validate_payload(payload: dict[str, Any]) -> list[str]:
    """Lightweight validation without heavy model calls."""
    warnings: list[str] = []
    try:
        parsed = RankingInput.model_validate(payload)
    except Exception as exc:  # pydantic.ValidationError
        return [f"payload validation failed: {exc}"]
    if not parsed.watchlist:
        warnings.append("watchlist is empty")
    if not parsed.topics.news:
        warnings.append("no news in payload")
    if not parsed.topics.pdf:
        warnings.append("no analytics in payload")
    return warnings


def health(config: str | Path | AppConfig = "config.yaml") -> dict[str, Any]:
    from . import __version__
    cfg = config if isinstance(config, AppConfig) else load_config(config)
    return {
        "status": "ok",
        "version": __version__,
        "schema_version": cfg.io.result_schema_version,
        "news_index": (cfg.paths.news_cache / "faiss.index").exists(),
        "analytics_index": (cfg.paths.analytics_cache / "faiss.index").exists(),
        "news_cache": (cfg.paths.news_cache / "emb.npy").exists(),
        "analytics_cache": (cfg.paths.analytics_cache / "emb.npy").exists(),
        "model_bi": cfg.embeddings.bi_encoder.model_name,
        "model_cross": cfg.embeddings.cross_encoder.model_name,
    }


def run_ranking(
    payload: dict[str, Any] | RankingInput | str | Path,
    companies: pd.DataFrame | str | Path,
    config: str | Path | AppConfig = "config.yaml",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Main entry point for backend. Returns versioned JSON contract."""
    cfg = config if isinstance(config, AppConfig) else load_config(config, overrides=overrides)
    parsed = load_ranking_input(payload)
    df = load_companies(companies)

    result = run_pipeline(parsed, df, cfg)

    return {
        "schema_version": cfg.io.result_schema_version,
        "run_id": result.run_id,
        "status": result.status,
        "sets": [
            {
                "set_id": s.set_id,
                "company": s.company,
                "news": s.news,
                "analytics": s.analytics,
                "set_score": s.set_score,
                "warnings": s.warnings,
            }
            for s in result.sets
        ],
        "diagnostics": result.diagnostics,
    }


def dump_result(result: dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")