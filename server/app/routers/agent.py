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
import json
from insides.evidence import parse_model_json
from pipeline_adapter import ranked_for_insights
from insides.audiences import get_audience


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
    ranking_result: dict[str, Any] | None = Field(
        default=None, description="Результат run_ranking с sets[]; исходный ranking_input нужен для цитат.",
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


def _build_module(
    run_id: str,
    force_refresh: bool = False,
) -> ResearchModule:
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
    module.store.refresh_cache = force_refresh
    return module


def _save_json(path: Path, payload: dict[str, Any]) -> None:
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


def _chat_context(insight: dict[str, Any]) -> dict[str, Any]:
    foundation = insight.get("foundation") or {}
    documents = []

    for document in foundation.get("documents") or []:
        documents.append(
            {
                "document_id": document.get("document_id"),
                "title": document.get("title"),
                "source_type": document.get("source_type"),
                "topics": document.get("topics") or [],
                "published_at": document.get("published_at"),
                "url": document.get("url"),
                "citations": document.get("citations") or [],
            }
        )

    return {
        "insight_id": insight.get("insight_id"),
        "title": insight.get("title"),
        "lead": insight.get("lead"),
        "what_happened": insight.get("what_happened"),
        "why_important_for_company": insight.get(
            "why_important_for_company",
            [],
        ),
        "possible_consequences": insight.get(
            "possible_consequences",
            [],
        ),
        "relevant_actions": insight.get(
            "relevant_actions",
            [],
        ),
        "bank_assessment": insight.get("bank_assessment"),
        "target_audience": insight.get("target_audience"),
        "company_input": insight.get("company_input"),
        "warnings": insight.get("warnings") or [],
        "documents": documents,
        "markdown": insight.get("markdown", ""),
    }


def _build_chat_messages(
    request: InsightChatRequest,
    context: dict[str, Any],
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "Ты отвечаешь на уточняющие вопросы пользователя "
                "по конкретному бизнес-инсайту. "
                "Отвечай только на основании переданного контекста. "
                "Не выдумывай факты, цифры, даты, источники, банковские "
                "продукты или условия. "
                "Если в контексте нет ответа, прямо скажи, что данных "
                "недостаточно. "
                "Отвечай на русском языке. "
                "Верни только валидный JSON следующего формата:\n"
                "{\n"
                '  "paragraphs": ["абзац 1", "абзац 2"],\n'
                '  "context": "краткое описание использованных данных",\n'
                '  "references": ["document_id"],\n'
                '  "citations": {"0": ["document_id"]},\n'
                '  "suggested_view": null\n'
                "}\n"
                "Поле paragraphs должно содержать от одного до четырёх "
                "непустых абзацев. "
                "В references указывай только document_id из контекста. "
                "В citations ключ — номер абзаца, начиная с нуля."
            ),
        },
    ]

    for item in request.history[-10:]:
        messages.append(
            {
                "role": item.role,
                "content": item.content,
            }
        )

    messages.append(
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": request.question,
                    "audience_type": request.audience_type,
                    "insight": context,
                },
                ensure_ascii=False,
            ),
        }
    )

    return messages


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
        if request.ranking_result is not None:
            ranking_input = ranked_for_insights(ranking_input, request.ranking_result)
            if not ranking_input["ranking_sets"]:
                raise ValueError("Ranker returned no supported sets")
        audience = get_audience(request.audience_type)
        if ranking_input.get("target_audience") and ranking_input["target_audience"].get("type") != request.audience_type:
            raise ValueError("ranking_input targets another reader role")
        ranking_input["target_audience"] = audience
        _save_json(output_dir / "05_ranked.json", ranking_input)

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


class InsightChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class InsightChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)

    insight: dict[str, Any] = Field(
        description="Сгенерированный объект инсайта из результата insides.",
    )

    history: list[InsightChatMessage] = Field(
        default_factory=list,
        max_length=20,
    )

    audience_type: AudienceType = "decision_maker"


class InsightChatResponse(BaseModel):
    question: str
    paragraphs: list[str]
    context: str
    references: list[str]
    citations: dict[int, list[str]] = Field(default_factory=dict)
    suggested_view: dict[str, Any] | None = None


@router.post(
    "/chat",
    response_model=InsightChatResponse,
)
def chat(request: InsightChatRequest) -> InsightChatResponse:
    run_id = str(uuid.uuid4())
    module = _build_module(run_id=run_id)
    context = _chat_context(request.insight)

    try:
        settings = _settings()

        client = JsonLLMClient(
            settings=settings,
            store=module.store,
            max_output_tokens=settings.llm_max_output_tokens,
        )

        raw_response = client.complete(
            _build_chat_messages(
                request=request,
                context=context,
            )
        )

        payload = parse_model_json(raw_response)

        paragraphs = payload.get("paragraphs")

        if not isinstance(paragraphs, list):
            raise ValueError(
                "Ответ LLM должен содержать массив paragraphs.",
            )

        paragraphs = [
            str(paragraph).strip() for paragraph in paragraphs if str(paragraph).strip()
        ][:4]

        if not paragraphs:
            raise ValueError(
                "LLM вернула пустой ответ.",
            )

        allowed_references = {
            document.get("document_id")
            for document in context["documents"]
            if document.get("document_id")
        }

        references = [
            str(reference)
            for reference in payload.get("references", [])
            if str(reference) in allowed_references
        ]

        citations: dict[int, list[str]] = {}
        raw_citations = payload.get("citations") or {}

        if isinstance(raw_citations, dict):
            for raw_index, raw_values in raw_citations.items():
                try:
                    index = int(raw_index)
                except (TypeError, ValueError):
                    continue

                if index < 0 or index >= len(paragraphs):
                    continue

                if not isinstance(raw_values, list):
                    continue

                values = [
                    str(value)
                    for value in raw_values
                    if str(value) in allowed_references
                ]

                if values:
                    citations[index] = list(dict.fromkeys(values))

        references = list(
            dict.fromkeys(
                [
                    *references,
                    *[
                        reference
                        for values in citations.values()
                        for reference in values
                    ],
                ]
            )
        )

        suggested_view = payload.get("suggested_view")

        if not isinstance(suggested_view, dict):
            suggested_view = None

        return InsightChatResponse(
            question=request.question,
            paragraphs=paragraphs,
            context=str(
                payload.get(
                    "context",
                    "Ответ сформирован по материалам выбранного инсайта.",
                )
            ),
            references=references,
            citations=citations,
            suggested_view=suggested_view,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Ошибка обработки вопроса агентом инсайтов: "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc
    finally:
        module.store.save_corpus()
