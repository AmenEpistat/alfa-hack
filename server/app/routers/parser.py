from __future__ import annotations

import hashlib
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PARSER_ROOT = REPOSITORY_ROOT / "parser"
PARSER_SRC = PARSER_ROOT / "src"
PARSER_CACHE = REPOSITORY_ROOT / "cache"
PARSER_OUTPUT = REPOSITORY_ROOT / "output" / "parser-runs"

if str(PARSER_SRC) not in sys.path:
    sys.path.insert(0, str(PARSER_SRC))

from alpha_parser import ResearchModule
from alpha_parser.config import Settings
from alpha_parser.schemas import CompanyInput


router = APIRouter(
    prefix="/api/parser",
    tags=["parser"],
)


class ParserCollectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: dict[str, Any]
    topic: str = Field(
        default="События отрасли и конкурентов",
        min_length=2,
        max_length=500,
    )

    news_limit: int = Field(default=5, ge=0, le=20)
    competitor_limit: int = Field(default=5, ge=0, le=10)
    pdf_limit: int = Field(default=15, ge=0, le=100)

    discover_peers: bool = True
    cached_only: bool = False
    min_sources: int = Field(default=10, ge=10, le=100)

    target_audience: dict[str, Any] | None = None
    force_refresh: bool = False


class ParserPdfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    logical_id: str | None = None
    title: str | None = None
    published_at: str | None = None
    force: bool = False


def _settings() -> Settings:
    return Settings(_env_file=PARSER_ROOT / ".env")


def _module(run_id: str, force_refresh: bool = False) -> ResearchModule:
    run_dir = PARSER_OUTPUT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    module = ResearchModule(
        settings=_settings(),
        workspace=PARSER_ROOT,
        output_dir=run_dir,
        cache_dir=PARSER_CACHE,
        budget_scope="backend",
        tenant_scope="backend",
    )

    module.store.refresh_cache = force_refresh
    return module


def _validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    try:
        return CompanyInput.model_validate(profile).model_dump(mode="json")
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Некорректный профиль компании.",
                "errors": exc.errors(include_input=False),
            },
        ) from exc


@router.get("/health")
def health() -> dict[str, Any]:
    parser_src_exists = PARSER_SRC.is_dir()
    config_exists = (PARSER_ROOT / "config").is_dir()

    if not parser_src_exists:
        raise HTTPException(
            status_code=503,
            detail="Каталог parser/src не найден.",
        )

    return {
        "status": "ok",
        "parser": {
            "available": True,
            "src": str(PARSER_SRC),
            "config_available": config_exists,
            "cache_dir": str(PARSER_CACHE),
            "output_dir": str(PARSER_OUTPUT),
        },
    }


@router.post("/collect")
def collect(request: ParserCollectRequest) -> dict[str, Any]:
    """
    Запускает сбор внешних публикаций, PDF и новостей конкурентов
    через alpha_parser.ResearchModule.
    """

    profile = _validate_profile(request.profile)
    run_id = str(uuid.uuid4())

    try:
        module = _module(
            run_id=run_id,
            force_refresh=request.force_refresh,
        )

        result = module.collect_from_profile(
            profile,
            topic=request.topic,
            news_limit=request.news_limit,
            competitor_limit=request.competitor_limit,
            pdf_limit=request.pdf_limit,
            discover_peers=request.discover_peers,
            cached_only=request.cached_only,
            min_sources=request.min_sources,
            target_audience=request.target_audience,
        )

        return {
            "status": result.get("status", "partial"),
            "run_id": result.get("run_id", run_id),
            "company_id": profile["company_id"],
            "result": result,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Файл или каталог parser не найден: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка выполнения parser: {type(exc).__name__}: {exc}",
        ) from exc


@router.post("/pdf")
def parse_pdf(request: ParserPdfRequest) -> dict[str, Any]:
    """
    Обрабатывает PDF через parser.

    Путь должен быть доступен серверу. Для PDF из parser/inputs
    можно передавать относительный путь, например:
    inputs/analytics/report.pdf
    """

    requested_path = Path(request.path)

    if requested_path.is_absolute():
        pdf_path = requested_path.resolve()
    else:
        pdf_path = (PARSER_ROOT / requested_path).resolve()

    try:
        pdf_path.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="Путь к PDF должен находиться внутри репозитория.",
        ) from exc

    if not pdf_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"PDF не найден: {pdf_path}",
        )

    if pdf_path.suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=422,
            detail="Ожидается файл с расширением .pdf.",
        )

    run_id = str(uuid.uuid4())

    try:
        module = _module(run_id=run_id)

        result = module.ingest_pdf(
            pdf_path.relative_to(PARSER_ROOT),
            logical_id=request.logical_id,
            title=request.title,
            published_at=request.published_at,
            force=request.force,
        )

        return {
            "status": "completed",
            "run_id": run_id,
            "result": result,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка обработки PDF: {type(exc).__name__}: {exc}",
        ) from exc
