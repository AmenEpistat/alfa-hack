"""Discover editable industry peers through the GLM tool agent, without a company catalog."""
import re
import uuid
from urllib.parse import urlsplit
from .agent import GLMPlanner, QueryArgs, FetchArgs, FinishArgs, BudgetError
from .llm import ProviderError
from .schemas import Action, PeerCandidate, PeerCandidates, PeerDiscoveryRequest, WatchCompany, utcnow
from .sources import canonical


PEER_TOOLS = {"search_web": QueryArgs, "fetch_article": FetchArgs, "record_peer": PeerCandidate, "record_peers": PeerCandidates, "finish": FinishArgs}


def normalized(text):
    return " ".join(text.casefold().split())


def domain_of(url):
    return (urlsplit(url).hostname or "").casefold().removeprefix("www.")


def validate_peer(candidate, evidence, request):
    evidence_url = canonical(candidate.evidence_url)
    if evidence_url not in evidence:
        raise ValueError("evidence_url must refer to a fetched page")
    page = evidence[evidence_url]
    domain = candidate.domain.casefold().removeprefix("www.").rstrip(".")
    host = domain_of(page["url"])
    if not host or not domain or host != domain:
        raise ValueError("company domain must match the fetched evidence domain")
    if any(domain == excluded or domain.endswith("." + excluded) for excluded in
           [x.casefold().removeprefix("www.").rstrip(".") for x in request.exclude_domains]):
        raise ValueError("company domain is excluded")
    if normalized(candidate.industry_evidence) not in normalized(page["text"]):
        raise ValueError("industry evidence must be a quote from the fetched text")
    if not any(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", page["text"], re.IGNORECASE)
               for name in [candidate.name, *candidate.aliases] if name.strip()):
        raise ValueError("company name or alias must occur in the fetched text")
    return WatchCompany(name=candidate.name, aliases=candidate.aliases, domain=domain,
                        specialization=request.industry, geography=request.region,
                        enabled=True, confirmed=True, origin="industry_agent", relationship="industry_peer",
                        industry=request.industry, discovery_evidence=[{
                            "url": page["url"], "title": page["title"], "quote": candidate.industry_evidence,
                            "industry_match_reason": candidate.industry_match_reason, "fetched_at": page["fetched_at"]}])


class PeerDiscoveryAgent:
    def __init__(self, store, settings, sources, planner=None):
        self.store, self.settings, self.sources, self.planner = store, settings, sources, planner

    def run(self, request: PeerDiscoveryRequest, *, checkpoint=None):
        if re.search(r"\b(?:U_\d+|F_\d+|group_\w+)\b", request.industry + " " + (request.region or ""), re.I):
            raise ValueError("provide public industry/region, not internal identifiers")
        report = {"discovery_id": str(uuid.uuid4()), "industry": request.industry, "region": request.region,
                  "status": "partial", "companies": [], "gaps": [], "errors": [], "trace": [],
                  "usage": {"input_tokens": 0, "output_tokens": 0, "calls": 0, "cost_rub": None}}
        if not self.sources.settings.searxng_url:
            report["gaps"].append("SearXNG is not configured; no company names were generated")
            return report
        if self.planner is None:
            if not all((self.settings.llm_base_url, self.settings.llm_model, self.settings.llm_api_key)):
                report["gaps"].append("GLM is not configured; no company names were generated")
                return report
            self.planner = GLMPlanner(self.settings, self.store)
        candidates, evidence, domains = set(), {}, set()
        if checkpoint is not None:
            # Restore only evidence actually present in this store, never trust caller-provided text.
            if checkpoint.get("industry") != request.industry or checkpoint.get("region") != request.region:
                raise ValueError("checkpoint industry/region must match request")
            report["previous_attempt"] = {
                "discovery_id": checkpoint.get("discovery_id"), "errors": checkpoint.get("errors", []),
                "usage": checkpoint.get("usage", {}), "gaps": checkpoint.get("gaps", [])}
            report["trace"] = checkpoint.get("trace", [])[-3:]
            for step in checkpoint.get("trace", []):
                result = step.get("result", {})
                if step.get("tool") == "search_web":
                    candidates.update(canonical(c["url"]) for c in result.get("candidates", []))
                if step.get("tool") == "fetch_article" and not result.get("error") and result.get("url"):
                    doc = next((d for d in reversed(self.store.documents(history=True))
                                if d.get("url") == result["url"] and d.get("fetched_at") == result.get("fetched_at")), None)
                    if doc is None:
                        continue
                    text = "\n".join(c["text"] for c in self.store.chunks(doc["version_id"]))
                    page = {"url": doc["url"], "title": doc["title"], "text": text, "fetched_at": doc["fetched_at"]}
                    evidence[canonical(result["url"])] = page
                    evidence[canonical(step["arguments"]["url"])] = page
        pages = 0
        schemas = {k: v.model_json_schema() for k, v in PEER_TOOLS.items()}
        for step in range(self.settings.max_steps):
            state = {"purpose": "industry_peer_discovery", "industry": request.industry, "region": request.region,
                     "limit": request.limit, "exclude_domains": request.exclude_domains,
                     "remaining_evidence_pages": self.settings.max_pages - pages,
                     "loaded_evidence": [{"url": p["url"], "title": p["title"], "text": p["text"][:1600]}
                                        for p in list({p["url"]: p for p in evidence.values()}.values())[-3:]],
                     "recorded_companies": [{"name": c["name"], "domain": c["domain"]} for c in report["companies"]],
                     "observations": report["trace"][-3:], "gaps": report["gaps"], "remaining_steps": self.settings.max_steps - step}
            try:
                action = Action.model_validate(self.planner.choose(state, schemas))
                if action.tool not in PEER_TOOLS:
                    raise ValueError("tool not allowed for peer discovery")
                args = PEER_TOOLS[action.tool].model_validate(action.arguments)
            except (BudgetError, ProviderError) as exc:
                report["gaps"].append(str(exc))
                report["errors"].append({"stage": "planner", **(exc.as_dict() if isinstance(exc, ProviderError) else {"category": "token_budget"})})
                break
            except Exception as exc:
                report["trace"].append({"tool": "invalid_action", "result": {"error": type(exc).__name__, "message": str(exc)[:500]}})
                continue
            record = {"step": step, "tool": action.tool, "arguments": args.model_dump(), "reason": action.reason}
            try:
                if action.tool == "search_web":
                    result = self.sources.search_web(args.query, None, None)
                    candidates.update(canonical(c["url"]) for c in result.get("candidates", []))
                elif action.tool == "fetch_article":
                    if canonical(args.url) not in candidates:
                        raise ValueError("page must come from this discovery's search results")
                    if pages >= self.settings.max_pages:
                        raise BudgetError("peer evidence page budget exhausted")
                    pages += 1
                    doc = self.sources.fetch_article(args.url)["document"]
                    if doc["quality"] == "failed":
                        raise ValueError("failed evidence extraction")
                    text = "\n".join(chunk["text"] for chunk in self.store.chunks(doc["version_id"]))
                    page = {"url": doc["url"], "title": doc["title"], "text": text, "fetched_at": doc.get("fetched_at", utcnow())}
                    evidence[canonical(args.url)] = page
                    evidence[canonical(doc["url"])] = page
                    result = {**page, "text": text[:2400], "text_truncated": len(text) > 2400}
                elif action.tool in {"record_peer", "record_peers"}:
                    items = [args] if action.tool == "record_peer" else args.companies
                    validated = [validate_peer(item, evidence, request) for item in items]
                    new_domains = [company.domain for company in validated]
                    if len(set(new_domains)) != len(new_domains) or domains.intersection(new_domains):
                        raise ValueError("company domain already recorded")
                    for company in validated[:request.limit - len(report["companies"])]:
                        domains.add(company.domain)
                        report["companies"].append(company.model_dump(mode="json"))
                    result = ({"recorded": True, "name": validated[0].name, "domain": validated[0].domain}
                              if action.tool == "record_peer" else
                              {"recorded": True, "companies": [{"name": c.name, "domain": c.domain} for c in validated]})
                else:
                    report["gaps"].extend(args.gaps)
                    result = {"finished": True}
                record["result"] = result
            except Exception as exc:
                record["result"] = {"error": type(exc).__name__, "message": str(exc) if isinstance(exc, (ValueError, BudgetError)) else "source request failed"}
                report["errors"].append({"stage": action.tool, "error": type(exc).__name__})
            report["trace"].append(record)
            if action.tool == "finish" or len(report["companies"]) >= request.limit:
                break
        report["usage"] = getattr(self.planner, "usage", report["usage"])
        if len(report["companies"]) >= request.limit and not report["errors"]:
            report["status"] = "complete"
        elif len(report["companies"]) < request.limit:
            report["gaps"].append(f"Found {len(report['companies'])} evidence-backed industry peers of {request.limit} requested")
        return report
