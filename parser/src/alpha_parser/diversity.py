"""Select competitor publications across companies before taking a second article."""
from collections import Counter


def event_companies(event):
    return list(dict.fromkeys(
        match["domain"].casefold().removeprefix("www.").rstrip(".")
        for match in event.get("competitors", []) if match.get("domain")))


def select_diverse_events(events, *, total_limit=5, max_per_company=2):
    if total_limit <= 0:
        return []
    ordered = sorted(events, key=lambda event: event["published_at"], reverse=True)
    companies = list(dict.fromkeys(domain for event in ordered for domain in event_companies(event)))
    selected = []
    seen = set()
    counts = Counter()
    for _ in range(max_per_company):
        for company in companies:
            for event in ordered:
                domains = event_companies(event)
                identity = event.get("duplicate_group") or event["document_id"]
                if company not in domains or identity in seen or any(counts[d] >= max_per_company for d in domains):
                    continue
                selected.append(event)
                seen.add(identity)
                counts.update(domains)
                break
            if len(selected) >= total_limit:
                return sorted(selected, key=lambda event: event["published_at"], reverse=True)
    return sorted(selected, key=lambda event: event["published_at"], reverse=True)


def diversity_summary(events, *, min_companies=3, max_per_company=2, min_sources=5):
    counts = Counter(domain for event in events for domain in event_companies(event))
    identities = {event.get("duplicate_group") or event["document_id"] for event in events}
    return {"min_companies": min_companies, "max_sources_per_company": max_per_company,
            "min_sources": min_sources, "companies_with_news": len(counts), "sources": len(identities),
            "sources_by_company": dict(counts),
            "requirements_met": len(counts) >= min_companies and len(identities) >= min_sources
                               and all(count <= max_per_company for count in counts.values())}
