import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_tmp = tempfile.TemporaryDirectory(prefix='alfa-api-tests-')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_tmp.name) / 'test.db')
from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy import select, create_engine, text, inspect
from app.main import app
from app.database import SessionLocal
from app.models import Insight, GeneratedInsight, InsightSection
from app.seed import seed_users, seed_insights
from app.categories import CATEGORIES, resolve_category
from app.publication import store_generated_insights
from app.migrations import ensure_legacy_company_columns
from insides.products import load_product_catalog
from insides.markdown import render_insight_markdown


def generation(audience='cfo', category=1):
    ref = {'evidence_id': 'E1', 'quote': 'Стоимость финансирования влияет на бюджет.'}
    claim = {'text': 'Стоимость финансирования влияет на бюджет.', 'basis': 'bank_position', 'evidence': [ref]}
    product = load_product_catalog()['products'][0]
    article = {'insight_id': 'test-source', 'title': 'Контроль бюджета' if audience == 'cfo' else 'Платёжный календарь',
               'audience_type': audience, 'category_id': category, 'lead': claim,
               'events': [claim], 'synthesis': claim,
               'foundation': {'documents': [{'document_id': 'bank-doc', 'title': 'Отчёт банка', 'source_type': 'alpha_pdf', 'citations': [ref]}]},
               'product_recommendations': [{'product': product, 'mechanism': 'Поддержать планирование.', 'application': 'Обсудить условия с банком.', 'problem': claim, 'conditions': []}]}
    article['markdown'] = render_insight_markdown(article)
    return {'target_audience': {'type': audience}, 'generated_at': '2026-10-26T10:00:00+03:00',
            'company_input': {'company_id': 'company-1'}, 'status': 'completed', 'insights': [article]}


def small_seed(db):
    seed_users(db); seed_insights(db); db.commit()


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        with patch('app.main.seed_database', small_seed):
            cls.client.__enter__()
        cls.auth = {'Authorization': 'Bearer anna'}
        cls.ilya = {'Authorization': 'Bearer ilya'}

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        _tmp.cleanup()

    def setUp(self):
        with SessionLocal() as db:
            db.query(GeneratedInsight).delete()
            db.query(Insight).filter(Insight.id.like('ml-%')).delete()
            db.commit()

    def publish(self, audience='cfo', category=1, run='test'):
        with SessionLocal() as db:
            return store_generated_insights(db, generation(audience, category), 'anna' if audience == 'cfo' else 'ilya', run)[0]

    def test_exactly_two_accounts_with_server_audiences(self):
        self.assertEqual(self.client.get('/api/insights').status_code, 401)
        users = self.client.get('/api/auth/users').json()
        self.assertEqual({u['id']: u['audience_type'] for u in users}, {'anna': 'cfo', 'ilya': 'treasury_head'})
        login = self.client.post('/api/auth/login', json={'user_id': 'anna'}).json()
        self.assertEqual(login['access_token'], 'anna')
        self.assertEqual(login['user']['audience_type'], 'cfo')
        self.assertEqual(self.client.get('/api/auth/me?token=ilya').json()['audience_type'], 'treasury_head')

    def test_shared_seed_content_contract(self):
        items = self.client.get('/api/insights', headers=self.auth).json()
        self.assertEqual(len(items), 3)
        self.assertTrue(all(i['audience_type'] is None for i in items))
        detail = self.client.get('/api/insights/steel-cost', headers=self.auth).json()
        self.assertIn('## ', detail['content'])
        self.assertEqual(detail['category_id'], 3)
        self.assertEqual(detail['generation_method'], 'ai_assisted')

    def test_all_ten_categories_match_ml_numeric_id_slug_and_image_key(self):
        import xml.etree.ElementTree as ET
        categories = self.client.get('/api/insights/meta/categories', headers=self.auth).json()
        self.assertEqual(len(categories), 10)
        for expected_id, category in enumerate(categories, 1):
            self.assertEqual(category['id'], expected_id)
            self.assertEqual(resolve_category(category['slug']), category)
            self.assertEqual(resolve_category(category['image_key']), category)
            image = self.client.get(category['cover_url'])
            self.assertEqual(image.status_code, 200)
            root = ET.fromstring(image.text)
            self.assertEqual(root.attrib['viewBox'], '0 0 600 340')
        for value in (0, 11, True, '3', [], None):
            self.assertIsNone(resolve_category(value))

    def test_role_feeds_are_different_but_shared_links_open_for_both_accounts(self):
        anna_id = self.publish('cfo', 1, 'cfo-run')
        ilya_id = self.publish('treasury_head', 2, 'treasury-run')
        anna = self.client.get('/api/insights', headers=self.auth).json()
        ilya = self.client.get('/api/insights', headers=self.ilya).json()
        self.assertEqual([i['id'] for i in anna], [anna_id])
        self.assertEqual([i['id'] for i in ilya], [ilya_id])
        self.assertNotEqual(anna[0]['title'], ilya[0]['title'])
        self.assertEqual(ilya[0]['category_id'], 2)
        self.assertIn('currencies-payments.svg', ilya[0]['cover_url'])
        shared = self.client.get('/api/insights/'+anna_id, headers=self.ilya)
        self.assertEqual(shared.status_code, 200)
        self.assertEqual(shared.json()['id'], anna_id)
        self.assertEqual(shared.json()['audience_type'], 'cfo')
        self.assertEqual(self.client.post('/api/preferences/'+anna_id+'/toggle', headers=self.ilya).status_code, 200)
        self.assertFalse(self.client.get('/api/insights/'+anna_id, headers=self.auth).json()['is_saved'])
        sources = self.client.get('/api/insights/'+anna_id+'/sources', headers=self.ilya)
        self.assertEqual(sources.status_code, 200)
        self.assertEqual(sources.json()[0]['publisher'], 'Альфа-Банк')

    def test_pipeline_publication_persists_role_and_markdown(self):
        result = {'status': 'completed', 'run_id': 'pipeline-fixture', 'insights': generation()}
        with patch('app.routers.pipeline.handle_request', return_value=result) as handler:
            response = self.client.post('/api/pipeline/run', headers=self.auth, json={'action': 'generate', 'audience_type': 'cfo', 'company_id': 'company-1', 'ranking_input': {}})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(handler.call_args[0][0]['audience_type'], 'cfo')
        identifier = response.json()['published_insight_ids'][0]
        item = self.client.get('/api/insights/'+identifier, headers=self.auth).json()
        self.assertIn('**Решение от Альфа-Банка**', item['content'])
        self.assertIn('source:doc-', item['content'])
        self.assertEqual(item['generation_method'], 'ai')
        self.assertTrue(item['product_recommendations'])
        self.assertIsNone(item['expires_at'])  # No invented ML expiry.
        source = next(s for s in self.client.get('/api/insights/meta/sources', headers=self.auth).json() if s['id'].startswith('doc-'))
        self.assertEqual(source['origin'], 'bank')
        self.assertEqual(source['publisher'], 'Альфа-Банк')
        self.assertTrue(source['excerpts'])

    def test_cached_generation_does_not_duplicate_feed_on_new_pipeline_run(self):
        result = generation()
        result['run_id'] = 'stable-generation'
        with SessionLocal() as db:
            first = store_generated_insights(db, result, 'anna', 'pipeline-first')
            second = store_generated_insights(db, result, 'anna', 'pipeline-second')
            self.assertEqual(first, second)
            self.assertEqual(db.query(GeneratedInsight).count(), 1)

    def test_role_spoofing_is_rejected_before_ml_call(self):
        with patch('app.routers.pipeline.handle_request') as handler:
            response = self.client.post('/api/pipeline/run', headers=self.auth, json={'action': 'generate', 'audience_type': 'treasury_head', 'company_id': 'company-1', 'ranking_input': {}})
            self.assertEqual(response.status_code, 403)
            handler.assert_not_called()
        with SessionLocal() as db:
            malformed = generation()
            malformed['insights'][0]['audience_type'] = 'treasury_head'
            with self.assertRaises(ValueError):
                store_generated_insights(db, malformed, 'anna', 'bad')
            self.assertEqual(db.query(GeneratedInsight).count(), 0)

    def test_generated_chat_uses_server_article_role_and_history(self):
        from app.routers.agent import InsightChatResponse
        identifier = self.publish()
        answer = InsightChatResponse(question='Почему?', paragraphs=['Подтверждённый ответ.'], context='По отчёту банка', references=['bank-doc'], citations={0: ['bank-doc']})
        with patch('app.routers.agent.chat', return_value=answer) as chat:
            response = self.client.post('/api/insights/ask', headers=self.auth, json={'insight_id': identifier, 'question': 'Почему?', 'history': [{'role': 'user', 'content': 'Контекст'}]})
            self.assertEqual(response.status_code, 200, response.text)
            sent = chat.call_args[0][0]
            self.assertEqual(sent.audience_type, 'cfo')
            self.assertEqual(sent.insight['title'], 'Контроль бюджета')
            self.assertEqual(sent.history[0].content, 'Контекст')
            self.assertEqual(response.json()['generation_method'], 'ai')
            self.assertIn('(source:doc-', response.json()['content'])
        with patch('app.routers.agent.chat', return_value=answer) as chat:
            response = self.client.post('/api/insights/ask', headers=self.ilya, json={'insight_id': identifier, 'question': 'Почему?'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(chat.call_args[0][0].audience_type, 'treasury_head')

    def test_user_preferences_are_independent_and_feedback_can_be_cleared(self):
        path = '/api/preferences/steel-cost/toggle'
        first = self.client.post(path, headers=self.auth).json()['is_saved']
        other = self.client.get('/api/insights/steel-cost', headers=self.ilya).json()['is_saved']
        self.assertFalse(other)
        self.assertEqual(self.client.get('/api/insights/steel-cost', headers=self.auth).json()['is_saved'], first)
        body = {'insight_id': 'steel-cost', 'feedback': 'useful'}
        self.assertEqual(self.client.post('/api/preferences/feedback', headers=self.auth, json=body).json()['feedback'], 'useful')
        body['feedback'] = None
        self.assertIsNone(self.client.post('/api/preferences/feedback', headers=self.auth, json=body).json()['feedback'])

    def test_migration_preserves_existing_company(self):
        engine = create_engine('sqlite://')
        with engine.begin() as con:
            con.execute(text('CREATE TABLE companies (id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL)'))
            con.execute(text("INSERT INTO companies VALUES ('old', 'Существующая компания')"))
        ensure_legacy_company_columns(engine)
        ensure_legacy_company_columns(engine)
        self.assertTrue({'data', 'created_at', 'updated_at'} <= {c['name'] for c in inspect(engine).get_columns('companies')})
        with engine.connect() as con:
            self.assertEqual(con.execute(text('SELECT name FROM companies')).scalar(), 'Существующая компания')


if __name__ == '__main__':
    unittest.main()
