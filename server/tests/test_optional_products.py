"""Exercise optional bank offers through planning, validation and export."""
import json
import unittest
from unittest.mock import Mock

from insides.generation import generate_insights
from insides.products import load_product_catalog
from insides.schemas import GenerationResult


class OptionalProductTests(unittest.TestCase):
    def run_generation(self, with_product=False, invalid_product=False):
        texts = [
            'Поставщик сократил отсрочку платежа по новым договорам.',
            'Компания запланировала закупку дополнительной партии сырья.',
        ]
        payload = {
            'status': 'completed',
            'company_input': {'industry': 'Производство'},
            'topics': {'news': [
                {'document_id': f'd{i}', 'version_id': f'v{i}', 'chunk_id': f'c{i}',
                 'source_type': 'news', 'title': f'Договоры и закупки {i}',
                 'text': text, 'quality': 'verified', 'published_at': '2026-10-26'}
                for i, text in enumerate(texts, 1)
            ]},
        }
        events = [
            {'text': text, 'basis': 'source_fact',
             'evidence': [{'quote_id': f'q{i:04d}'}], 'company_fields': []}
            for i, text in enumerate(texts, 1)
        ]
        inference = {
            'text': 'Если закупки совпадут с сокращением отсрочки, может вырасти потребность в оборотных средствах.',
            'basis': 'model_inference',
            'evidence': [{'quote_id': 'q0001'}, {'quote_id': 'q0002'}],
            'company_fields': ['industry'],
        }
        article = {
            'audience_type': 'cfo', 'audience_rationale': 'Оценить влияние условий закупки на финансовый план.',
            'category_id': 1, 'title': 'Сокращение отсрочки меняет план закупок',
            'primary_document_id': 'd1', 'source_document_ids': ['d1', 'd2'],
            'events': events, 'synthesis': inference,
            'why_important_for_company': [inference],
            'possible_consequences': [{'kind': 'risk', 'claim': inference,
                                       'conditions': ['Если закупки совпадут по срокам'], 'horizon': None}],
            'relevant_actions': [{'kind': 'action', 'action': 'Проверить договор и пересмотреть план закупок.',
                                  'rationale': inference, 'checks': ['Сопоставить сроки платежей']}],
            'bank_assessment': {'status': 'insufficient_evidence', 'bank_statements': [],
                                'model_interpretation': None, 'limitations': ['Банковские оценки не использованы.']},
            'product_recommendations': [],
        }
        if with_product:
            product = load_product_catalog()['products'][0]
            article['product_recommendations'] = [{
                'product_id': 'unknown' if invalid_product else product['product_id'],
                'problem': inference, 'capability_quote': product['description'],
                'mechanism': 'Поможет профинансировать закупку сырья при сокращении отсрочки.',
                'application': 'Сравнить условия финансирования закупки с планом платежей.',
                'conditions': [product['applicability']],
            }]
        plan = {'groups': [{
            'title': article['title'], 'angle': inference['text'],
            'events': [{'text': event['text'], 'evidence': event['evidence']} for event in events],
        }]}
        client = Mock()
        client.usage = {}
        client.complete.side_effect = [json.dumps(plan), json.dumps(article)]
        result = generate_insights(payload, client, audience_type='cfo', max_repairs=0)
        return GenerationResult.model_validate(result).model_dump()

    def test_no_product_is_accepted_with_useful_action_and_no_offer(self):
        result = self.run_generation()
        self.assertEqual(len(result['insights']), 1, result['errors'])
        # One supplied group misses the separate five-insight requirement;
        # it must not be rejected for lacking a product.
        self.assertEqual([error['stage'] for error in result['errors']], ['quantity_requirement'])
        insight = result['insights'][0]
        self.assertEqual(insight['product_recommendations'], [])
        self.assertIn('Проверить договор и пересмотреть план закупок.', insight['markdown'])
        self.assertNotIn('Решение от Альфа-Банка', insight['markdown'])
        self.assertTrue(insight['validation']['product_recommendations_optional'])
        self.assertEqual(result['generation_policy']['minimum_products_per_insight'], 0)
        completeness = result['self_check']['completeness']
        self.assertEqual(completeness['required_products_per_insight'], 0)
        self.assertEqual(completeness['insights_without_products'], 1)
        self.assertEqual(completeness['insights_with_products'], 0)

    def test_offer_remains_separate_and_catalog_validation_still_applies(self):
        result = self.run_generation(with_product=True)
        self.assertEqual(len(result['insights']), 1, result['errors'])
        markdown = result['insights'][0]['markdown']
        self.assertLess(markdown.index('Что можно сделать'), markdown.index('Решение от Альфа-Банка'))
        self.assertLess(markdown.index('Решение от Альфа-Банка'), markdown.index('## Источники'))
        invalid = self.run_generation(with_product=True, invalid_product=True)
        self.assertEqual(invalid['insights'], [])
        self.assertIn('product_id', invalid['errors'][0]['message'])
