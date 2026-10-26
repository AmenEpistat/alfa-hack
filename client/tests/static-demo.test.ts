import test from 'node:test';
import assert from 'node:assert/strict';
import { staticDemoResponse } from '../src/shared/api/static-demo';

test('Netlify preview has exactly two readable articles and no model endpoint', async () => {
  const users = await (await staticDemoResponse('/auth/users')).json();
  assert.deepEqual(users.map((user: { id: string }) => user.id), ['anna', 'ilya']);
  const login = await (await staticDemoResponse('/auth/login', { method: 'POST', body: JSON.stringify({ user_id: 'anna' }) })).json();
  assert.equal(login.access_token, 'anna');
  const articles = await (await staticDemoResponse('/insights', {}, 'anna')).json();
  assert.deepEqual(articles.map((article: { id: string }) => article.id), ['steel-cost', 'price-fixation']);
  const source = await (await staticDemoResponse('/insights/steel-cost/sources', {}, 'ilya')).json();
  assert.equal(source[0].origin, 'external');
  assert.equal(source[1].origin, 'synthetic');
  assert.equal(source[1].publisher, 'Синтетический план');
  assert.equal((await staticDemoResponse('/insights/ask', { method: 'POST', body: '{}' }, 'anna')).status, 503);
});

test('editorial articles differ by role and their figures reconcile to the visible synthetic plan', async () => {
  const anna = await (await staticDemoResponse('/insights/steel-cost', {}, 'anna')).json();
  const ilya = await (await staticDemoResponse('/insights/steel-cost', {}, 'ilya')).json();
  assert.notEqual(anna.title, ilya.title);
  assert.equal(anna.audience_type, 'cfo');
  assert.equal(ilya.audience_type, 'treasury_head');
  assert.equal(anna.generation_method, 'editorial');
  assert.match(anna.content, /6,39 млн ₽/);
  assert.match(ilya.content, /платёжный календарь/);
  assert.match(anna.content, /\[worldsteel\]\(source:market\)/);
  const rows = await (await staticDemoResponse('/insights/meta/purchase-plan', {}, 'anna')).json();
  assert.equal(rows.length, 9);
  const totals = rows.reduce((sum: { volume: number; fixed: number; openValue: number }, row: { volume: number; fixed_volume: number; price: number }) => ({
    volume: sum.volume + row.volume,
    fixed: sum.fixed + row.fixed_volume,
    openValue: sum.openValue + (row.volume - row.fixed_volume) * row.price,
  }), { volume: 0, fixed: 0, openValue: 0 });
  assert.deepEqual(totals, { volume: 2150, fixed: 1085, openValue: 63_900_000 });
  const csv = await (await staticDemoResponse('/insights/export/purchase-plan.csv', {}, 'anna')).text();
  assert.equal(csv.trim().split('\r\n').length, 10);
});

test('saved state in the static preview is separate for the two accounts', async () => {
  const result = await (await staticDemoResponse('/preferences/steel-cost/toggle', { method: 'POST' }, 'anna')).json();
  assert.equal(result.is_saved, true);
  const other = await (await staticDemoResponse('/insights/steel-cost', {}, 'ilya')).json();
  assert.equal(other.is_saved, false);
  assert.equal((await (await staticDemoResponse('/preferences', {}, 'anna')).json())[0].is_saved, true);
  await staticDemoResponse('/preferences/steel-cost/toggle', { method: 'POST' }, 'anna');
});
