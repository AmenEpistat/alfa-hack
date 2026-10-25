"""Orchestrator: payload -> features -> embeddings/rank -> sets."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .config import AppConfig
from .data import RankingInput, extract_watchlist, normalize_ranking_input
from .sets import RankingSet, build_sets

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    run_id: str
    status: str
    sets: list[RankingSet]
    diagnostics: dict[str, Any] = field(default_factory=dict)


def run(
    payload: RankingInput,
    companies: pd.DataFrame,
    cfg: AppConfig,
) -> PipelineResult:
    run_id = payload.run_id or str(uuid.uuid4())
    t0 = time.time()
    timings: dict[str, float] = {}

    watchlist = extract_watchlist(payload, filter_enabled=cfg.hard_recall.primary.filter_enabled)
    payload = normalize_ranking_input(
        payload, drop_competitors_duplicates=cfg.io.drop_competitors_duplicates
    )

    t = time.time()
    sets = build_sets(payload, companies, watchlist, cfg)
    timings["build_sets"] = time.time() - t

    status = "ok" if sets else "partial"
    diagnostics = {
        "gaps": payload.gaps,
        "errors": payload.errors,
        "timings": timings,
        "counts": {
            "watchlist": len(watchlist),
            "news": len(payload.topics.news),
            "competitors": len(payload.topics.competitors),
            "analytics": len(payload.topics.pdf),
            "sets": len(sets),
        },
        "total_seconds": time.time() - t0,
    }
    if not watchlist:
        diagnostics.setdefault("warnings", []).append(
            "watchlist is empty: hard recall primary disabled"
        )
    return PipelineResult(run_id=run_id, status=status, sets=sets, diagnostics=diagnostics)
