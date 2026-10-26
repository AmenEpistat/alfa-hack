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
  assert.equal(source[1].publisher, 'Синтетические данные');
  assert.equal((await staticDemoResponse('/insights/ask', { method: 'POST', body: '{}' }, 'anna')).status, 503);
});

test('saved state in the static preview is separate for the two accounts', async () => {
  const result = await (await staticDemoResponse('/preferences/steel-cost/toggle', { method: 'POST' }, 'anna')).json();
  assert.equal(result.is_saved, true);
  const other = await (await staticDemoResponse('/insights/steel-cost', {}, 'ilya')).json();
  assert.equal(other.is_saved, false);
  assert.equal((await (await staticDemoResponse('/preferences', {}, 'anna')).json())[0].is_saved, true);
  await staticDemoResponse('/preferences/steel-cost/toggle', { method: 'POST' }, 'anna');
});
