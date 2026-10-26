# Prepared seed articles were written with AI assistance; /ask currently uses rules.
# Keep generation provenance separate from ownership of the underlying data.
import re

SOURCES = {
    "market": {
        "id": "market", "label": "worldsteel", "publisher": "worldsteel.org", "origin": "external",
        "date": "12 октября 2026", "title": "worldsteel Short Range Outlook — October 2026",
        "description": "worldsteel ожидает почти неизменный мировой спрос на сталь в 2026 году и рост на 1,7% в 2027 году.",
        "scope": "Обзор описывает спрос. Он не подтверждает изменение цены в договоре поставщика.",
        "url": "https://worldsteel.org/media/press-releases/2026/worldsteel-short-range-outlook-october-2026/",
    },
    "plan": {
        "id": "plan", "label": "План закупок", "publisher": "Альфа-Банк", "origin": "client",
        "date": "22 октября 2026", "title": "Закупки стали · IV квартал 2026",
        "description": "Данные клиента в Альфа-Банке: объёмы закупок, фиксация цены и стоимость за тонну.",
        "scope": "Сценарий меняет цену только для закупок без фиксации. Процент задаёт пользователь.", "url": None,
    },
    "profile": {
        "id": "profile", "label": "Профиль группы", "publisher": "Альфа-Банк", "origin": "client",
        "date": None, "title": "ГК «Северстрой» · строительство",
        "description": "Данные клиента в Альфа-Банке: отрасль и состав группы компаний.",
        "scope": "Отрасль объясняет выбор темы. Для оценки расходов нужны план закупок и условия договоров.", "url": None,
    },
}


def insight_content(insight):
    section_sources = {
        "steel-cost": {1: ["market"], 2: ["plan"]},
        "price-fixation": {0: ["plan"]},
        "purchase-budget": {1: ["plan"]},
    }.get(insight.id, {})
    parts = []
    source_ids = []
    for index, section in enumerate(insight.sections):
        text = section.text
        for source_id in section_sources.get(index, []):
            if f"source:{source_id}" not in text:
                # Keep a trailing Markdown table/list/code block intact.
                separator = "\n\n" if "\n" in text else " "
                text += f"{separator}[{SOURCES[source_id]['label']}](source:{source_id})"
        for source_id in re.findall(r"\]\(source:([a-z0-9_-]+)\)", text):
            if source_id in SOURCES and source_id not in source_ids:
                source_ids.append(source_id)
        parts.append(f"## {section.title}\n\n{text}")
    return "\n\n".join(parts), source_ids


def generation_method(insight_id):
    return "ai_assisted" if insight_id in {"steel-cost", "price-fixation", "purchase-budget"} else "editorial"
