from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
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


def _persist_run(
    run_dir: Path,
    payload: RankingInput,
    result: PipelineResult,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "input.json").write_text(
        payload.model_dump_json(indent=2), encoding="utf-8"
    )
    (run_dir / "result.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
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
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def run(
    payload: RankingInput,
    companies: pd.DataFrame,
    cfg: AppConfig,
    persist_artifacts: bool = True,
) -> PipelineResult:
    run_id = payload.run_id or str(uuid.uuid4())
    t0 = time.time()
    timings: dict[str, float] = {}

    watchlist = extract_watchlist(payload, filter_enabled=cfg.hard_recall.primary.filter_enabled)
    payload = normalize_ranking_input(payload, drop_competitors_duplicates=cfg.io.drop_competitors_duplicates)

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

    result = PipelineResult(run_id=run_id, status=status, sets=sets, diagnostics=diagnostics)

    if persist_artifacts:
        try:
            _persist_run(cfg.paths.runs_dir / run_id, payload, result)
            log.info("artifacts saved to %s", cfg.paths.runs_dir / run_id)
        except Exception:  # noqa: BLE001 — не роняем пайплайн из-за I/O
            log.exception("failed to persist run artifacts")

    return result