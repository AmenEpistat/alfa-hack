"""Replay external boundaries, keeping orchestration, validation and persistence real."""
import copy
import json
import os
from pathlib import Path

from backend import InferenceService
from alpha_parser.config import Settings

FIXTURES = Path(__file__).parent / 'fixtures'


def settings():
    return Settings(_env_file=None, llm_base_url='http://synthetic.invalid',
                    llm_api_key='synthetic-not-a-secret', llm_model='fixture-v1',
                    allow_unknown_cost=True)


class FixtureClient:
    """A deterministic response fixture, NOT a language model."""
    def __init__(self, *args, **kwargs):
        self.usage = {'calls': 0, 'cost_rub': 0, 'synthetic': True}

    def complete(self, messages):
        self.usage['calls'] += 1
        data = json.loads(messages[-1]['content'])
        if 'question' in data:
            refs = [d['document_id'] for d in data['insight']['documents']]
            result = {'paragraphs': ['СИНТЕТИЧЕСКИЙ ОТВЕТ: проверьте сроки договора и план платежей. '
                                     'Это фиксированная тестовая реплика, а не ответ живой модели.'],
                      'context': 'Синтетический стенд', 'references': refs, 'citations': {'0': refs}}
        elif 'synthesis_group' not in data:
            docs = {d['document_id']: d for d in data['documents']}
            groups = []
            for i in range(1, 6):
                pair = [docs[f'demo-news-{i}'], docs[f'demo-analysis-{i}']]
                groups.append({
                    'title': f'СИНТЕТИЧЕСКИЙ ПРИМЕР {i}: проверка финансового плана',
                    'angle': f'Если события учебного сценария {i} совпадут, может потребоваться пересмотр плана платежей.',
                    'events': [{'text': d['passages'][0]['text'],
                                'evidence': [{'quote_id': d['passages'][0]['quote_id']}]} for d in pair],
                })
            result = {'groups': groups}
        else:
            group = data['synthesis_group']
            events = [{**e, 'basis': 'source_fact', 'company_fields': []} for e in group['events']]
            inference = {'text': group['angle'], 'basis': 'model_inference',
                         'evidence': [ref for e in events for ref in e['evidence']],
                         'company_fields': ['industry']}
            result = {
                'audience_type': data['target_audience']['type'],
                'audience_rationale': 'Учебная проверка финансового плана для выбранной роли.',
                'category_id': 1, 'title': group['title'],
                'primary_document_id': data['primary_document_id'],
                'source_document_ids': data['source_document_ids'],
                'events': events, 'synthesis': inference,
                'why_important_for_company': [inference],
                'possible_consequences': [{'kind': 'risk', 'claim': inference,
                                          'conditions': ['Если учебные события совпадут по срокам'], 'horizon': None}],
                'relevant_actions': [{'kind': 'action', 'action': 'Сопоставить договоры и учебный план платежей.',
                                      'rationale': inference, 'checks': ['Проверить сроки платежей']}],
                'bank_assessment': {'status': 'insufficient_evidence', 'bank_statements': [],
                                    'model_interpretation': None,
                                    'limitations': ['Все источники вымышлены; банковская аналитика не использована.']},
                'product_recommendations': [],
            }
        return json.dumps(result, ensure_ascii=False)


def fixture_ranker(source, companies):
    return {'run_id': source['run_id'], 'status': 'ok', 'diagnostics': {'synthetic': True},
            'sets': [{'set_id': f'demo-set-{i}', 'company': {'company_id': 'U_900001'},
                      'news': [{'item_id': f'demo-news-{i}'}],
                      'analytics': [{'item_id': f'demo-analysis-{i}'}],
                      'set_score': 1, 'warnings': ['Fixture selection; no neural ranking performed.']}
                     for i in range(1, 6)]}


class SyntheticService(InferenceService):
    def __init__(self, **kwargs):
        if os.environ.get('ALPHA_SYNTHETIC_WORKDIR'):
            work = Path(os.environ['ALPHA_SYNTHETIC_WORKDIR'])
            kwargs.setdefault('cache_dir', work / 'cache')
            kwargs.setdefault('output_dir', work / 'output')
        super().__init__(csv_path=FIXTURES / 'companies.csv', settings=settings(),
                         ranker=fixture_ranker, insight_client_factory=lambda *_: FixtureClient(), **kwargs)

    def _collect(self, module, request, profile, audience):
        source = json.loads((FIXTURES / 'sources.json').read_text())
        source['company_input'] = copy.deepcopy(profile)
        source['target_audience'] = audience
        return {'status': 'completed', 'synthetic': True, 'ranking_input': source}, source


def handle_request(payload):
    if payload.get('action', 'run') != 'run' or payload.get('company_id') != 'U_900001':
        from fastapi import HTTPException
        raise HTTPException(422, 'Synthetic stand accepts action=run and company_id=U_900001 only')
    if any(payload.get(key) is not None for key in ('profile', 'preprocessing', 'ranking_input', 'ranking_result')):
        from fastapi import HTTPException
        raise HTTPException(422, 'Synthetic stand uses bundled fixtures only')
    return SyntheticService().handle(payload)
