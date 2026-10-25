from __future__ import annotations

import copy
import sys
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PARSER_ROOT = REPOSITORY_ROOT / "parser"
PARSER_SRC = PARSER_ROOT / "src"
INSIGHT_OUTPUT_ROOT = REPOSITORY_ROOT / "output" / "insight-runs"
CACHE_ROOT = REPOSITORY_ROOT / "cache"

for path in (REPOSITORY_ROOT, PARSER_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from alpha_parser.config import Settings
from alpha_parser.module import ResearchModule
from insides import generate_insights, load_product_catalog, save_articles
from insides.client import JsonLLMClient


router = APIRouter(
    prefix="/api/insight-agent",
    tags=["insight-agent"],
)

AudienceType = Literal[
    "business_owner",
    "ceo",
    "cfo",
    "chief_accountant",
    "treasury_head",
    "c_level",
    "decision_maker",
]


class InsightGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ranking_input: dict[str, Any] = Field(
        description="JSON ranking_input от parser или ranking_module.",
    )

    audience_type: AudienceType = "decision_maker"

    min_insights: int = Field(
        default=5,
        ge=5,
        le=20,
    )

    max_repairs: int = Field(
        default=1,
        ge=0,
        le=1,
    )

    max_chars_per_packet: int = Field(
        default=14000,
        ge=1000,
        le=50000,
    )

    max_catalog_chars: int = Field(
        default=30000,
        ge=1000,
        le=100000,
    )

    force_refresh: bool = False


def _settings() -> Settings:
    return Settings(
        _env_file=PARSER_ROOT / ".env",
    )


def _build_module(run_id: str, force_refresh: bool) -> ResearchModule:
    output_dir = INSIGHT_OUTPUT_ROOT / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    module = ResearchModule(
        settings=_settings(),
        workspace=PARSER_ROOT,
        output_dir=output_dir,
        cache_dir=CACHE_ROOT,
        budget_scope="insights",
        tenant_scope="backend",
    )

    return module


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


@router.post("/generate")
def generate(request: InsightGenerationRequest) -> dict[str, Any]:
    """
    Генерирует инсайты по уже отранжированным материалам.
    """

    run_id = str(uuid.uuid4())
    module = _build_module(
        run_id=run_id,
        force_refresh=request.force_refresh,
    )

    output_dir = INSIGHT_OUTPUT_ROOT / run_id
    result_path = output_dir / "06_insights.json"
    articles_dir = output_dir / "insights"

    try:
        ranking_input = copy.deepcopy(request.ranking_input)

        if not ranking_input.get("company_input"):
            raise HTTPException(
                status_code=422,
                detail="ranking_input.company_input обязателен.",
            )

        if not isinstance(ranking_input.get("topics"), dict):
            raise HTTPException(
                status_code=422,
                detail="ranking_input.topics должен быть объектом.",
            )

        settings = _settings()
        client = JsonLLMClient(
            settings=settings,
            store=module.store,
            max_output_tokens=settings.llm_max_output_tokens,
        )

        def on_progress(progress: dict[str, Any]) -> None:
            _save_json(result_path, progress)

        result = generate_insights(
            ranking_input,
            client,
            audience_type=request.audience_type,
            product_catalog=load_product_catalog(),
            min_insights=request.min_insights,
            max_chars_per_packet=request.max_chars_per_packet,
            max_catalog_chars=request.max_catalog_chars,
            max_repairs=request.max_repairs,
            on_progress=on_progress,
        )

        _save_json(result_path, result)

        markdown_files = save_articles(
            result,
            directory=articles_dir,
            protected=(result_path,),
        )

        return {
            "status": result.get("status"),
            "run_id": result.get("run_id", run_id),
            "input_run_id": result.get("input_run_id"),
            "insights_count": len(result.get("insights", [])),
            "errors": result.get("errors", []),
            "usage": result.get("usage", {}),
            "artifacts": {
                "json": str(result_path.resolve()),
                "markdown": markdown_files,
            },
            "result": result,
        }

    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Файл конфигурации или каталога не найден: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(f"Ошибка генерации инсайтов: {type(exc).__name__}: {exc}"),
        ) from exc
    finally:
        module.store.save_corpus()


@router.get("/health")
def health() -> dict[str, Any]:
    settings = _settings()

    configured = bool(
        settings.llm_base_url and settings.llm_api_key and settings.llm_model
    )

    return {
        "status": "ok" if configured else "degraded",
        "agent": "insides",
        "llm_configured": configured,
        "output_dir": str(INSIGHT_OUTPUT_ROOT),
        "cache_dir": str(CACHE_ROOT),
    }
