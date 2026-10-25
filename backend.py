"""Backend entry point for preprocessing, collection and insight generation."""
from __future__ import annotations

import argparse
import copy
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import uuid
from zoneinfo import ZoneInfo

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "parser" / "src"))

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal
from alpha_parser import ResearchModule
from alpha_parser.cache import JsonCache, CacheBusyError, atomic_json, code_fingerprint, file_lock, fingerprint
from alpha_parser.config import Settings
from alpha_parser.pdf import parse_pdf
from alpha_parser.schemas import CompanyInput
from preprocessing import preprocess_csv
from preprocessing.pipeline import select_company
from insides import generate_insights, save_articles
from insides.client import JsonLLMClient
from insides.evidence import prepare_input
from insides.audiences import AudienceType, get_audience
from insides.products import load_product_catalog


class InferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["preprocess", "collect", "generate", "run"] = "collect"
    audience_type: AudienceType
    company_id: str | None = Field(None, min_length=1, max_length=100)
    topic: str = Field("События отрасли и конкурентов", min_length=2, max_length=500)
    preprocessing: dict | None = None
    profile: dict | None = None
    ranked_input: dict | None = None
    run_id: str | None = None
    offline: bool = False
    allow_pdf_processing: bool = False
    force_refresh: bool = False
    news_limit: int = Field(5, ge=5, le=30)
    competitor_limit: int = Field(5, ge=5, le=30)
    pdf_limit: int = Field(15, ge=5, le=100)
    min_insights: int = Field(5, ge=5)
    competitors: list[dict] | None = Field(None, max_length=30)


class InferenceService:
    """Configure trusted file paths, credentials and tenant outside request JSON."""

    def __init__(self, *, project_dir=PROJECT_DIR, cache_dir=None, output_dir=None,
                 csv_path=None, tenant_id="default", settings=None, ranker=None,
                 insight_client_factory=None):
        self.project_dir = Path(project_dir).resolve()
        self.workspace = self.project_dir / "parser"
        self.cache_dir = Path(cache_dir).resolve() if cache_dir is not None else self.project_dir / "cache"
        self.output_dir = Path(output_dir).resolve() if output_dir is not None else self.project_dir / "output" / "runs"
        self.csv_path = Path(csv_path).resolve() if csv_path is not None else self.project_dir / "inputs" / "csv" / "df_Uid_data_hack.csv"
        self.tenant_scope = hashlib.sha256(str(tenant_id).encode("utf-8")).hexdigest()[:24]
        self.settings = settings or Settings(_env_file=self.workspace / ".env")
        # API credentials never enter JSON, logs or cache filenames.
        self.budget_scope = fingerprint({"key_digest": hashlib.sha256(self.settings.llm_api_key.encode()).hexdigest()})
        self.cache = JsonCache(self.cache_dir)
        self.ranker = ranker
        self.insight_client_factory = insight_client_factory

    def _profile(self, request):
        if request.preprocessing is not None and request.profile is not None:
            raise ValueError("Provide either preprocessing or profile")
        if request.preprocessing is not None:
            payload = copy.deepcopy(request.preprocessing)
            if request.company_id is None:
                if len(payload.get("companies", [])) != 1:
                    raise ValueError("company_id is required to select a preprocessed company")
                company_id = payload["companies"][0]["company_id"]
            else:
                company_id = request.company_id
            profile = select_company(payload, company_id)
        elif request.profile is not None:
            profile = copy.deepcopy(request.profile)
            payload = {"schema_version": "1.0", "dataset_type": "company_profiles",
                       "source": {"type": "upstream_json"}, "companies": [profile]}
        elif request.action == "generate":
            profile = copy.deepcopy((request.ranked_input or {}).get("company_input", {}))
            payload = {"schema_version": "1.0", "dataset_type": "company_profiles",
                       "source": {"type": "ranked_input"}, "companies": [profile]}
        else:
            if request.company_id is None:
                raise ValueError("company_id or an upstream company profile is required")
            payload = preprocess_csv(self.csv_path, company_ids=[request.company_id],
                                     cache_dir=self.cache_dir / "private" / self.tenant_scope)
            profile = select_company(payload, request.company_id)
        profile = CompanyInput.model_validate(profile).model_dump(mode="json")
        if request.company_id is not None and profile["company_id"] != request.company_id:
            raise ValueError("company_id does not match the supplied profile")
        return payload, profile

    def _module(self, folder, refresh):
        module = ResearchModule(self.settings, workspace=self.workspace, output_dir=folder,
                                cache_dir=self.cache_dir, budget_scope=self.budget_scope,
                                tenant_scope=self.tenant_scope)
        module.store.refresh_cache = refresh
        return module

    def _pdfs(self, module, request):
        manifest = json.loads((module.settings.config_dir / "analytics_manifest.json").read_text(encoding="utf-8-sig"))
        gaps, hits, accepted = [], 0, set()
        for entry in manifest["documents"]:
            try:
                result = parse_pdf(module.store, module.settings,
                                   module.settings.input_dir / "analytics" / entry["file"],
                                   logical_id=entry["logical_id"], title=entry.get("title"),
                                   published_at=entry.get("published_at"),
                                   cached_only=not request.allow_pdf_processing or request.offline,
                                   force=request.force_refresh and request.allow_pdf_processing and not request.offline)
                if result["document"]["quality"] == "failed":
                    gaps.append("PDF extraction failed: " + entry["file"])
                else:
                    accepted.add(result["document"]["version_id"])
                hits += int(bool(result.get("cache", {}).get("hit") or result.get("skipped")))
            except (ValueError, FileNotFoundError):
                gaps.append("PDF is not available in the configured extraction cache: " + entry["file"])
        # Historical corpus entries must never bypass PDF content/config invalidation.
        for doc in module.store.documents():
            if doc["source_type"] == "alpha_pdf" and doc["version_id"] not in accepted:
                module.store.state["current_versions"].pop(doc["document_id"], None)
        module.store.flush()
        return {"files": len(manifest["documents"]), "reused": hits, "gaps": gaps}

    @staticmethod
    def _ranked(original, ranked):
        if ranked.get("target_audience") != original.get("target_audience"):
            raise ValueError("Ranker must preserve the target audience")
        if ranked.get("company_input") != original.get("company_input"):
            raise ValueError("Ranked JSON belongs to another company profile")
        available = {topic: {(row["version_id"], row["chunk_id"]): row for row in rows}
                     for topic, rows in original["topics"].items()}
        for topic, rows in ranked.get("topics", {}).items():
            if topic not in available:
                raise ValueError("Unknown ranked topic")
            for row in rows:
                source = available[topic].get((row["version_id"], row["chunk_id"]))
                if source is None or any(row.get(key) != value for key, value in source.items()):
                    raise ValueError("Ranker must preserve exact source text, identities and metadata")
        prepare_input(ranked)
        return ranked

    def _generate(self, module, ranked, request, folder):
        audience = get_audience(request.audience_type)
        product_catalog = load_product_catalog()
        normalized = prepare_input(ranked)
        normalized["target_audience"] = audience
        normalized["product_catalog_sha256"] = product_catalog["content_sha256"]
        normalized.pop("input_run_id", None)
        # Cache the actual model input, not per-request transport/cache diagnostics.
        normalized["company_analysis_context"].pop("preprocessing_metadata", None)
        normalized["company_analysis_context"].pop("generated_at", None)
        cache_key = {
            "tenant": self.tenant_scope, "input": normalized, "min_insights": request.min_insights,
            "date": datetime.now(ZoneInfo("Europe/Moscow")).date().isoformat(),
            "model": self.settings.llm_model, "provider": self.settings.llm_base_url,
            "thinking": [self.settings.llm_thinking_protocol, self.settings.llm_thinking_mode,
                         self.settings.llm_reasoning_effort, self.settings.llm_extra_body],
            "code": code_fingerprint((PROJECT_DIR / "insides").glob("*.py")),
        }

        def checkpoint(result):
            atomic_json(folder / "06_insights.json", result)
            save_articles(result, directory=folder / "insights",
                          protected=[folder / "05_ranked.json", folder / "06_insights.json"])
        with self.cache.lock("insights", cache_key):
            cached = None if request.force_refresh else self.cache.get("insights", cache_key, ttl=self.settings.insight_cache_ttl)
            if cached is not None:
                historical = copy.deepcopy(cached.get("usage", {}))
                cached["usage"] = {"calls": 0, "submitted_calls": 0, "input_tokens": 0, "output_tokens": 0,
                                   "cost_rub": 0, "cache_hit": True, "historical_usage": historical,
                                   "scope": "this request reused saved generation; no model call"}
                cached["recovery"] = {"type": "cache_reuse", "source_run_id": cached["run_id"],
                                      "current_input_run_id": ranked.get("run_id")}
                checkpoint(cached)
                return cached, True
            if request.offline:
                raise ValueError("No matching insight cache entry; offline mode cannot call a model")
            client = (self.insight_client_factory(module.settings, module.store) if self.insight_client_factory
                      else JsonLLMClient(module.settings, module.store))
            result = generate_insights(ranked, client, audience_type=request.audience_type, product_catalog=product_catalog,
                                       min_insights=request.min_insights, on_progress=checkpoint)
            if len(result["insights"]) >= request.min_insights and result["status"] in {"completed", "partial"}:
                self.cache.put("insights", cache_key, result, ttl=self.settings.insight_cache_ttl)
            return result, False

    def handle(self, payload):
        """Run a pipeline request and return a JSON-compatible dictionary."""
        run_id = folder = None
        try:
            request = InferenceRequest.model_validate(payload)
            if request.offline and request.allow_pdf_processing:
                raise ValueError("offline mode cannot extract PDFs")
            if request.action == "generate" and request.ranked_input is None:
                raise ValueError("generate requires ranked_input from the ranking stage")
            if request.run_id and request.action != "generate":
                raise ValueError("run_id is only used to append generation to an existing collection")

            preprocessing, profile = self._profile(request)
            audience = get_audience(request.audience_type)
            run_id = str(uuid.UUID(request.run_id)) if request.run_id else str(uuid.uuid4())
            folder = self.output_dir / self.tenant_scope / run_id
            with file_lock(folder / ".inference.lock"):
                if request.run_id:
                    meta = json.loads((folder / "00_request.json").read_text(encoding="utf-8"))
                    if meta.get("tenant") != self.tenant_scope or meta.get("company_id") != profile["company_id"]:
                        raise ValueError("Run does not belong to this tenant/company")
                    original = json.loads((folder / "04_ranker_input.json").read_text(encoding="utf-8"))
                    self._ranked(original, request.ranked_input)
                else:
                    atomic_json(folder / "00_request.json", {
                        "run_id": run_id, "tenant": self.tenant_scope,
                        "company_id": profile["company_id"], "action": request.action,
                        "offline": request.offline, "target_audience": audience,
                    })
                    atomic_json(folder / "01_preprocessing.json", preprocessing)

                response = {
                    "status": "completed", "run_id": run_id, "stage": "preprocessing",
                    "company_id": profile["company_id"], "target_audience": audience,
                    "preprocessing": preprocessing,
                    "cache": {"csv": preprocessing.get("preprocessing", {}).get("cache")},
                    "artifacts": {},
                }
                if request.action != "preprocess":
                    self._process(request, profile, preprocessing, audience, folder, response)
                response["artifacts"] = {p.name: str(p.resolve()) for p in folder.glob("*.json")}
                if (folder / "insights").exists():
                    response["artifacts"]["markdown"] = [
                        str(p.resolve()) for p in sorted((folder / "insights").glob("*.md"))
                    ]
                return response
        except Exception as error:
            detail = self._error(error)
            if folder is not None:
                detail["output_dir"] = str(folder)
            return {"status": "failed", "run_id": run_id, "error": detail}

    def _process(self, request, profile, preprocessing, audience, folder, response):
        module = self._module(folder, request.force_refresh)
        module.store.state["company_profiles"][profile["company_id"]] = profile
        try:
            if request.action == "generate":
                ranked = copy.deepcopy(request.ranked_input)
                if ranked.get("target_audience") not in (None, audience):
                    raise ValueError("Ranked input targets a different reader audience")
                if ranked.get("company_input") != profile:
                    raise ValueError("Ranked input must preserve the complete company profile")
                ranked["target_audience"] = audience
            else:
                result, pdf_cache = self._collect(module, request, profile, preprocessing, audience)
                response["cache"]["pdf"] = pdf_cache
                response.update(status=result["status"], stage="collection",
                                parser=result, ranking_input=result["ranking_input"])
                ranked = None
                if request.action == "run":
                    if request.ranked_input is not None:
                        ranked = self._ranked(result["ranking_input"], request.ranked_input)
                    elif self.ranker is not None and not request.offline:
                        ranked = self._ranked(
                            result["ranking_input"], self.ranker(copy.deepcopy(result["ranking_input"]))
                        )
                    else:
                        response.update(
                            stage="awaiting_ranking",
                            next_action="Rank ranking_input, then call generate with ranked_input and run_id",
                        )
            if ranked is not None:
                atomic_json(folder / "05_ranked.json", ranked)
                insights, hit = self._generate(module, ranked, request, folder)
                response.update(status=insights["status"], stage="insights", insights=insights)
                response["cache"]["insights"] = {"hit": hit}
            response["cache"]["shared"] = copy.deepcopy(module.store.cache.stats)
        finally:
            module.store.save_corpus()

    def _collect(self, module, request, profile, preprocessing, audience):
        module.store.load_corpus()
        if not request.offline:
            now = datetime.now(timezone.utc).timestamp()
            for document in module.store.documents():
                if document["source_type"] != "external":
                    continue
                try:
                    fetched = datetime.fromisoformat(document["fetched_at"].replace("Z", "+00:00")).timestamp()
                except (ValueError, TypeError, KeyError):
                    fetched = 0
                if request.force_refresh or now - fetched >= self.settings.article_cache_ttl:
                    module.store.state["current_versions"].pop(document["document_id"], None)

        pdf_cache = self._pdfs(module, request)
        if request.competitors is not None:
            owner = profile["company_id"]
            for watch in module.store.watches(owner):
                module.store.watch_update(owner, watch["id"], None)
            # Remember an empty selection so automatic discovery doesn't overwrite it.

            def mark_custom(record):
                return {**record, "initialized": True, "catalog_version": "user_defined"}
            module.store._edit_watches(owner, mark_custom)
            for company in request.competitors:
                module.add_competitor(owner, company)

        result = module.collect_from_profile(
            profile, topic=request.topic, target_audience=audience, cached_only=request.offline,
            news_limit=request.news_limit, competitor_limit=request.competitor_limit,
            pdf_limit=request.pdf_limit, discover_peers=not request.offline,
        )
        if pdf_cache["gaps"]:
            result["gaps"] = list(dict.fromkeys([*result["gaps"], *pdf_cache["gaps"]]))
            result["status"] = "partial"
        result["preprocessing_input"] = {
            key: preprocessing.get(key) for key in ("schema_version", "source", "preprocessing")
        }
        module.store.run_put({key: value for key, value in result.items() if key != "ranking_input"})
        result["ranking_input"] = module.get_ranking_input(result["run_id"])
        atomic_json(module.store.root / "04_ranker_input.json", result["ranking_input"])
        return result, pdf_cache

    @staticmethod
    def _error(error):
        from alpha_parser.llm import ProviderError
        if isinstance(error, ProviderError):
            return error.as_dict()
        if isinstance(error, ValidationError):
            return {
                "category": "invalid_input", "message": "JSON schema validation failed",
                "fields": [{"path": ".".join(map(str, e["loc"])), "type": e["type"]}
                           for e in error.errors(include_input=False)[:12]],
            }
        if isinstance(error, (ValueError, FileNotFoundError, CacheBusyError)):
            return {"category": "busy" if isinstance(error, CacheBusyError) else "invalid_input_or_cache_miss",
                    "message": str(error)[:1500]}
        return {"category": type(error).__name__, "message": "Inference failed; saved stage files are retained"}


_default = None


def handle_request(request):
    """Convenient entry point; reuse an explicit InferenceService for custom paths/tenants."""
    global _default
    if _default is None:
        _default = InferenceService()
    return _default.handle(request)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, help="UTF-8 request JSON; stdin when omitted")
    parser.add_argument("--response", type=Path, help="Optional JSON response file")
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--csv-path", type=Path)
    parser.add_argument("--tenant-id", default="default")
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text(encoding="utf-8-sig") if args.request else sys.stdin.read())
        service = InferenceService(cache_dir=args.cache_dir, output_dir=args.output_dir,
                                   csv_path=args.csv_path, tenant_id=args.tenant_id)
        # Extraction libraries may print diagnostics; stdout remains a JSON protocol.
        with redirect_stdout(sys.stderr):
            result = service.handle(request)
    except (ValueError, OSError) as error:
        result = {"status": "failed", "run_id": None,
                  "error": {"category": "invalid_request_or_configuration", "message": str(error)[:1500]}}
    if args.response:
        atomic_json(args.response, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
