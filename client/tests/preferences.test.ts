import assert from 'node:assert/strict';
import { test } from 'node:test';
import { insightPreferencesStore as preferences } from '../src/entities/insight/model/preferences-store';
import { insightId } from '../src/entities/insight/model/insight';

test('bookmarks remain independent, persist per user and retain legacy preferences', () => {
  const data = new Map<string, string>([['alfa-hackathon:steel-insight:v1', JSON.stringify({ saved: true, feedback: 'useful', taskCreated: true })]]);
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
  } });
  try {
    preferences.setUser('anna');
    assert.equal(preferences.isSaved(insightId), true);
    assert.equal(preferences.isSaved('price-fixation'), false);
    preferences.toggleSavedFor('price-fixation');
    preferences.toggleSavedFor('purchase-budget');
    preferences.setUser('ilya');
    assert.equal(preferences.isSaved('price-fixation'), false);
    assert.equal(preferences.isSaved(insightId), false);
    preferences.setUser('anna');
    assert.equal(preferences.isSaved('price-fixation'), true);
    assert.equal(preferences.isSaved('purchase-budget'), true);
    assert.equal(preferences.feedback, 'useful');
    assert.equal(preferences.taskCreated, true);
    preferences.toggleSavedFor('price-fixation');
    assert.equal(preferences.isSaved('purchase-budget'), true);
    assert.equal(preferences.isSaved(insightId), true);
    preferences.setUser(null);
    assert.equal(preferences.savedIds.length, 0);
    assert.equal(preferences.saved, false);
  } finally {
    if (descriptor) Object.defineProperty(globalThis, 'localStorage', descriptor);
    else Reflect.deleteProperty(globalThis, 'localStorage');
  }
});
