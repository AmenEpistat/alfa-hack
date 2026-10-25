"""Materialize source excerpts for a downstream ranker; no inference or ranking."""
import re
from urllib.parse import urlsplit
from .schemas import CompetitorMatch, RankingInput, RankingItem, RankingTopics, SourceCoverage
from .storage import Store, digest
from .coverage import coverage_for, coverage_gaps


def entity_matches(title, text, url, watches, *, allow_official_domain=False):
    host = (urlsplit(url or "").hostname or "").casefold().removeprefix("www.")
    content = title + "\n" + text
    matches = []
    for watch in watches:
        if not watch.get("confirmed") or not watch.get("enabled"):
            continue
        names = [watch["name"], *watch.get("aliases", [])]
        name_mention = False
        for name in names:
            if not name.strip():
                continue
            short = re.fullmatch(r"([^\W\d_]{1,2})\W*", name, re.UNICODE)
            if short:
                base = short[1]
                quoted = r"[«\"“„']\s*" + re.escape(base) + r"[!?]?\s*[»\"”']"
                exact = r"(?<!\w)" + re.escape(name) + r"(?!\w)"
                found = re.search(quoted, content, re.I) or re.search(exact, content)
            else:
                found = re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", content, re.I)
            if found:
                name_mention = True
                break
        domain = watch["domain"].casefold().removeprefix("www.")
        official = bool(host and domain and (host == domain or host.endswith("." + domain)))
        if not name_mention and not (allow_official_domain and official):
            continue
        matches.append(CompetitorMatch(watch_id=watch["id"], name=watch["name"], domain=watch["domain"],
                                      match_type=("official_domain_and_name" if name_mention else "official_domain") if official else "name_mention",
                                      relationship=watch.get("relationship") or "competitor", origin=watch.get("origin") or "manual"))
    return matches


def build_ranking_input(store: Store, run: dict) -> dict:
    """Use only this run's exact document versions and selected chunks.

    For a document added by cached parse_pdf without search hits, expose its
    stored chunks. Never extract a file, follow a candidate URL, or load a
    current replacement version in place of the version used by the run.
    """
    topics = RankingTopics()
    result = RankingInput(run_id=run["run_id"], status=run["status"], request=run["request"],
                          context=run.get("context"), topics=topics, search_window=run.get("search_window"),
                          company_input=run.get("company_input"),
                          preprocessing_input=run.get("preprocessing_input"),
                          company_analysis_context=run.get("company_analysis_context"),
                          competitor_events=run.get("competitor_events", []), competitor_brief=run.get("competitor_brief"),
                          competitor_news_policy=run.get("competitor_news_policy"),
                          competitor_diversity=run.get("competitor_diversity"),
                          watchlist=[{key: value for key, value in watch.items() if key not in {"owner"}}
                                     for watch in run.get("watchlist", [])],
                          gaps=list(run.get("gaps", [])), errors=list(run.get("errors", [])))
    selected = list(dict.fromkeys(run.get("chunk_ids", [])))
    watches = [w for w in run.get("watchlist", []) if w.get("confirmed") and w.get("enabled")]
    approved = {e["version_id"] for e in run.get("competitor_events", [])}
    news_policy = run.get("competitor_news_policy")
    missing = []
    seen = set()
    for reference in run.get("documents", []):
        version_id = reference["version_id"]
        if version_id in seen:
            continue
        seen.add(version_id)
        document = store.version(version_id)
        if document is None or document["document_id"] != reference["document_id"]:
            missing.append("Document version is unavailable: " + version_id)
            continue
        if document["quality"] == "failed":
            continue
        chunks = store.chunks(version_id)
        by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
        retrieved = [by_id[id_] for id_ in selected if id_ in by_id]
        if not retrieved:
            # parse_pdf records a document rather than a set of search hits.
            parsed = any(step.get("tool") == "parse_pdf" and not step.get("result", {}).get("error")
                         and step.get("result", {}).get("version_id") == version_id
                         for step in run.get("trace", []))
            # Legacy traces did not include version_id in parse_pdf results.
            parsed = parsed or any(step.get("tool") == "parse_pdf" and not step.get("result", {}).get("error")
                                   and "version_id" not in step.get("result", {})
                                   and step.get("result", {}).get("title") == document["title"]
                                   for step in run.get("trace", []))
            retrieved = chunks if parsed else []
        if not retrieved:
            missing.append("No collected text chunks for document version: " + version_id)
        published = document.get("published_at")
        date_in_range = (run["request"]["start"] <= published[:10] <= run["request"]["end"]) if published else None
        if date_in_range is False:
            missing.append("Document outside requested interval excluded: " + version_id)
            continue
        document_matches = entity_matches(document["title"], "\n".join(c["text"] for c in chunks),
            document.get("url"), watches, allow_official_domain=True) if news_policy and version_id in approved else None
        for chunk in retrieved:
            if not chunk["text"].strip():
                continue
            matches = document_matches if document_matches is not None else entity_matches(
                document["title"], chunk["text"], document.get("url"), watches)
            topic = "pdf" if document["source_type"] == "alpha_pdf" else "news"
            fields = {key: document.get(key) for key in ("source_type", "source_name", "original_filename", "url", "published_at", "fetched_at",
                                                       "quality", "warnings", "duplicate_group", "publication_date_evidence")}
            fields.update({key: chunk.get(key) for key in ("document_id", "version_id", "chunk_id", "text", "page_start",
                                                          "page_end", "char_start", "char_end", "section_title", "table_ids")})
            item = RankingItem(item_id=digest(f"ranking-1:{topic}:{chunk['chunk_id']}"), topic=topic,
                               title=document["title"], date_in_range=date_in_range, entity_matches=matches, **fields)
            getattr(topics, topic).append(item)
            if matches and (not news_policy or version_id in approved):
                # The same source can be ranked in two topics; chunk_id permits cross-topic deduplication.
                topics.competitors.append(item.model_copy(update={
                    "item_id": digest(f"ranking-1:competitors:{chunk['chunk_id']}"), "topic": "competitors"}))
    if news_policy:
        topics.competitors.sort(key=lambda item: item.published_at or "", reverse=True)
    diversity = run.get("competitor_diversity")
    if diversity and not diversity["requirements_met"]:
        missing.append(f"Competitor diversity insufficient: {diversity['companies_with_news']}/{diversity['min_companies']} companies; maximum two articles per company")
        if result.status not in {"running", "queued", "failed", "cancelled"}:
            result.status = "partial"
    result.gaps.extend(missing)
    for topic in ("news", "pdf", "competitors"):
        result.topic_gaps[topic] = [] if getattr(topics, topic) else [
            "No extracted materials collected for this topic in this run"]
    if not watches:
        result.topic_gaps["competitors"].append("No confirmed competitor watchlist snapshot in this run")
    minimum = run.get("source_requirements", {}).get("min_sources", 10)
    # Old run snapshots keep the requirements under which they were collected.
    minimum_per_topic = run.get("source_requirements", {}).get("min_sources_per_topic", 0)
    summary = coverage_for(topics.model_dump(mode="json"), minimum, minimum_per_topic)
    result.coverage = SourceCoverage.model_validate(summary)
    result.gaps = list(dict.fromkeys([*result.gaps, *coverage_gaps(summary)]))
    if not summary["requirements_met"] and result.status not in {"running", "queued", "failed", "cancelled"}:
        result.status = "partial"
    result.target_audience = run.get("target_audience")
    return result.model_dump(mode="json")
