"""Answers over the supplied purchase plan. This module does not call an LLM."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from .metadata import SOURCES
from .schemas import AnalysisView, AskResponse


def requested_view(question: str, current: AnalysisView) -> AnalysisView:
    values = current.model_dump()
    for pattern, company in [(r"вс[еяй].*групп|по компани|сравн.*компани", "group"),
                             ("инфраструкт", "infrastructure"), ("девелоп", "development"), ("подряд", "contracting")]:
        if re.search(pattern, question):
            values["company_id"] = company
            break
    for pattern, period in [("октябр", "october"), ("ноябр", "november"), ("декабр", "december"), ("квартал", "quarter")]:
        if pattern in question:
            values["period"] = period
            break
    rate = re.search(r"([+−–-]?\d+(?:[.,]\d+)?)\s*(?:%|процент)", question)
    if rate:
        value = float(rate[1].replace(",", ".").replace("−", "-").replace("–", "-"))
        if re.search(r"сни[жз]|упад|паден|дешев", question):
            value = -abs(value)
        values["price_change_pct"] = value
    return AnalysisView.model_validate(values)


def money(value):
    return f"{value:,.0f}".replace(",", " ") + " ₽"


def prepare_answer(payload, db, calculate):
    question = payload.question.strip().lower().replace("ё", "е")
    # Reject unavailable periods before interpreting numbers as scenario inputs.
    market_question = re.search(r"источник|worldsteel|спрос|рынок", question)
    unsupported_period = not market_question and re.search(r"\b20\d{2}\b|январ|феврал|март|апрел|\bма[йяе]\b|июн|июл|август|сентябр|прошл.*квартал|следующ.*квартал", question.replace("2026", ""))
    try:
        view = requested_view(question, payload.view)
    except ValueError:
        return AskResponse(question=payload.question, kind="unsupported", paragraphs=["Укажите изменение цены от −30 до +30%."], content="Укажите изменение цены от −30 до +30%.", context="Сценарий не изменён", references=[])
    analysis = calculate(view, db)
    period = {"quarter": "IV квартал 2026", "october": "Октябрь 2026", "november": "Ноябрь 2026", "december": "Декабрь 2026"}[view.period]
    company = "Вся группа" if view.company_id == "group" else analysis.rows[0].name
    context = f"{company} · {period} · цена {view.price_change_pct:+g}%"
    kind, paragraphs, citations = "unsupported", [], {}

    if unsupported_period:
        paragraphs = ["В плане есть только октябрь, ноябрь и декабрь 2026 года. Для другого периода данных нет."]
    elif re.search(r"курс|доллар|кредит|прибыл|марж|выручк|дивиденд|погод|крипт", question):
        paragraphs = ["В этих материалах нет данных для такого вывода. Доступны план закупок стали, объёмы и условия фиксации цены."]
    elif re.search(r"вероятност|гаранти|точно.*подорож|будет ли.*рост", question):
        paragraphs = ["Обзор worldsteel описывает спрос на сталь, а не вероятность изменения вашей закупочной цены. Процент в расчёте — сценарное допущение."]
        citations = {0: ["market"]}
    elif re.search(r"срок|актуал|устаре|пересмотр", question):
        kind = "validity"
        expired = datetime.now(ZoneInfo("Europe/Moscow")) >= datetime(2026, 10, 30, tzinfo=ZoneInfo("Europe/Moscow"))
        paragraphs = ["Срок актуальности истёк: вывод нужно проверить заново." if expired else "Вывод нужно пересмотреть до 30 октября 2026 года.", "При изменении договора, цены поставщика или плана закупок пересмотр нужен раньше."]
    elif re.search(r"почему.*(мне|нас|мо|нам)|что.*знач.*(бизнес|нас|меня)|как.*(касается|затрагивает)|отрасл|профил|релевант", question):
        kind = "relevance"
        paragraphs = ["В профиле группы указано строительство. Поэтому закупки стали могут влиять на расходы компаний группы.", "Размер влияния зависит от плана закупок и условий конкретного договора."]
        citations = {0: ["profile"]}
    elif re.search(r"источник|worldsteel|рын[ок]|прогноз", question):
        kind = "source"
        paragraphs = ["Обзор worldsteel описывает мировой спрос на сталь. Он не подтверждает рост цены в конкретном договоре.", "Для расчёта расходов используются объёмы и цены из плана закупок клиента в Альфа-Банке."]
        citations = {0: ["market"], 1: ["plan"]}
    elif re.search(r"что делать|следующ|начать|действ|рекоменд", question):
        kind = "actions"
        paragraphs = ["Проверьте ближайшие заказы без фиксированной цены: объём, дату поставки и право поставщика пересмотреть стоимость.", "Запросите актуальные условия и согласуйте изменения бюджета до размещения заказа."]
    elif re.search(r"сравн|по компани", question):
        kind = "comparison"
        view = view.model_copy(update={"company_id": "group"})
        analysis = calculate(view, db)
        context = f"Вся группа · {period} · цена {view.price_change_pct:+g}%"
        paragraphs = [f"{row.name}: без фиксации {money(row.exposed_budget)}, изменение бюджета {money(row.delta)}." for row in analysis.rows]
        citations = {index: ["plan"] for index in range(len(paragraphs))}
    elif re.search(r"расч|бюдж|сумм|цен|стоит|сколько|договор|фиксац|октябр|ноябр|декабр|квартал|подряд|девелоп|инфраструкт|%", question):
        kind = "calculation"
        total = analysis.total
        paragraphs = [f"В выбранном плане закупки без фиксированной цены составляют {money(total.exposed_budget)} ({total.open_volume:g} т).", f"При изменении цены на {view.price_change_pct:+g}% бюджет изменится на {money(total.delta)}. Расчёт: {money(total.exposed_budget)} × {view.price_change_pct:g}%.", "Закупки с фиксированной ценой исключены. Это сценарий, а не прогноз цены поставщика."]
        citations = {0: ["plan"], 1: ["plan"]}
    else:
        paragraphs = ["По этому вопросу в материалах недостаточно данных. Можно уточнить расчёт закупок, условия фиксации цены или источники вывода."]

    references = list(dict.fromkeys(source for ids in citations.values() for source in ids))
    content = "\n\n".join(text + "".join(f" [{SOURCES[source]['label']}](source:{source})" for source in citations.get(index, [])) for index, text in enumerate(paragraphs))
    return AskResponse(question=payload.question, kind=kind, paragraphs=paragraphs, content=content,
                       context=context, references=references, citations=citations,
                       suggested_view=view if kind != "unsupported" and view != payload.view else None,
                       generation_method="rules")
