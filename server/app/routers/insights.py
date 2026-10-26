from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..accounts import audience_for_user
from ..categories import CATEGORIES, category_for_insight, resolve_category
from ..database import get_db
from ..dependencies import get_user_id
from ..metadata import SOURCES, generation_method, insight_content
from ..models import Company, GeneratedInsight, Insight, PurchasePlan, QuestionHistory, UserPreference
from ..publication import visible_insights
from ..schemas import InsightResponse, InsightSection, AskRequest, AskResponse

router = APIRouter(prefix='/api/insights', tags=['insights'], dependencies=[Depends(get_user_id)])


def get_preference(db, user_id, insight_id):
    return db.scalar(select(UserPreference).where(UserPreference.user_id == user_id, UserPreference.insight_id == insight_id))


def source_records(record):
    from insides.markdown import source_document_id
    result = []
    for doc in (record.payload.get('foundation') or {}).get('documents') or []:
        source_id = source_document_id(doc)
        bank = doc.get('source_type') in {'alpha_pdf', 'bank', 'alfa_bank'}
        result.append({'id': source_id, 'label': doc.get('title') or 'Источник',
            'publisher': 'Альфа-Банк' if bank else 'Внешний источник', 'origin': 'bank' if bank else 'external',
            'date': doc.get('published_at'), 'title': doc.get('title') or 'Источник',
            'description': 'Аналитический материал Альфа-Банка.' if bank else 'Документ, использованный для этого инсайта.',
            'scope': 'Исходные утверждения и цитаты сохранены в составе результата ML.', 'url': doc.get('url'), 'excerpts': [c.get('quote') for c in doc.get('citations', []) if c.get('quote')]})
    return result


def serialize_insight(insight, saved=False, generated=None):
    category = resolve_category(generated.payload.get('category_id')) if generated else category_for_insight(insight)
    content, source_ids = insight_content(insight) if generated is None else (generated.payload['markdown'], [s['id'] for s in source_records(generated)])
    return InsightResponse(id=insight.id, topic=category['name'] if generated and category else insight.topic,
        title=insight.title, summary=insight.summary, minutes=insight.minutes, cover=insight.cover,
        category_id=category['id'] if category else None, category_name=category['name'] if category else None,
        cover_url=category['cover_url'] if category else None, cover_background=category['cover_background'] if category else None,
        sections=[InsightSection(title=s.title, text=s.text) for s in insight.sections], content=content, source_ids=source_ids,
        is_saved=saved, prepared_at=generated.prepared_at if generated else '2026-10-22T09:00:00+03:00',
        expires_at=generated.payload.get('expires_at') if generated else '2026-10-30T00:00:00+03:00',
        generation_method='ai' if generated else generation_method(insight.id),
        audience_type=generated.audience_type if generated else None,
        product_recommendations=generated.payload.get('product_recommendations', []) if generated else [])


@router.get('', response_model=list[InsightResponse])
def list_insights(user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    result = []
    for insight in visible_insights(db, user_id):
        pref = get_preference(db, user_id, insight.id)
        result.append(serialize_insight(insight, bool(pref and pref.is_saved), db.get(GeneratedInsight, insight.id)))
    return result


@router.get('/meta/categories')
def categories():
    return CATEGORIES


@router.get('/meta/sources')
def sources(user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    records = dict(SOURCES)
    for insight in visible_insights(db, user_id):
        generated = db.get(GeneratedInsight, insight.id)
        if generated:
            records.update({item['id']: item for item in source_records(generated)})
    return list(records.values())


@router.get('/meta/companies')
def companies(db: Session = Depends(get_db)):
    return [{'id': c.id, 'name': c.name} for c in db.scalars(select(Company).limit(100)).all()]


@router.get('/meta/profile')
def profile(user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    items = []
    for record in db.scalars(select(GeneratedInsight).where(GeneratedInsight.audience_type == audience_for_user(user_id))).all():
        company = db.get(Company, record.company_id) if record.company_id else None
        if record.company_id and not any(c['id'] == record.company_id for c in items):
            items.append({'id': record.company_id, 'name': company.name if company else record.company_id})
    return {'name': 'Мои компании', 'industry': '', 'source_id': 'profile', 'companies': items}


@router.get('/meta/purchase-plan')
def plan(db: Session = Depends(get_db)):
    return [{'company_id': p.company_id, 'company_name': p.company.name, 'month': p.month,
             'volume': p.volume, 'fixed_volume': p.fixed_volume, 'price': p.price}
            for p in db.scalars(select(PurchasePlan).options(selectinload(PurchasePlan.company))).all()]


@router.get('/export/purchase-plan.csv')
def export_plan(db: Session = Depends(get_db)):
    import csv, io
    out = io.StringIO(); writer = csv.writer(out, delimiter=';')
    writer.writerow(['Компания', 'Месяц', 'План, т', 'Фиксация, т', 'Цена, ₽/т'])
    for row in plan(db):
        writer.writerow([row['company_name'], row['month'], row['volume'], row['fixed_volume'], row['price']])
    return Response('\ufeff' + out.getvalue(), media_type='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename=purchase-plan.csv'})


@router.post('/ask', response_model=AskResponse)
def ask(payload: AskRequest, user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    insight = db.get(Insight, payload.insight_id)
    if insight is None:
        raise HTTPException(404, 'Инсайт не найден.')
    generated = db.get(GeneratedInsight, insight.id)
    if generated:
        from .agent import chat, InsightChatRequest
        response = chat(InsightChatRequest(question=payload.question, insight=generated.payload,
            audience_type=audience_for_user(user_id), history=payload.history), user_id=user_id)
        from insides.markdown import source_document_id
        docs = (generated.payload.get('foundation') or {}).get('documents', [])
        ids = {d.get('document_id'): source_document_id(d) for d in docs}
        paragraphs = response.paragraphs
        citations = {index: [ids[ref] for ref in refs if ref in ids] for index, refs in response.citations.items()}
        content = '\n\n'.join(p + ''.join(f' [Источник](source:{ref})' for ref in citations.get(i, [])) for i, p in enumerate(paragraphs))
        answer = AskResponse(question=payload.question, kind='source', paragraphs=paragraphs, context=response.context,
            content=content, references=list(dict.fromkeys(ref for refs in citations.values() for ref in refs)),
            citations=citations, generation_method='ai')
    else:
        # Shared seed articles have no live ML context; do not pretend to call an LLM.
        text = 'Для этой общей статьи нет сохранённого контекста ML. Уточняющий диалог доступен для сгенерированной подборки вашей роли.'
        answer = AskResponse(question=payload.question, kind='unsupported', paragraphs=[text], content=text,
                             context='Общая подборка', references=[], generation_method='rules')
    db.add(QuestionHistory(user_id=user_id, insight_id=insight.id, question=payload.question, answer=answer.content))
    db.commit()
    return answer


@router.get('/{insight_id}', response_model=InsightResponse)
def get_insight(insight_id: str, user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    insight = db.get(Insight, insight_id)
    if insight is None:
        raise HTTPException(404, 'Инсайт не найден.')
    pref = get_preference(db, user_id, insight_id)
    return serialize_insight(insight, bool(pref and pref.is_saved), db.get(GeneratedInsight, insight_id))


@router.get('/{insight_id}/sources')
def get_insight_sources(insight_id: str, db: Session = Depends(get_db)):
    insight = db.get(Insight, insight_id)
    if insight is None:
        raise HTTPException(404, 'Инсайт не найден.')
    generated = db.get(GeneratedInsight, insight_id)
    if generated:
        return source_records(generated)
    _, source_ids = insight_content(insight)
    return [SOURCES[source_id] for source_id in source_ids if source_id in SOURCES]
