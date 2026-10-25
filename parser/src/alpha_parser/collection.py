"""Bounded multi-source collection for ranking; no per-article model calls."""
from collections import deque
from datetime import timedelta
import re
import uuid
import httpx
from .collector import SourceCollector
from .schemas import utcnow
from .sources import canonical
from .text_quality import is_substantive_fragment
from .coverage import count_run_sources, select_diverse_hits
from .diversity import select_diverse_events, diversity_summary
from .competitor_news import (RECENT_DAYS, MAX_NEWS_AGE_DAYS, candidate_is_static,
                              make_event, cached_events, build_brief, read_chunks, official_news_links)


def add_event(run, event):
    if event["version_id"] not in {e["version_id"] for e in run["competitor_events"]}:
        run["competitor_events"].append(event)


def finalize_competitors(run):
    policy = run["competitor_news_policy"]
    run["competitor_events"] = select_diverse_events(run["competitor_events"],
        total_limit=policy["total_target"], max_per_company=policy["max_news_per_company"])
    run["competitor_diversity"] = diversity_summary(run["competitor_events"],
        min_companies=policy["min_companies"], max_per_company=policy["max_news_per_company"],
        min_sources=policy["total_target"])
    run["competitor_brief"] = build_brief(run)


def collect_materials(store, settings, sources, request, context, watches, limits, peer_report=None):
    run = {"run_id": str(uuid.uuid4()), "status": "running", "mode": "source_collection",
           "request": request.model_dump(mode="json"), "context": context, "watchlist": watches,
           "documents": [], "chunk_ids": [], "trace": [], "queries": [], "gaps": [], "errors": [],
           "usage": (peer_report or {}).get("usage", {"input_tokens": 0, "output_tokens": 0, "calls": 0, "cost_rub": None}),
           "peer_discovery": peer_report, "updated_at": utcnow(), "coverage": "bounded candidates for downstream ranking"}
    run["source_requirements"] = {"min_sources": limits.min_sources, "min_sources_per_topic": limits.min_sources_per_topic, "required_topics": ["news", "pdf", "competitors"]}
    run["competitor_news_policy"] = {
        "initial_search_days": RECENT_DAYS, "fallback_max_age_days": MAX_NEWS_AGE_DAYS,
        "publication_date_required": True, "exclude_static_pages": True,
        "order": "published_at_desc", "impact_method": "conditional_event_rules",
         "target_news_per_company": min(2, limits.competitor_limit),
        "max_news_per_company": 2, "min_companies": 3,
        "total_target": max(limits.min_sources_per_topic, limits.competitor_limit) if limits.competitor_limit else 0,
        "selection": "one_per_company_then_second"}
    run["competitor_events"] = []
    helper = SourceCollector()
    if peer_report:
        run["gaps"].extend(peer_report.get("gaps", []))
        run["errors"].extend({**error, "component": "peer_discovery"} for error in peer_report.get("errors", []))
    query = " ".join(x for x in [request.topic, context.get("company_industry"), context.get("company_city") or context.get("company_region")] if x)
    if limits.pdf_limit:
        candidates = store.search(query, source_type="alpha_pdf", start=request.start, end=request.end, limit=100)
        hits = select_diverse_hits([hit for hit in candidates if is_substantive_fragment(hit["chunk"]["text"])],
                                   limits.pdf_limit)
        helper.add_hits(run, hits)
        run["trace"].append({"tool": "search_local", "arguments": {"query": query},
                             "result": {"hits_count": len(hits)}})
    plans = []
    if request.external and limits.news_limit:
        plans.append({"key": "news", "target": limits.news_limit, "queue": deque(), "urls": set(),
                      "queries": [query, request.topic + " новости " + (context.get("company_city") or context.get("company_region") or "")]})
    if request.external and limits.competitor_limit:
        for watch in watches:
            name = " ".join(re.findall(r"[\w-]+", watch["name"]))
            if len(re.sub(r"\W", "", name)) < 3:
                alias = max([name, *watch.get("aliases", [])], key=len)
                descriptor = " ".join(word for word in re.findall(r"[\w-]+", alias) if word.casefold() != name.casefold())
                term = f'"{name}" {descriptor}'.strip()
            else:
                term = f'"{name}"'
            plans.append({"key": watch["id"], "target": 2, "queue": deque(), "urls": set(),
                          "queries": [f'{term} site:{watch["domain"]} новости',
                                     f'{term} новости результаты развитие',
                                     f'{term} цены продажи инвестиции',
                                     f'{term} новости {request.topic}']})
        if not watches:
            helper.gap(run, "Competitor collection has no enabled company targets")
    focus = context.get("audience_search_focus")
    if focus:
        for plan in plans:
            if plan["key"] == "news":
                plan["queries"].insert(0, " ".join(str(x) for x in (
                    context.get("company_industry"), context.get("company_city") or context.get("company_region"), focus) if x))
    collected = {plan["key"]: set() for plan in plans}
    attempted, accepted = set(), set()
    cached_rows = []
    cached_urls = set()
    if limits.competitor_limit:
        cached_rows = cached_events(store, settings, request, context, watches, refresh_metadata=bool(request.external))
        selected = select_diverse_events([row[0] for row in cached_rows],
            total_limit=run["competitor_news_policy"]["total_target"], max_per_company=2)
        selected_versions = {event["version_id"] for event in selected}
        for event, doc, chunks in cached_rows:
            if event["version_id"] not in selected_versions:
                continue
            matched = {match["watch_id"] for match in event["competitors"]}
            if not any(key in collected and len(collected[key]) < 2 for key in matched):
                continue
            helper.add_document(run, doc)
            run["chunk_ids"] = list(dict.fromkeys(run["chunk_ids"] + [c["chunk_id"] for c in chunks]))
            add_event(run, event)
            accepted.add(doc["version_id"])
            cached_urls.add(canonical(doc["url"]))
            for key in matched:
                if key in collected:
                    collected[key].add(doc["version_id"])
            run["trace"].append({"tool": "cached_competitor_event", "result": {
                "version_id": doc["version_id"], "published_at": doc["published_at"]}})
    search_available = True

    def enqueue(plan, items, *, priority=False):
        for item in items:
            if not item.get("url"):
                continue
            url = canonical(item["url"])
            if url in cached_urls:
                continue
            if url.lower().split("?", 1)[0].endswith((".pdf", ".xlsx", ".zip")):
                run["trace"].append({"tool": "filter_candidate", "arguments": {"url": url},
                                     "result": {"excluded": "Non-HTML candidate; use explicit PDF ingestion"}})
                continue
            if plan["key"] != "news" and candidate_is_static(url):
                continue
            if url not in plan["urls"]:
                plan["urls"].add(url)
                if priority:
                    plan["queue"].appendleft(url)
                else:
                    plan["queue"].append(url)

    for plan in plans:
        if plan["key"] != "news":
            targets = [w for w in watches if w["id"] == plan["key"]]
            for _, doc, _ in cached_rows:
                enqueue(plan, official_news_links(doc, targets))
            evidence_urls = {item["url"] for watch in targets for item in watch.get("discovery_evidence", [])}
            for doc in store.documents():
                if doc.get("url") in evidence_urls:
                    enqueue(plan, official_news_links(doc, targets, include_hubs=True))
        specs = [(query, None) for query in plan["queries"]] if plan["key"] == "news" else [
            (query, RECENT_DAYS) for query in plan["queries"][:3]] + [
            (query, MAX_NEWS_AGE_DAYS) for query in (plan["queries"][0], plan["queries"][-1])]
        for search, days in specs:
            if not search_available or sources.fetcher.count >= settings.max_requests:
                break
            run["queries"].append(search)
            search_start = max(request.start, request.end - timedelta(days=days)) if days else request.start
            record = {"tool": "search_web", "arguments": {"query": search, "start": str(search_start),
                       "end": str(request.end)}, "target": plan["key"]}
            try:
                result = sources.search_web(search, str(search_start), str(request.end))
                enqueue(plan, result.get("candidates", []))
                record["result"] = {"candidates_count": len(result.get("candidates", []))}
                if result.get("gap"):
                    helper.gap(run, result["gap"])
            except Exception as exc:
                record["result"] = {"error": type(exc).__name__}
                run["errors"].append({"stage": "search_web", "target": plan["key"], "error": type(exc).__name__})
                if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
                    search_available = False
                    helper.gap(run, "SearXNG is unreachable; start the configured search service")
            run["trace"].append(record)
    # RSS is a fallback for news, not a replacement for competitor discovery.
    news_plan = next((p for p in plans if p["key"] == "news"), None)
    if news_plan and len(news_plan["queue"]) < news_plan["target"]:
        for spec in sources.registry:
            if not spec["enabled"] or spec["kind"] != "rss" or sources.fetcher.count >= settings.max_requests:
                continue
            try:
                enqueue(news_plan, sources.discover(spec["id"], limit=8))
            except Exception as exc:
                run["errors"].append({"stage": "read_rss", "source_id": spec["id"], "error": type(exc).__name__})
    store.run_put(run)
    while len(attempted) < settings.max_pages and sources.fetcher.count < settings.max_requests:
        progressed = False
        for plan in plans:
            unique = count_run_sources(store, run, version_ids=collected[plan["key"]])
            enough_topic = (count_run_sources(store, run, source_type="external") >= limits.min_sources_per_topic
                            if plan["key"] == "news" else unique >= 2)
            if unique >= plan["target"] and enough_topic:
                if plan["key"] != "news" or count_run_sources(store, run) >= limits.min_sources:
                    continue
            while plan["queue"] and plan["queue"][0] in attempted:
                plan["queue"].popleft()
            if not plan["queue"]:
                continue
            if len(attempted) >= settings.max_pages or sources.fetcher.count >= settings.max_requests:
                break
            progressed = True
            url = plan["queue"].popleft()
            attempted.add(url)
            record = {"tool": "fetch_article", "arguments": {"url": url}, "target": plan["key"]}
            try:
                doc = sources.fetch_article(url)["document"]
                if plan["key"] != "news":
                    targets = [w for w in watches if w["id"] == plan["key"]]
                    enqueue(plan, official_news_links(doc, targets), priority=True)
                published = doc.get("published_at")
                if doc["quality"] == "failed" or (published and not str(request.start) <= published[:10] <= str(request.end)):
                    record["result"] = {"excluded": "failed extraction or publication outside requested interval"}
                else:
                    chunks = [chunk for chunk in read_chunks(store, doc["version_id"])
                              if is_substantive_fragment(chunk["text"])]
                    text = "\n".join(chunk["text"] for chunk in chunks)
                    event, rejection = make_event(doc, chunks, watches, request, context)
                    matched = {match["watch_id"] for match in event["competitors"]} if event else set()
                    if not text.strip() or (plan["key"] != "news" and plan["key"] not in matched):
                        record["result"] = {"excluded": rejection or "Company identity not established"}
                    else:
                        helper.add_document(run, doc)
                        run["chunk_ids"] = list(dict.fromkeys(run["chunk_ids"] + [c["chunk_id"] for c in chunks]))
                        if plan["key"] == "news":
                            collected["news"].add(doc["version_id"])
                        if event:
                            add_event(run, event)
                        for watch_id in matched:
                            if watch_id in collected:
                                collected[watch_id].add(doc["version_id"])
                        accepted.add(doc["version_id"])
                        record["result"] = {"document_id": doc["document_id"], "version_id": doc["version_id"], "title": doc["title"]}
            except Exception as exc:
                record["result"] = {"error": type(exc).__name__}
                run["errors"].append({"stage": "fetch_article", "url": url, "error": type(exc).__name__})
            run["trace"].append(record)
            store.run_put(run)
        if not progressed:
            break
    for plan in plans:
        unique = count_run_sources(store, run, version_ids=collected[plan["key"]])
        if plan["key"] == "news" and unique < plan["target"]:
            helper.gap(run, f"Collection target {plan['key']}: {unique}/{plan['target']} unique documents")
    finalize_competitors(run)
    run["collection"] = {"targets": {p["key"]: p["target"] for p in plans},
                          "documents_collected": {key: count_run_sources(store, run, version_ids=value) for key, value in collected.items()},
                          "article_attempts": len(attempted), "external_documents": len(accepted),
                          "http_requests": sources.fetcher.count}
    run["status"] = "partial" if run["gaps"] or run["errors"] else "complete"
    if not run["documents"]:
        run["status"] = "partial"
    run["stop_reason"] = "Source collection completed within configured document and HTTP budgets"
    run["updated_at"] = utcnow()
    store.run_put(run)
    return run


def collect_cached_materials(store, settings, sources, request, context, watches, limits):
    """A new run over cached evidence only; never calls HTTP, a model or PDF extraction."""
    from .schemas import CollectionLimits
    run = collect_materials(
        store, settings, sources, request, context, watches,
        CollectionLimits(news_limit=0, competitor_limit=0, pdf_limit=limits.pdf_limit, min_sources=limits.min_sources,
                         min_sources_per_topic=limits.min_sources_per_topic))
    helper = SourceCollector()
    run["mode"] = "cached_collection"
    run["competitor_news_policy"].update(target_news_per_company=min(2, limits.competitor_limit),
        total_target=max(limits.competitor_limit, limits.min_sources_per_topic) if limits.competitor_limit else 0)
    helper.gap(run, "Cached-only run; no fresh web search, peer discovery or source downloads were performed")
    query = " ".join(x for x in [request.topic, context.get("company_industry"), context.get("company_city") or context.get("company_region")] if x)
    plans = []
    if limits.news_limit:
        plans.append(("news", query, max(limits.news_limit, limits.min_sources_per_topic, limits.min_sources - count_run_sources(store, run))))
    collected = {}
    external_versions = set()
    if limits.competitor_limit:
        peer_counts = {watch["id"]: set() for watch in watches}
        if not watches:
            helper.gap(run, "Competitor collection has no enabled company targets")
        rows = cached_events(store, settings, request, context, watches)
        chosen = select_diverse_events([row[0] for row in rows],
            total_limit=run["competitor_news_policy"]["total_target"], max_per_company=2)
        chosen_versions = {event["version_id"] for event in chosen}
        for event, doc, chunks in rows:
            if event["version_id"] not in chosen_versions:
                continue
            matched = {match["watch_id"] for match in event["competitors"]}
            if not any(count_run_sources(store, run, version_ids=peer_counts[key]) <
                       2 for key in matched):
                continue
            helper.add_document(run, doc)
            run["chunk_ids"] = list(dict.fromkeys(run["chunk_ids"] + [c["chunk_id"] for c in chunks]))
            add_event(run, event)
            external_versions.add(doc["version_id"])
            for key in matched:
                peer_counts[key].add(doc["version_id"])
        for key, versions in peer_counts.items():
            collected[key] = count_run_sources(store, run, version_ids=versions)
            # One or two articles per company are enough; the global quota is checked separately.
    for key, search, target in plans:
        hits = select_diverse_hits(
            store.search(search, source_type="external", start=request.start, end=request.end, limit=100), 100)
        accepted, versions = [], set()
        for hit in hits:
            doc = hit["document"]
            if not is_substantive_fragment(hit["chunk"]["text"]):
                continue
            if doc["version_id"] not in versions and count_run_sources(store,
                {"documents": [hit["document"] for hit in accepted]}) >= target:
                continue
            versions.add(doc["version_id"])
            accepted.append(hit)
        helper.add_hits(run, accepted)
        external_versions.update(versions)
        collected[key] = count_run_sources(store, run, version_ids=versions)
        run["trace"].append({"tool": "search_local", "arguments": {"query": search, "source_type": "external"},
                             "result": {"hits_count": len(accepted)}, "target": key})
        if collected[key] < target:
            helper.gap(run, f"Collection target {key}: {collected[key]}/{target} cached unique documents")
    finalize_competitors(run)
    run["collection"] = {
        "targets": {**{key: target for key, _, target in plans},
                   **{w["id"]: 2 for w in watches if limits.competitor_limit}},
        "documents_collected": collected,
        "article_attempts": 0, "external_documents": len(external_versions), "http_requests": 0}
    run["status"] = "partial"
    run["stop_reason"] = "Cached collection completed without network or model calls"
    run["updated_at"] = utcnow()
    store.run_put(run)
    return run
