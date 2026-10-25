"""Compact user-facing Markdown derived from validated insight JSON."""
from __future__ import annotations

import html
import re
from .categories import get_category
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlsplit

_ESCAPE = re.compile(r"([\\*_{}\[\]#!|~" + chr(96) + r"])")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_DOCUMENT_TYPES = {
    "external", "alpha_pdf", "pdf", "news", "external_news",
    "competitor", "competitors", "competitor_news",
}
# Presentation-only omissions: never convert lack of evidence into a fact.
# If a substantive sentence depends on a diagnostic clause, omit that sentence.
_DIAGNOSTIC = re.compile(
    r"\b(?:отсутств\w*|недостат\w*|нехват\w*|неяс\w*|неизвест\w*|неуточнен\w*|неподтвержден\w*|"
    r"не\s+(?:указан\w*|извест\w*|подтвержд\w*|раскрыт\w*|определен\w*|"
    r"предоставлен\w*|получен\w*|установлен\w*|доступ\w*|содерж\w*|хвата\w*))\b"
    r"|\b(?:нет|мало)\s+(?:данных|сведений|информации|подтверждений|источников)\b"
    r"|\b(?:требу\w*|нуж\w*|необходим\w*)\s+(?:дополнительн\w*\s+)?"
    r"(?:провер\w*|уточн\w*|подтвержд\w*|верифик\w*)\b"
    r"|\b(?:уточни\w*|доуточни\w*|перепровер\w*)\b"
    r"|\b(?:проверить|подтвердить|установить)\s*,?\s+"
    r"(?:ли\b|расположен\w*\b|находится\b|дат\w*\b|источник\w*\b)"
    r"|\b(?:нельзя|невозможно|не удается)\s+(?:определ\w*|оцен\w*|вывест\w*|подтверд\w*|установ\w*)"
    r"|\b(?:интерпретац\w*|предположени\w*|вывод\w*)\s+модел\w*"
    r"|\b(?:unknown|missing|unavailable|insufficient)\b"
    r"|\bnot\s+(?:supplied|provided|specified|confirmed|available)\b"
    r"|\b(?:needs?|requires?)\s+(?:verification|clarification|review)\b",
    re.IGNORECASE,
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ])")
_META_TAIL = re.compile(
    r",\s*(?:но|однако)\s+это\s+(?:лишь\s+)?(?:интерпретац|предполож|вывод).*$",
    re.IGNORECASE,
)


def _plain(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(_CONTROL.sub("", str(value)).split())


def _text(value: Any) -> str:
    raw = _ESCAPE.sub(r"\\\1", html.escape(_plain(value), quote=False))
    raw = re.sub(r"^(\d+)\.(?=\s)", r"\1\\.", raw)
    return re.sub(r"^([-+>])(?=\s)", r"\\\1", raw)


def _diagnostic(value: str) -> bool:
    return bool(_DIAGNOSTIC.search(value.replace("ё", "е")))


def _narrative(value: Any) -> str:
    """Omit diagnostic sentences/clauses; preserve complete conditional wording."""
    raw = _META_TAIL.sub("", _plain(value))
    kept = []
    for sentence in _SENTENCE.split(raw):
        if _diagnostic(sentence) and re.match(r"^(?:if|\u0435\u0441\u043b\u0438)\b", sentence, re.IGNORECASE):
            continue
        clauses = []
        for clause in re.split(r"\s*;\s*", sentence):
            # Retain a fact before a trailing diagnostic, without deleting any
            # business condition introducing the fact.
            tails = re.split(r",\s*(?:но|однако|при этом)\s+", clause, maxsplit=1)
            if len(tails) == 2 and _diagnostic(tails[1]):
                clause = tails[0]
            if clause and not _diagnostic(clause):
                clauses.append(clause.strip(" ;"))
        if clauses:
            fragment = "; ".join(clauses).rstrip(" ;,")
            if fragment and fragment[-1] not in ".!?\u2026":
                fragment += "."
            kept.append(fragment)
    return " ".join(kept).strip()


def _safe_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if any(char.isspace() or ord(char) < 32 for char in value) or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        parsed.port
    except ValueError:
        return None
    return quote(value, safe=":/?#@!$&'*+,;=%[]")


def _source_key(document: Mapping[str, Any]) -> tuple[str, str]:
    address = _safe_url(document.get("url"))
    if address:
        return "url", address
    if document.get("document_id"):
        return "document", str(document["document_id"])
    return "title", _plain(document.get("title"))


def _source_title(document: Mapping[str, Any]) -> str:
    if document.get("source_type") == "alpha_pdf":
        # Preserve the original upload name, never the content-addressed cache path.
        filename = document.get("original_filename")
        if isinstance(filename, str) and filename.strip():
            name = filename.strip().replace("\\", "/").rsplit("/", 1)[-1]
            if name.lower().endswith(".pdf"):
                return _plain(name[:-4])
    return _plain(document.get("title"))


class _Sources:
    def __init__(self):
        self.documents: list[Mapping[str, Any]] = []
        self.labels: dict[tuple[str, str], str] = {}

    def cite(self, documents: list[Mapping[str, Any]]) -> str:
        labels = []
        for document in documents:
            key = _source_key(document)
            if key not in self.labels:
                self.documents.append(document)
                self.labels[key] = f"S{len(self.documents)}"
            label = self.labels[key]
            if label not in labels:
                labels.append(label)
        return " ".join(f"[{label}]" for label in labels)

    def markdown(self, level: int = 2) -> str:
        if not self.documents:
            return ""
        lines = ["#" * level + " Источники", ""]
        for document in self.documents:
            label = self.labels[_source_key(document)]
            address = _safe_url(document.get("url"))
            title = _source_title(document) or address
            # Never substitute internal document/evidence IDs for a title.
            if title:
                link = f"[{_text(title)}]({address})" if address else _text(title)
                lines.append(f"- [{label}] {link}")
        return "\n".join(lines).rstrip() + "\n"


def _brief(value: Any) -> str:
    """Keep up to two complete narrative sentences, including business conditions."""
    raw = _narrative(value)
    sentences = []
    start = 0
    for match in _SENTENCE.finditer(raw):
        before = raw[start:match.start()]
        if re.search(r"\b(?:г|гг|руб|коп|им|рис|табл|стр|др)\.$", before, re.IGNORECASE):
            continue
        sentences.append(before)
        start = match.end()
    if raw[start:]:
        sentences.append(raw[start:])
    return " ".join(sentences[:2])


def _nested_claims(value):
    if isinstance(value, Mapping):
        if {"text", "basis", "evidence"} <= value.keys():
            yield value
        else:
            for key, child in value.items():
                if key not in {"foundation", "lead", "source_summaries", "markdown", "sources_markdown"}:
                    yield from _nested_claims(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nested_claims(child)


class _Insight:
    def __init__(self, insight: Mapping[str, Any], sources: _Sources):
        self.insight = insight
        self.sources = sources
        self.citations: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
        self.seen: set[str] = set()
        for document in insight.get("foundation", {}).get("documents", []):
            if document.get("source_type") not in _DOCUMENT_TYPES:
                continue
            if not (_source_title(document) or _safe_url(document.get("url"))):
                continue
            for citation in document.get("citations", []):
                key = (str(citation.get("evidence_id", "")), str(citation.get("quote", "")))
                self.citations.setdefault(key, []).append(document)

    def documents(self, claim: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        found = []
        for evidence in claim.get("evidence", []):
            key = (str(evidence.get("evidence_id", "")), str(evidence.get("quote", "")))
            found.extend(self.citations.get(key, []))
        return found

    def claim(self, claim: Mapping[str, Any]) -> str:
        text = _narrative(claim.get("text"))
        documents = self.documents(claim)
        if not text or not documents:
            return ""
        key = text.casefold().rstrip(".!?")
        if key in self.seen:
            return ""
        self.seen.add(key)
        if claim.get("basis") == "bank_position" and not re.search(r"банк|альфа", text, re.IGNORECASE):
            text = "По оценке аналитиков Альфа-Банка: " + text
        return _text(text) + " " + self.sources.cite(documents)

    def render(self, title_level: int) -> str:
        event = self.insight.get("what_happened", {})
        sections = []
        event_lines = []
        event_claims = self.insight.get("events") or [
            event.get("summary"), *event.get("key_facts", []), *event.get("causes", [])
        ]
        for claim in event_claims:
            if claim:
                line = self.claim(claim)
                if line:
                    event_lines.append(line)
        timing = event.get("timing")
        if timing:
            # Keep an extra time reference when it adds a number not in the
            # summary/facts. Date/quality diagnostics are removed separately.
            timing_text = _narrative(timing.get("text"))
            numbers = set(re.findall(r"\d+", timing_text))
            covered = set(re.findall(r"\d+", " ".join(event_lines)))
            if numbers - covered:
                line = self.claim(timing)
                if line:
                    event_lines.append(line)
        if event_lines:
            sections.append(" ".join(event_lines))

        if self.insight.get("synthesis"):
            line = self.claim(self.insight["synthesis"])
            if line:
                sections.append(line)

        # PDF statements retain their author attribution. Client effects stay
        # in separate paragraphs and keep the model's conditional language.
        bank = self.insight.get("bank_assessment", {})
        if bank.get("status") == "documented_context":
            bank_lines = [self.claim(claim) for claim in bank.get("bank_statements", [])]
            if any(bank_lines):
                sections.append(" ".join(line for line in bank_lines if line))

        company_lines = [self.claim(claim) for claim in self.insight.get("why_important_for_company", [])]
        if any(company_lines):
            sections.append(" ".join(line for line in company_lines if line))
        for consequence in self.insight.get("possible_consequences", []):
            conditions = [_narrative(value) for value in consequence.get("conditions", [])]
            # Dropping a necessary condition would overstate the consequence.
            if any(not condition for condition in conditions):
                continue
            line = self.claim(consequence.get("claim", {}))
            if line:
                if conditions:
                    line += " Условия: " + "; ".join(_text(value).rstrip(".") for value in conditions) + "."
                sections.append(line)

        if bank.get("status") == "documented_context" and bank.get("model_interpretation"):
            line = self.claim(bank["model_interpretation"])
            if line:
                sections.append(line)

        actions = []
        for action in self.insight.get("relevant_actions", []):
            text = _narrative(action.get("action"))
            rationale = action.get("rationale", {})
            documents = self.documents(rationale)
            if text and documents and _narrative(rationale.get("text")):
                key = text.casefold().rstrip(".!?")
                if key not in self.seen:
                    self.seen.add(key)
                    actions.append("- " + _text(text) + " " + self.sources.cite(documents))
        if actions:
            sections.append("**Что можно сделать**\n\n" + "\n".join(actions))
        product_lines = []
        for recommendation in self.insight.get("product_recommendations", []):
            product = recommendation.get("product", {})
            url = _safe_url(product.get("url"))
            if not url or urlsplit(url).hostname != "alfabank.ru":
                continue
            name = _text(product.get("name"))
            mechanism = _narrative(recommendation.get("mechanism"))
            application = _narrative(recommendation.get("application"))
            if not name or not mechanism or not application:
                continue
            problem = recommendation.get("problem", {})
            documents = self.documents(problem)
            citation = (" " + self.sources.cite(documents)) if documents else ""
            product_lines.append("**[" + name + "](" + url + ")** — " + _text(mechanism) + citation)
            product_lines.append(_text(application))
            conditions = [product.get("applicability"), *recommendation.get("conditions", [])]
            conditions = list(dict.fromkeys(_narrative(value) for value in conditions if value))
            if any(conditions):
                product_lines.append("Условия применения: " + "; ".join(_text(value).rstrip(".") for value in conditions if value) + ".")
        if product_lines:
            sections.append("**Решение от Альфа-Банка**\n\n" + "\n\n".join(product_lines))
        if not sections:
            return ""
        # Render the body first to preserve the original source numbering.
        candidates = [self.insight.get("lead"), self.insight.get("synthesis"), event.get("summary")]
        lead = ""
        for candidate in candidates:
            if not candidate:
                continue
            text = _brief(candidate.get("text"))
            documents = self.documents(candidate)
            if text and documents and all(_source_key(doc) in self.sources.labels for doc in documents):
                lead = "**Кратко:** " + _text(text) + " " + self.sources.cite(documents)
                break
        if lead:
            sections.insert(0, lead)
        title = _narrative(self.insight.get("title")).rstrip(".") or "Инсайт"
        category_line = ""
        category = self.insight.get("category")
        category_id = self.insight.get("category_id")
        if category_id is None and isinstance(category, Mapping):
            category_id = category.get("id")
        if category_id is not None:
            try:
                category_line = "**Категория:** " + _text(get_category(category_id)["name"]) + "\n\n"
            except ValueError:
                pass  # Old saved articles are rendered without inventing a category.
        return "#" * title_level + " " + _text(title) + "\n\n> **Сгенерировано ИИ**\n\n" + category_line + "\n\n".join(sections) + "\n"


def render_insight_markdown(insight: Mapping[str, Any]) -> str:
    """Render one compact insight followed only by its used documentary sources."""
    sources = _Sources()
    body = _Insight(insight, sources).render(1)
    if not body:
        return ""
    footer = sources.markdown()
    return body.rstrip() + ("\n\n" + footer if footer else "\n")


def render_sources_markdown(insight: Mapping[str, Any]) -> str:
    """Describe exactly the article's displayed sources, without another model call."""
    sources = _Sources()
    view = _Insight(insight, sources)
    if not view.render(1) or not sources.documents:
        return ""
    explicit = {item.get("document_id"): item.get("summary", {})
                for item in insight.get("source_summaries", []) if isinstance(item, Mapping)}
    factual = [claim for claim in _nested_claims(insight)
               if claim.get("basis") in {"source_fact", "bank_position"}]
    lines = ["# Источники", "", "> **Сгенерировано ИИ**", ""]
    for document in sources.documents:
        key = _source_key(document)
        label = sources.labels[key]
        address = _safe_url(document.get("url"))
        title = _source_title(document) or address
        if not title:
            continue
        link = f"[{_text(title)}]({address})" if address else _text(title)
        lines.extend([f"## [{label}] {link}", ""])
        description = ""
        summary = explicit.get(document.get("document_id"))
        if summary and summary.get("basis") in {"source_fact", "bank_position"} and not summary.get("company_fields"):
            documents = view.documents(summary)
            if documents and all(_source_key(doc) == key for doc in documents):
                description = _brief(summary.get("text"))
        if not description:
            texts = []
            for claim in factual:
                documents = view.documents(claim)
                if documents and all(_source_key(doc) == key for doc in documents):
                    text = _narrative(claim.get("text"))
                    if text and text not in texts:
                        texts.append(text)
            description = _brief(" ".join(texts))
        if not description:
            # A legacy result may have only a mixed-source interpretation.
            # In that case show the exact cited passage instead of inventing a synopsis.
            quotes = [citation.get("quote") for citation in document.get("citations", [])]
            description = _brief(next((quote for quote in quotes if _narrative(quote)), ""))
        if description:
            lines.extend([_text(description), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_markdown_articles(result: Mapping[str, Any]) -> list[str]:
    """Return independent articles, each with its own AI badge and sources."""
    return [
        markdown for insight in result.get("insights", [])
        if (markdown := render_insight_markdown(insight))
    ]
