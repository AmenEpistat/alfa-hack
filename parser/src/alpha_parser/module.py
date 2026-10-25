"""Public in-process interface. No HTTP server or FastAPI import is required."""
from contextlib import contextmanager, nullcontext
from pathlib import Path
from .config import Settings
from .context import Context
from .pdf import ingest_manifest, parse_pdf
from .ranking import build_ranking_input
from .periods import history_window
from .schemas import CompanyInput, CollectionLimits, PeerDiscoveryRequest, ResearchRequest, WatchCompany
from .sources import Sources
from .storage import Store


class ResearchModule:
    """Call from application code; each network operation owns its HTTP client/budget."""

    def __init__(self, settings: Settings | None = None, *, workspace: str | Path = ".", output_dir: str | Path | None = None, cache_dir=None, budget_scope="default", tenant_scope="default"):
        self.workspace = Path(workspace).resolve()
        base = settings or Settings(_env_file=self.workspace / ".env")
        paths = {key: (self.workspace / getattr(base, key)).resolve()
                 for key in ("data_dir", "input_dir", "config_dir", "tessdata")}
        if output_dir is not None:
            paths["data_dir"] = Path(output_dir).resolve()
        self.settings = base.model_copy(update=paths)
        self.store = Store(self.settings.data_dir, cache_dir=cache_dir, budget_scope=budget_scope, tenant_scope=tenant_scope)

    @contextmanager
    def _sources(self):
        source = Sources(self.store, self.settings)
        try:
            yield source
        finally:
            source.fetcher.close()

    def ingest_pdf(self, path: str | Path, *, logical_id=None, title=None, published_at=None, force=False):
        return parse_pdf(self.store, self.settings, self.workspace / path, logical_id=logical_id,
                         title=title, published_at=published_at, force=force)

    def ingest_pdfs(self, manifest: str | Path | None = None, *, force=False):
        path = self.workspace / manifest if manifest else self.settings.config_dir / "analytics_manifest.json"
        return ingest_manifest(self.store, self.settings, path, force)

    def get_context(self, company_id: str, *, group_id=None, role=None):
        return Context(self.store).get(company_id, group_id, role)

    def _owner(self, company_id, group=False):
        if not group:
            return company_id
        context = self.get_context(company_id)
        if not context["group_id"]:
            raise ValueError("company has no known group")
        return "group:" + context["group_id"]

    def add_competitor(self, company_id: str, company: WatchCompany | dict):
        spec = WatchCompany.model_validate(company)
        return self.store.watch_add(self._owner(company_id, spec.apply_to_group), spec)

    def discover_competitors(self, industry: str, *, region=None, limit=3, exclude_domains=None, checkpoint=None):
        """Accept the industry field directly from the caller's dataset processor."""
        from .peers import PeerDiscoveryAgent
        request = PeerDiscoveryRequest(industry=industry, region=region, limit=limit, exclude_domains=exclude_domains or [])
        from .cache import code_fingerprint
        key = {"request": request.model_dump(mode="json"), "model": self.settings.llm_model,
               "endpoint": self.settings.llm_base_url,
               "thinking": [self.settings.llm_thinking_protocol, self.settings.llm_thinking_mode, self.settings.llm_reasoning_effort],
               "code": code_fingerprint([Path(__file__).with_name("peers.py"), Path(__file__).with_name("agent.py")])}
        cache = self.store.cache
        lock = cache.lock("peers", key) if cache is not None and checkpoint is None else nullcontext()
        with lock:
            if cache is not None and not getattr(self.store, "refresh_cache", False) and checkpoint is None:
                report = cache.get("peers", key, ttl=self.settings.peer_cache_ttl)
                if report is not None:
                    report["cache"] = {"hit": True, "historical_usage": report.pop("usage", {})}
                    report["usage"] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_rub": 0,
                                       "scope": "cache retrieval; no model call"}
                    return report
            with self._sources() as sources:
                report = PeerDiscoveryAgent(self.store, self.settings, sources).run(request, checkpoint=checkpoint)
            if cache is not None and report.get("status") == "complete" and report.get("companies") and not report.get("errors"):
                cache.put("peers", key, report, ttl=self.settings.peer_cache_ttl)
            return report

    def ensure_industry_competitors(self, company_id: str, industry: str, *, region=None, limit=3, exclude_domains=None, checkpoint=None):
        """Seed an agent-generated default once; never undo user edits/deletions."""
        existing = self.store.watches(company_id)
        if existing or self.store.watch_defaults_initialized(company_id):
            return {"status": "existing", "companies": existing, "discovery": None}
        report = self.discover_competitors(industry, region=region, limit=limit, exclude_domains=exclude_domains, checkpoint=checkpoint)
        companies = [WatchCompany.model_validate(c) for c in report["companies"]]
        if companies and report.get("status") == "complete":
            self.store.seed_watches(company_id, companies, report["discovery_id"])
        return {"status": report["status"], "companies": self.store.watches(company_id), "discovery": report}

    def collect_from_profile(self, profile: CompanyInput | dict, *, topic,
                             news_limit=5, competitor_limit=5, pdf_limit=15,
                             discover_peers=True, cached_only=False, min_sources=10, target_audience: dict | None = None):
        """Use a preprocessing JSON company directly; raw CSV/financial tables are not required."""
        spec = CompanyInput.model_validate(profile)
        return self.collect_for_ranking(
            company_id=spec.company_id, profile=spec, topic=topic,
            news_limit=news_limit, competitor_limit=competitor_limit, pdf_limit=pdf_limit,
            discover_peers=discover_peers, cached_only=cached_only, min_sources=min_sources, target_audience=target_audience)

    def collect_for_ranking(self, *, company_id, topic, industry=None, region=None,
                            news_limit=5, competitor_limit=5, pdf_limit=15, discover_peers=True,
                            profile: CompanyInput | dict | None = None, cached_only=False, min_sources=10, target_audience: dict | None = None):
        """Collect bounded source evidence from the complete preprocessed company profile."""
        from .collection import collect_materials, collect_cached_materials
        spec = CompanyInput.model_validate(profile) if profile is not None else None
        if spec is not None:
            if spec.company_id != company_id:
                raise ValueError("profile.company_id must match company_id")
            self.store.state["company_profiles"][spec.company_id] = spec.model_dump(mode="json")
            public = spec.public_context()
            group_id = spec.group_id
        else:
            context = self.get_context(company_id)
            public = Context.public(context)
            group_id = context["group_id"]
        window = history_window()
        request = ResearchRequest(company_id=company_id, group_id=group_id, topic=topic, start=window.start, end=window.end,
                                  external=not cached_only)
        limits = CollectionLimits(news_limit=news_limit, competitor_limit=competitor_limit, pdf_limit=pdf_limit, min_sources=min_sources)
        if industry is not None:
            public["company_industry"] = PeerDiscoveryRequest(industry=industry).industry
            public["industries"] = [industry]
        if region is not None:
            public["company_region"] = region
            public["regions"] = [region]
        if target_audience:
            public["audience_search_focus"] = target_audience.get("search_focus", "")
        discovery = None
        if discover_peers and competitor_limit and not cached_only:
            defaults = self.ensure_industry_competitors(company_id, public["company_industry"], region=public["company_region"])
            discovery = defaults["discovery"]
        watches = self.store.watches(company_id)
        if group_id and not (spec and spec.identity_ambiguous):
            watches += [w for w in self.store.watches("group:" + group_id) if w["apply_to_group"]]
        watches = [w for w in watches if w["confirmed"] and w["enabled"]]
        with self._sources() as sources:
            if cached_only:
                run = collect_cached_materials(self.store, self.settings, sources, request, public, watches, limits)
            else:
                run = collect_materials(self.store, self.settings, sources, request, public, watches, limits, discovery)
        run["search_window"] = window.metadata()
        run["target_audience"] = target_audience
        if spec is not None:
            run["input_source"] = "preprocessing_json"
            run["company_input"] = spec.model_dump(mode="json")
            from .profile_context import apply_profile_context
            apply_profile_context(run, spec)
            if spec.identity_ambiguous:
                run["gaps"].append("Company profile has a source ID collision; payment/person relations were not joined")
                run["status"] = "partial"
            self.store.run_put(run)
        result = self._with_ranking_input(run)
        self.store.run_put({key: value for key, value in result.items() if key != "ranking_input"})
        from .storage import write_json
        write_json(self.store.root / "04_ranker_input.json", result["ranking_input"])
        return result

    def get_run(self, run_id: str):
        run = self.store.run_get(run_id)
        return self._with_ranking_input(run) if run is not None else None

    def _with_ranking_input(self, run):
        ranking = build_ranking_input(self.store, run)
        return {**run, "status": ranking["status"], "gaps": ranking["gaps"],
                "coverage": ranking["coverage"], "ranking_input": ranking}

    def get_ranking_input(self, run_id: str):
        run = self.store.run_get(run_id)
        if run is None:
            raise KeyError("run not found")
        return build_ranking_input(self.store, run)


