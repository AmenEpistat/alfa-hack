import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

test('locked npm tarballs and project registry use the public npm host', () => {
  const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'));
  const entries = Object.values(lock.packages) as { resolved?: string }[];
  const urls = entries.flatMap(entry => entry.resolved ? [new URL(entry.resolved)] : []);
  assert.ok(urls.length > 100);
  assert.deepEqual([...new Set(urls.map(url => `${url.protocol}//${url.host}`))], ['https://registry.npmjs.org']);
  assert.match(readFileSync(new URL('../.npmrc', import.meta.url), 'utf8'), /^registry=https:\/\/registry\.npmjs\.org\//m);
});
