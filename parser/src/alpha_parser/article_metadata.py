"""Explicit article headline/date extraction; unrelated footer dates are ignored."""
from datetime import datetime
import re

DATE_CLASS = re.compile(r"(?:date|publish|timestamp|time)", re.I)
RELATED = re.compile(r"(?:related|recommend|footer|copyright|news__item|card__|modal|popup)", re.I)


def valid_date(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    match = re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})(?:\s+\d{1,2}:\d{2})?", value)
    if match:
        try:
            year = int(match[3])
            if len(match[3]) == 2:
                year += 2000 if year <= 68 else 1900
            return datetime(year, int(match[2]), int(match[1])).isoformat()
        except ValueError:
            pass
    return None


def article_metadata(tree, parsed):
    title_candidates = tree.xpath('//article//h1|//main//h1|//h1')
    title = next((" ".join(e.text_content().split()) for e in title_candidates if e.text_content().strip()), None)
    title = title or next(iter(tree.xpath('//meta[@property="og:title"]/@content')), None)
    title = title or next(iter(tree.xpath('//head/title/text()')), None) or parsed.get("title")
    published, updated, evidence = None, None, None
    for element in tree.xpath("//meta[@content]"):
        name = (element.get("property") or element.get("name") or element.get("itemprop") or "").lower()
        if name in {"article:published_time", "datepublished", "pubdate", "publishdate"}:
            value = valid_date(element.get("content"))
            if value and published is None:
                published = value
                evidence = {"method": "publication_meta", "raw": element.get("content"), "field": name}
        if name in {"article:modified_time", "datemodified"}:
            updated = valid_date(element.get("content")) or updated
    import json
    for script in tree.xpath('//script[@type="application/ld+json"]/text()'):
        try:
            nodes = json.loads(script)
            nodes = nodes if isinstance(nodes, list) else [nodes]
            for node in nodes[:50]:
                if not isinstance(node, dict):
                    continue
                for candidate in [node, *node.get("@graph", [])[:50]]:
                    if not isinstance(candidate, dict) or "article" not in str(candidate.get("@type", "")).lower():
                        continue
                    value = valid_date(candidate.get("datePublished"))
                    if value and published is None:
                        published = value
                        evidence = {"method": "article_json_ld", "raw": candidate["datePublished"]}
                    updated = updated or valid_date(candidate.get("dateModified"))
        except (ValueError, TypeError):
            continue
    # Only a unique article/header date is accepted. Lists, related cards and footer dates do not qualify.
    if published is None:
        candidates = []
        for element in tree.xpath('//time[@datetime]|//*[@itemprop="datePublished"]|//*[@class]'):
            marker = element.get("class", "")
            if element.tag != "time" and element.get("itemprop") != "datePublished" and not DATE_CLASS.search(marker):
                continue
            if any(RELATED.search(e.get("class", "")) or e.tag in {"footer", "nav"}
                   for e in [element, *element.iterancestors()]):
                continue
            raw = element.get("datetime") or element.get("content") or " ".join(element.text_content().split())
            value = valid_date(raw)
            if value:
                candidates.append((value, raw, element.tag, marker))
        if len({row[0] for row in candidates}) == 1:
            published, raw, tag, marker = candidates[0]
            evidence = {"method": "visible_article_date", "raw": raw, "tag": tag, "class": marker}
    return title, published, updated, evidence


def clean_tree(tree):
    import copy
    cleaned = copy.deepcopy(tree)
    for element in list(cleaned.xpath("//script|//style|//nav|//footer|//form|//*[@role='dialog']|//*[@class]")):
        marker = element.get("class", "")
        if element.tag in {"script", "style", "nav", "footer", "form"} or element.get("role") == "dialog" or re.search(r"(?:^|[ _-])(?:modal|popup)(?:$|[ _-])", marker, re.I):
            if element.getparent() is not None:
                element.drop_tree()
    return cleaned
