import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseInsight, parseAnswer, parseSources, toServerView } from '../src/entities/insight/api/insights-api';
import { apiRequest, setAccessToken, normalizeApiBase, ApiError } from '../src/shared/api/request';

test('backend fields and Markdown survive adaptation without reading-time metadata', () => {
  const entry = parseInsight({ id: 'steel-cost', topic: 'Рынок', title: 'Сталь', summary: 'Сводка', cover: 'steel', content: '**Вывод**\n\n- Договор', source_ids: ['plan'], prepared_at: '2026-10-22', expires_at: '2026-10-30', generation_method: 'ai_assisted', is_saved: true });
  assert.equal(entry.content, '**Вывод**\n\n- Договор');
  assert.deepEqual(entry.sourceIds, ['plan']); assert.equal(entry.generationMethod, 'ai_assisted');
  assert.equal(entry.isSaved, true); assert.equal(entry.expiresAt, '2026-10-30');
  assert.equal('minutes' in entry, false);
  assert.throws(() => parseInsight({ id: '', title: 'x' } as never));
  const answer = parseAnswer({ question: 'Октябрь', paragraphs: ['Ответ'], content: 'Ответ [План](source:plan)', context: 'Октябрь', references: ['plan'], generation_method: 'rules', suggested_view: { company_id: 'infrastructure', period: 'october', price_change_pct: 15 } });
  assert.equal(answer.generationMethod, 'rules');
  assert.deepEqual(toServerView(answer.suggestedView!), { company_id: 'infrastructure', period: 'october', price_change_pct: 15 });
});

test('API base and authenticated transport follow contract and report errors', async () => {
  assert.equal(normalizeApiBase('http://localhost:8000'), 'http://localhost:8000/api');
  assert.equal(normalizeApiBase('/api/'), '/api');
  assert.throws(() => normalizeApiBase('javascript:alert(1)'));
  const original = globalThis.fetch;
  try {
    setAccessToken('anna');
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/insights');
      assert.equal(new Headers(options?.headers).get('Authorization'), 'Bearer anna');
      return new Response(JSON.stringify({ detail: 'Инсайт не найден.' }), { status: 404 });
    };
    await assert.rejects(apiRequest('/insights'), (error: unknown) => error instanceof ApiError && error.status === 404 && error.message === 'Инсайт не найден.');
    globalThis.fetch = async () => { throw new Error('offline'); };
    await assert.rejects(apiRequest('/insights'), /Не удалось связаться/);
  } finally { globalThis.fetch = original; setAccessToken(null); }
});


test('source provenance is separate from generation and unsafe source links are rejected', () => {
  const source = { id: 'plan', label: 'План', publisher: 'Альфа-Банк', origin: 'client', url: null } as const;
  assert.equal(parseSources([source as never])[0].origin, 'client');
  assert.throws(() => parseSources([{ ...source, url: 'javascript:alert(1)' } as never]));
});

test('category metadata and cover URLs come from API; unsafe URLs are not used', async () => {
  const { resolveApiAssetUrl } = await import('../src/shared/api/request');
  const entry = parseInsight({ id: 'x', title: 'Заголовок', summary: 'Сводка', topic: 'Финансы', cover: 'budget', content: 'Текст', category_id: 'finance-rates', category_name: 'Финансы и ставки', cover_url: '/api/assets/insight-categories/finance-rates.svg', cover_background: '#d7e1cb' });
  assert.equal(entry.categoryId, 'finance-rates');
  assert.equal(entry.coverUrl, '/api/assets/insight-categories/finance-rates.svg');
  assert.equal(entry.coverBackground, '#d7e1cb');
  assert.equal(resolveApiAssetUrl('javascript:alert(1)'), undefined);
  assert.equal(resolveApiAssetUrl('//other.example/image.svg'), undefined);
});

test('ML numeric category IDs and role metadata are preserved', () => {
  const entry = parseInsight({ id: 'ml-1', title: 'Инсайт', summary: 'Вывод', topic: 'Валюты', cover: 'currencies_international_payments', category_id: 2, category_name: 'Валюты и международные расчеты', cover_url: '/api/assets/insight-categories/currencies-payments.svg', content: '# Инсайт', audience_type: 'treasury_head', generation_method: 'ai' });
  assert.equal(entry.categoryId, 2);
  assert.equal(entry.audienceType, 'treasury_head');
  assert.equal(entry.coverUrl, '/api/assets/insight-categories/currencies-payments.svg');
  const docs = parseSources([{ id: 'doc-5af', label: 'Обзор', publisher: 'Альфа-Банк', origin: 'bank', date: null, title: 'Обзор', description: 'Документ', scope: 'Источник', url: null }]);
  assert.equal(docs[0].origin, 'bank');
});
