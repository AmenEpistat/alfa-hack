import assert from 'node:assert/strict';
import { test } from 'node:test';
import { InsightPreferencesStore, type Preference, type PreferencesRequest } from '../src/entities/insight/model/preferences-store';
const saved: Preference = { insight_id: 'steel-cost', is_saved: true, feedback: null, reason: null };
const deferred = <T>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; };

test('preferences load from API and mutations keep server state', async () => {
  const calls: string[] = [];
  const store = new InsightPreferencesStore((async (path, options) => {
    calls.push(path);
    if (!options) return [saved];
    if (path.endsWith('/toggle')) return { ...saved, is_saved: false };
    const body = JSON.parse(options.body as string);
    return { ...saved, feedback: body.feedback, reason: body.reason };
  }) as PreferencesRequest);
  store.setUser('anna'); await store.load();
  assert.equal(store.isSaved('steel-cost'), true);
  await store.toggleSavedFor('steel-cost');
  assert.equal(store.isSaved('steel-cost'), false);
  await store.setFeedback('steel-cost', 'useful');
  assert.equal(store.feedbackFor('steel-cost'), 'useful');
  await store.setFeedback('steel-cost', 'useful');
  assert.equal(store.feedbackFor('steel-cost'), null);
  assert.deepEqual(calls, ['/preferences', '/preferences/steel-cost/toggle', '/preferences/feedback', '/preferences/feedback']);
});

test('stale response cannot leak previous user preferences', async () => {
  const response = deferred<Preference[]>();
  const store = new InsightPreferencesStore((() => response.promise) as PreferencesRequest);
  store.setUser('anna'); const pending = store.load(); store.setUser('ilya');
  response.resolve([saved]); await pending;
  assert.deepEqual(store.savedIds, []);
});

test('duplicate mutations are blocked and failed mutations do not change saved state', async () => {
  const response = deferred<Preference>(); let calls = 0;
  const store = new InsightPreferencesStore((async () => { calls++; return response.promise; }) as PreferencesRequest);
  store.setUser('anna'); const first = store.toggleSavedFor('steel-cost');
  await store.toggleSavedFor('steel-cost');
  assert.equal(calls, 1); assert.equal(store.pending['steel-cost'], true);
  response.resolve(saved); await first;
  assert.equal(store.isSaved('steel-cost'), true);
  const failed = new InsightPreferencesStore((async () => { throw new Error('Сервер недоступен'); }) as PreferencesRequest);
  failed.setUser('anna'); await failed.toggleSavedFor('steel-cost');
  assert.equal(failed.isSaved('steel-cost'), false);
  assert.equal(failed.errors['steel-cost'], 'Сервер недоступен');
  assert.equal(failed.pending['steel-cost'], false);
});
