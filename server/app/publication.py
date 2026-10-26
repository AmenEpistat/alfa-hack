"""Publish accepted generation results into the same API the browser reads."""
import hashlib
from sqlalchemy import select
from .accounts import audience_for_user, require_audience
from .categories import resolve_category
from .models import GeneratedInsight, Insight


def store_generated_insights(db, result, user_id, run_id):
    articles = result.get('insights') or []
    if not articles:
        return []
    audience = (result.get('target_audience') or {}).get('type')
    require_audience(user_id, audience)
    accepted = []
    # Validate the whole batch before modifying the database.
    for item in articles:
        if item.get('audience_type') != audience:
            raise ValueError('Generated article targets another reader role')
        category = resolve_category(item.get('category_id'))
        if not category or not isinstance(item.get('markdown'), str) or not item['markdown'].strip() or not item.get('title'):
            raise ValueError('Generated article needs a valid category, title and Markdown')
        accepted.append((item, category))
    ids = []
    for item, category in accepted:
        source_run = result.get("run_id") or run_id
        key = f"{source_run}:{audience}:{item.get('insight_id', item['title'])}"
        identifier = 'ml-' + hashlib.sha256(key.encode()).hexdigest()[:32]
        lead = item.get('lead') or item.get('synthesis') or {}
        summary = lead.get('text', '') if isinstance(lead, dict) else str(lead)
        row = db.get(Insight, identifier)
        if row is None:
            row = Insight(id=identifier, topic=category['name'], title=item['title'], summary=summary, minutes=0, cover=category['slug'])
            db.add(row)
            db.flush()
        else:
            row.title, row.summary, row.topic, row.cover = item['title'], summary, category['name'], category['slug']
        payload = {**item, 'company_input': result.get('company_input') or item.get('company_input') or {}}
        company_id = payload['company_input'].get('company_id')
        record = db.get(GeneratedInsight, identifier)
        if record is None:
            record = GeneratedInsight(insight_id=identifier, audience_type=audience, company_id=company_id,
                                      run_id=run_id, prepared_at=result.get('generated_at'), payload=payload)
            db.add(record)
        else:
            record.payload, record.prepared_at = payload, result.get('generated_at')
        ids.append(identifier)
    db.commit()
    return ids


def visible_insights(db, user_id):
    generated = list(db.scalars(select(GeneratedInsight).where(GeneratedInsight.audience_type == audience_for_user(user_id))).all())
    if generated:
        return list(db.scalars(select(Insight).where(Insight.id.in_([g.insight_id for g in generated])).order_by(Insight.created_at.desc())).all())
    # Explicitly shared seed collection until this role has a generated result.
    return list(db.scalars(select(Insight).where(~Insight.id.in_(select(GeneratedInsight.insight_id))).order_by(Insight.created_at)).all())
