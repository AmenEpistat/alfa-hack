"""Verified dated competitor events and conditional, source-linked impact hypotheses."""
from datetime import date
from urllib.parse import urlsplit
import re
from .ranking import entity_matches
from .storage import digest

RECENT_DAYS = 90
MAX_NEWS_AGE_DAYS = 365
STATIC = re.compile(r"/(?:jobs?|careers?|vacanc(?:y|ies)|vakansii|shops?|stores?|catalog|products?|about|contacts?)(?:/|$)", re.I)
EVENT_RULES = (
    ("store_relocation", r"переех|переез[дж]|смен[аы] адрес|relocat|store moved"),
    ("store_closure", r"закры(?:л|т|ва)|closed?\b|closur"),
    ("store_opening", r"откр(?:ыл|ыт|ыва)|нов\w* магазин|expan|open(?:ed|ing)?\b"),
    ("pricing", r"цен\w*|скидк\w*|дисконт\w*|pric(?:e|ing)|discount"),
    ("financial_results", r"выручк\w*|продаж\w*|прибыл\w*|отч[её]т\w*|revenue|sales|results|report"),
    ("investment", r"инвест\w*|приобр\w*|поглощ\w*|invest|acquisit"),
    ("logistics", r"логист\w*|достав\w*|распределительн\w*|склад\w*|logistic|deliver"),
    ("assortment", r"ассортимент\w*|собственн\w* торгов\w* марк\w*|бренд\w*|assortment|brand"),
)
SCENARIOS = {
    "store_relocation": ("customer_demand", "mixed",
        "Смена адреса торговой точки может перераспределить локальный спрос; она сама по себе не подтверждает увеличение числа магазинов.",
        ["Нужно сравнить прежний и новый адреса с нашими зонами обслуживания.",
         "Следует проверить изменение площади, ассортимента и покупательского трафика."]),
    "store_opening": ("customer_demand", "risk",
        "Новая торговая точка может перераспределить часть локального спроса.",
        ["Совпадают зоны обслуживания и покупательские сегменты.", "Нужно сопоставить адрес события с адресами торговых точек нашей компании."]),
    "store_closure": ("customer_demand", "opportunity",
        "Закрытие торговой точки может освободить локальный спрос.",
        ["Наша компания обслуживает тот же район и покупательский сегмент.", "Нужно проверить факт закрытия и изменение трафика."]),
    "pricing": ("price_pressure", "risk",
        "Изменение цен или скидок может усилить давление на цены и маржу.",
        ["Сравниваются одинаковые категории товаров и сопоставимые условия продажи.", "Нужны собственные цены, себестоимость и длительность акции."]),
    "financial_results": ("competitive_capacity", "uncertain",
        "Изменение продаж и финансовых результатов может менять возможности конкурента финансировать развитие.",
        ["Показатели и период должны быть сопоставимы.", "Рост выручки сам по себе не доказывает отток покупателей нашей компании."]),
    "investment": ("competitive_capacity", "mixed",
        "Инвестиции или приобретения могут изменить масштаб и возможности компании.",
        ["Нужны сроки реализации и затрагиваемые рынки.", "Следует проверить пересечение с нашей географией и ассортиментом."]),
    "logistics": ("service_competition", "mixed",
        "Изменения логистики и доставки могут повлиять на скорость обслуживания и доступность товаров.",
        ["Изменения распространяются на наш рынок.", "Нужно сопоставить сроки доставки, наличие товаров и издержки."]),
    "assortment": ("product_competition", "risk",
        "Изменение ассортимента может усилить конкуренцию за отдельные группы покупателей.",
        ["Есть пересечение товарных категорий и аудитории.", "Нужно сравнить ассортимент и условия продаж."]),
}


def candidate_is_static(url):
    return bool(STATIC.search(urlsplit(url).path) or urlsplit(url).path.lower().endswith((".pdf", ".xlsx", ".zip")))


def event_type(text):
    return next((kind for kind, pattern in EVENT_RULES if re.search(pattern, text, re.I)), "other")


def evaluate_news(doc, text, request):
    if candidate_is_static(doc.get("url") or "") or re.search(r"ваканси|требуется|careers?|vacanc", doc.get("title", ""), re.I):
        return None, "Static company/service page is not a competitor news item"
    published = doc.get("published_at")
    if not published:
        return None, "Publication date is not verified; cannot classify as latest competitor news"
    try:
        day = date.fromisoformat(published[:10])
    except ValueError:
        return None, "Invalid publication date"
    end = date.fromisoformat(str(request.end))
    age = (end - day).days
    if age < 0 or day < date.fromisoformat(str(request.start)):
        return None, "Publication outside request history"
    if age > MAX_NEWS_AGE_DAYS:
        return None, "Historical material is not latest competitor news"
    if doc.get("quality") == "failed":
        return None, "Failed extraction"
    if not text.strip():
        return None, "Empty news text"
    kind = "store_relocation" if re.search(EVENT_RULES[0][1], text[:2500], re.I) else event_type(doc["title"])
    if kind == "other":
        kind = event_type(text[:2500])
    news_path = re.search(r"/(?:news|novosti|press|press-center|articles|article|events?)(?:/|-)", urlsplit(doc.get("url") or "").path, re.I)
    if kind == "other" and not news_path:
        return None, "No identifiable business event in extracted content"
    return {"event_type": kind, "age_days": age, "freshness": "last_90_days" if age <= RECENT_DAYS else "last_year"}, None


def make_event(doc, chunks, watches, request, context):
    text = "\n".join(c["text"] for c in chunks)
    eligibility, rejection = evaluate_news(doc, text, request)
    if rejection:
        return None, rejection
    matches = entity_matches(doc["title"], text[:1200], doc.get("url"), watches, allow_official_domain=True)
    if not matches:
        return None, "Competitor identity is not established"
    quote = text[:800]
    # Keep an exact, contiguous source quote; hypotheses never modify source text.
    scenario = SCENARIOS.get(eligibility["event_type"])
    hypotheses = []
    if scenario:
        channel, direction, hypothesis, conditions = scenario
        hypotheses.append({"type": "conditional_hypothesis", "method": "event_rule", "channel": channel,
                           "direction": direction, "text": hypothesis, "conditions": conditions,
                           "confidence": "not_quantified", "causality_established": False,
                           "geographic_overlap": "not_established",
                           "company_industry": context.get("company_industry"),
                           "company_region": context.get("company_region")})
    return {
        "event_id": digest("competitor-event:" + doc["version_id"])[:32],
        "document_id": doc["document_id"], "version_id": doc["version_id"], "duplicate_group": doc.get("duplicate_group"),
        "competitors": [m.model_dump(mode="json") for m in matches],
        "headline": doc["title"], "published_at": doc["published_at"],
        "publication_date_evidence": doc.get("publication_date_evidence"),
        "source_url": doc.get("url"), "source_name": doc["source_name"],
        "source_quality": doc["quality"], "source_warnings": doc.get("warnings", []),
        "fact": {"type": "source_excerpt", "text": quote, "chunk_ids": [c["chunk_id"] for c in chunks]},
        **eligibility, "impact_hypotheses": hypotheses,
        "limitations": ["Отраслевая близость не доказывает прямую конкуренцию.",
                       "Влияние на нашу компанию требует проверки географии, аудитории и собственных показателей."],
    }, None


def read_chunks(store, version_id):
    return store.chunks(version_id)


def cached_events(store, settings, request, context, watches, *, refresh_metadata=False):
    from .sources import extract_html
    events = []
    for doc in store.documents():
        if doc["source_type"] != "external" or candidate_is_static(doc.get("url") or ""):
            continue
        chunks = read_chunks(store, doc["version_id"])
        text = "\n".join(c["text"] for c in chunks)
        if not entity_matches(doc["title"], text, doc.get("url"), watches, allow_official_domain=True):
            continue
        if refresh_metadata and "/alpha-3" not in doc["extractor_version"]:
            from pathlib import Path
            original = Path(doc["original_path"])
            if original.is_file() and original.suffix.lower() == ".html":
                try:
                    doc = extract_html(store, original.read_bytes(), doc["url"], original_url=doc.get("original_url"),
                                     fetched_at=doc["fetched_at"])["document"]
                    chunks = read_chunks(store, doc["version_id"])
                except ValueError:
                    continue
        event, _ = make_event(doc, chunks, watches, request, context)
        if event:
            events.append((event, doc, chunks))
    events.sort(key=lambda row: row[0]["published_at"], reverse=True)
    return events


def official_news_links(doc, watches, limit=12, *, include_hubs=False):
    """Discover article links in retained official HTML without another request."""
    from pathlib import Path
    from urllib.parse import urljoin
    from lxml import html
    original = Path(doc.get("original_path") or "")
    if not original.is_file() or original.suffix.lower() != ".html":
        return []
    host = (urlsplit(doc.get("url") or "").hostname or "").lower().removeprefix("www.")
    domains = {w["domain"].lower().removeprefix("www.") for w in watches}
    if not any(host == domain or host.endswith("." + domain) for domain in domains):
        return []
    try:
        tree = html.fromstring(original.read_bytes())
    except (ValueError, html.etree.ParserError):
        return []
    urls = []
    for href in tree.xpath("//a[@href]/@href"):
        url = urljoin(doc["url"], href)
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname != urlsplit(doc["url"]).hostname:
            continue
        article = re.search(r"/(?:news|novosti|press|press-center|articles|events?)/[^/?#]+", parsed.path, re.I)
        hub = include_hubs and re.search(r"/(?:news|novosti|press|press-center)/?$", parsed.path, re.I)
        if not article and not hub:
            continue
        if candidate_is_static(url) or url in urls or url == doc["url"]:
            continue
        urls.append(url)
        if len(urls) >= limit:
            break
    return [{"url": url} for url in urls]


def build_brief(run):
    events = sorted(run.get("competitor_events", []), key=lambda e: e["published_at"], reverse=True)
    lines = []
    for event in events:
        names = ", ".join(m["name"] for m in event["competitors"])
        line = f'{event["published_at"][:10]} — {names}: {event["headline"]}. Источник: {event["source_url"]}'
        line += " Факт из публикации: " + event["fact"]["text"]
        for hypothesis in event["impact_hypotheses"]:
            line += " Возможное влияние: " + hypothesis["text"] + " Условия: " + " ".join(hypothesis["conditions"])
            if hypothesis.get("company_context_text"):
                line += " Данные нашей компании: " + hypothesis["company_context_text"]
        lines.append(line)
    policy = run.get("competitor_news_policy", {})
    target = policy.get("total_target", 0)
    gaps = []
    counts = {}
    for watch in run.get("watchlist", []):
        count = sum(any(m["watch_id"] == watch["id"] for m in event["competitors"]) for event in events)
        counts[watch["id"]] = count
    if target and len(events) < target:
        gaps.append(f"Found {len(events)}/{target} diverse competitor news sources")
    summary = run.get("competitor_diversity")
    if summary and not summary["requirements_met"]:
        gaps.append(f"Competitor diversity is insufficient: {summary['companies_with_news']}/{summary['min_companies']} companies")
    if not events:
        gaps.append("No dated recent competitor events found")
    return {"schema_version": "1.0", "company_id": run["request"]["company_id"],
            "as_of": run["request"]["end"], "events": events,
            "report_draft": "\n\n".join(lines),
            "scope": "Source facts and conditional impact hypotheses, before downstream business ranking",
            "gaps": gaps, "events_by_company": counts,
            "policy": run.get("competitor_news_policy"), "diversity": run.get("competitor_diversity"),
            "analysis_method": "Deterministic conditional event rules; no quantified causal estimate",
            "causality_established": False}
