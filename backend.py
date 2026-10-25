"""In-process parser -> ranker -> insight agent entry point."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Literal
import uuid

PROJECT_DIR = Path(__file__).resolve().parent
for path in (PROJECT_DIR, PROJECT_DIR / "parser" / "src", PROJECT_DIR / "ranking_module" / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from alpha_parser import ResearchModule
from alpha_parser.cache import JsonCache, atomic_json, code_fingerprint, file_lock, fingerprint
from alpha_parser.config import Settings
from alpha_parser.pdf import parse_pdf
from alpha_parser.schemas import CompanyInput
from insides import generate_insights, save_articles
from insides.audiences import AudienceType, get_audience
from insides.client import JsonLLMClient
from insides.evidence import prepare_input
from insides.products import load_product_catalog
from pipeline_adapter import ranked_for_insights
from preprocessing import preprocess_csv
from preprocessing.pipeline import select_company


class InferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["collect", "rank", "generate", "run"] = "run"
    audience_type: AudienceType
    company_id: str | None = None
    profile: dict | None = None
    preprocessing: dict | None = None
    ranking_input: dict | None = Field(None, validation_alias=AliasChoices("ranking_input", "ranked_input"))
    ranking_result: dict | None = None
    topic: str = Field("События отрасли и конкурентов", min_length=2, max_length=500)
    news_limit: int = Field(10, ge=5, le=20)
    competitor_limit: int = Field(6, ge=5, le=10)
    pdf_limit: int = Field(15, ge=5, le=100)
    min_insights: int = Field(5, ge=5, le=20)
    max_repairs: int = Field(1, ge=0, le=1)
    max_chars_per_packet: int = Field(14000, ge=1000, le=50000)
    max_catalog_chars: int = Field(30000, ge=1000, le=100000)
    cached_only: bool = False
    allow_pdf_processing: bool = False
    force_refresh: bool = False


class InferenceService:
    def __init__(self, *, project_dir=PROJECT_DIR, cache_dir=None, output_dir=None,
                 csv_path=None, tenant_id="default", settings=None, companies=None,
                 ranker=None, insight_client_factory=None):
        self.project_dir = Path(project_dir).resolve()
        self.workspace = self.project_dir / "parser"
        self.cache_dir = Path(cache_dir or self.project_dir / "cache").resolve()
        self.output_dir = Path(output_dir or self.project_dir / "output" / "runs").resolve()
        self.csv_path = Path(csv_path or self.project_dir / "inputs" / "csv" / "df_Uid_data_hack.csv").resolve()
        self.settings = settings or Settings(_env_file=self.workspace / ".env")
        self.tenant_scope = hashlib.sha256(str(tenant_id).encode()).hexdigest()[:24]
        self.budget_scope = fingerprint({"key_digest": hashlib.sha256(self.settings.llm_api_key.encode()).hexdigest()})
        self.cache = JsonCache(self.cache_dir)
        self.companies, self.ranker = companies, ranker
        self.insight_client_factory = insight_client_factory

    def _profile(self, request):
        preprocessing = request.preprocessing
        if request.profile is not None and preprocessing is not None:
            raise ValueError("Provide either profile or preprocessing")
        if request.ranking_input is not None:
            profile = request.ranking_input.get("company_input")
            if request.profile is not None and request.profile != profile:
                raise ValueError("profile differs from ranking_input.company_input")
        elif request.profile is not None:
            profile = request.profile
        else:
            if request.company_id is None:
                if preprocessing is not None and len(preprocessing.get("companies", [])) == 1:
                    request = request.model_copy(update={"company_id": preprocessing["companies"][0]["company_id"]})
                else:
                    raise ValueError("company_id, profile or ranking_input is required")
            preprocessing = preprocessing or preprocess_csv(
                self.csv_path, company_ids=[request.company_id],
                cache_dir=self.cache_dir / "private" / self.tenant_scope)
            profile = select_company(preprocessing, request.company_id)
        profile = CompanyInput.model_validate(profile).model_dump(mode="json")
        if request.company_id is not None and profile["company_id"] != request.company_id:
            raise ValueError("company_id differs from the supplied company profile")
        return profile, preprocessing or {"schema_version": "1.0", "companies": [profile]}

    def _collect(self, module, request, profile, audience):
        module.store.load_corpus()
        manifest = module.settings.config_dir / "analytics_manifest.json"
        pdf_gaps = []
        if manifest.exists():
            accepted = set()
            for entry in json.loads(manifest.read_text(encoding="utf-8-sig"))["documents"]:
                try:
                    parsed = parse_pdf(
                        module.store, module.settings, module.settings.input_dir / "analytics" / entry["file"],
                        logical_id=entry["logical_id"], title=entry.get("title"), published_at=entry.get("published_at"),
                        cached_only=request.cached_only or not request.allow_pdf_processing,
                        force=request.force_refresh and request.allow_pdf_processing and not request.cached_only)
                    if parsed["document"]["quality"] != "failed":
                        accepted.add(parsed["document"]["version_id"])
                except (FileNotFoundError, ValueError):
                    pdf_gaps.append("PDF is not available in the extraction cache: " + entry["file"])
            for document in module.store.documents():
                if document["source_type"] == "alpha_pdf" and document["version_id"] not in accepted:
                    module.store.state["current_versions"].pop(document["document_id"], None)
        result = module.collect_from_profile(
            profile, target_audience=audience, topic=request.topic,
            news_limit=request.news_limit, competitor_limit=request.competitor_limit, pdf_limit=request.pdf_limit,
            cached_only=request.cached_only, discover_peers=not request.cached_only)
        source = result.get("ranking_input") or module.get_ranking_input(result["run_id"])
        if pdf_gaps:
            result["status"] = source["status"] = "partial"
            result.setdefault("gaps", []).extend(pdf_gaps)
            source.setdefault("gaps", []).extend(pdf_gaps)
        return result, source

    def _rank(self, source, preprocessing, folder):
        if self.ranker is not None:
            return self.ranker(copy.deepcopy(source), self.companies)
        from alfa_insights.api import run_ranking
        import pandas as pd

        companies = self.companies
        if isinstance(companies, list):
            companies = pd.DataFrame(companies)
        if companies is None:
            # Use the same cleaned IDs/features as the parser, rather than rereading raw CSV in the ranker.
            dataset = preprocessing if len(preprocessing.get("companies", [])) > 1 else preprocess_csv(
                self.csv_path, cache_dir=self.cache_dir / "private" / self.tenant_scope)
            companies = pd.DataFrame([
                {**company.get("attributes", {}),
                 **{key: value for key, value in company.get("features", {}).items() if key != "okved_sector"},
                 "SYNTHETIC_U": company["company_id"], "MAINOKVED_CODE": company.get("okved_code"),
                 "MAINOKVED_NAME": company.get("industry"), "REGION": company.get("region"),
                 "CITY": company.get("city"), "GROUP_ID": company.get("group_id")}
                for company in dataset["companies"]])
        return run_ranking(source, companies, config=self.project_dir / "ranking_module" / "config.yaml",
                           overrides={"paths": {"root": str(self.project_dir / "ranking_module"),
                                                "runs_dir": str(folder / "ranking")}})

    def _generate(self, ranked, module, request, folder):
        catalog = load_product_catalog()
        key = {"tenant": self.tenant_scope, "input": ranked, "min_insights": request.min_insights,
               "max_chars_per_packet": request.max_chars_per_packet, "max_catalog_chars": request.max_catalog_chars,
               "max_repairs": request.max_repairs, "catalog": catalog["content_sha256"],
               "model": self.settings.llm_model, "endpoint": self.settings.llm_base_url,
               "thinking": [self.settings.llm_thinking_protocol, self.settings.llm_thinking_mode,
                            self.settings.llm_reasoning_effort, self.settings.llm_extra_body],
               "code": code_fingerprint((self.project_dir / "insides").glob("*.py"))}

        def checkpoint(result):
            atomic_json(folder / "06_insights.json", result)
            save_articles(result, directory=folder / "insights")

        with self.cache.lock("pipeline_insights", key):
            result = None if request.force_refresh else self.cache.get("pipeline_insights", key, ttl=self.settings.insight_cache_ttl)
            if result is None:
                client = (self.insight_client_factory(module.settings, module.store) if self.insight_client_factory
                          else JsonLLMClient(module.settings, module.store))
                result = generate_insights(ranked, client, audience_type=request.audience_type,
                                           product_catalog=catalog, min_insights=request.min_insights,
                                           max_chars_per_packet=request.max_chars_per_packet,
                                           max_catalog_chars=request.max_catalog_chars,
                                           max_repairs=request.max_repairs, on_progress=checkpoint)
                if result.get("status") == "completed":
                    self.cache.put("pipeline_insights", key, result, ttl=self.settings.insight_cache_ttl)
            else:
                result["usage"] = {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                                   "cost_rub": 0, "cache_hit": True, "historical_usage": result.get("usage", {})}
            checkpoint(result)
            return result

    def handle(self, payload):
        run_id, module, response = str(uuid.uuid4()), None, {}
        try:
            request = InferenceRequest.model_validate(payload)
            profile, preprocessing = self._profile(request)
            audience = get_audience(request.audience_type)
            folder = self.output_dir / self.tenant_scope / run_id
            with file_lock(folder / ".pipeline.lock"):
                atomic_json(folder / "00_request.json", {"run_id": run_id, "company_id": profile["company_id"],
                                                         "action": request.action, "target_audience": audience})
                atomic_json(folder / "01_preprocessing.json", preprocessing)
                module = ResearchModule(self.settings, workspace=self.workspace, output_dir=folder,
                                        cache_dir=self.cache_dir, tenant_scope=self.tenant_scope, budget_scope=self.budget_scope)
                module.store.refresh_cache = request.force_refresh
                response = {"run_id": run_id, "company_id": profile["company_id"], "status": "completed", "stage": "collection"}
                if request.ranking_input is not None:
                    source = copy.deepcopy(request.ranking_input)
                else:
                    if request.action in {"rank", "generate"}:
                        raise ValueError("rank/generate requires ranking_input from the parser")
                    parser_result, source = self._collect(module, request, profile, audience)
                    response["parser"] = parser_result
                    atomic_json(folder / "03_parser.json", parser_result)
                source.setdefault("company_input", profile)
                if source.get("target_audience") and source["target_audience"].get("type") != request.audience_type:
                    raise ValueError("ranking_input targets another reader role")
                source["target_audience"] = audience
                prepare_input(source)
                atomic_json(folder / "04_ranker_input.json", source)
                response.update(status=source.get("status", "partial"), ranking_input=source)
                if request.action != "collect":
                    response["stage"] = "ranking"
                    ranking_result = request.ranking_result
                    if ranking_result is None:
                        if request.action == "generate":
                            # Retain the old direct parser-JSON generation interface.
                            ranked = source
                        else:
                            ranking_result = self._rank(source, preprocessing, folder)
                    if ranking_result is not None:
                        atomic_json(folder / "05_ranking.json", ranking_result)
                        response["ranking_result"] = ranking_result
                        ranked = ranked_for_insights(source, ranking_result)
                    atomic_json(folder / "05_ranked.json", ranked)
                    response["ranked_input"] = ranked
                    if request.action != "rank" and (ranking_result is None or ranked.get("ranking_sets")):
                        response["stage"] = "insights"
                        response["insights"] = self._generate(ranked, module, request, folder)
                        response["status"] = response["insights"]["status"]
                        if source.get("status") != "completed" and response["status"] == "completed":
                            response["status"] = "partial"
                    elif not ranked.get("ranking_sets"):
                        response.update(status="partial", stop_reason="Ranker returned no supported sets; generation skipped")
                    else:
                        response["status"] = ranked["status"]
                response["artifacts"] = {path.name: str(path) for path in folder.glob("*.json")}
                response["artifacts"]["markdown"] = [str(path) for path in sorted((folder / "insights").glob("*.md"))]
                return response
        except Exception as exc:
            detail = exc.as_dict() if hasattr(exc, "as_dict") else {"category": type(exc).__name__, "message": str(exc)[:1500]}
            return {**response, "status": "failed", "run_id": run_id, "error": detail}
        finally:
            if module is not None:
                try:
                    module.store.save_corpus()
                except OSError:
                    response.setdefault("warnings", []).append("Shared corpus cache could not be saved; stage files are retained")


def handle_request(payload):
    return InferenceService().handle(payload)


if __name__ == "__main__":
    import argparse
    from contextlib import redirect_stdout

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True, help="Request JSON in UTF-8")
    parser.add_argument("--response", type=Path, help="Optional response JSON path")
    args = parser.parse_args()
    with redirect_stdout(sys.stderr):
        result = handle_request(json.loads(args.request.read_text(encoding="utf-8-sig")))
    if args.response:
        atomic_json(args.response, result)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    raise SystemExit(1 if result["status"] == "failed" else 0)
