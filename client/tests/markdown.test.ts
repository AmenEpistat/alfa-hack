import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MarkdownBody, safeMarkdownUrl } from '../src/shared/ui/markdown/MarkdownBody';

test('Markdown renders structured content and safe citations without raw HTML or remote images', () => {
  const text = '## Вывод\n\n**Важно**\n\n- Договор\n- Цена\n\n| Объём | Цена |\n|---|---|\n| 100 | 60 |\n\n[План](source:plan)\n\n<script>alert(1)</script>\n\n![tracking](https://example.com/image)\n\n[bad](javascript:alert%281%29)';
  const html = renderToStaticMarkup(createElement(MarkdownBody, { children: text, renderCitation: id => createElement('button', {}, `Источник ${id}`) }));
  assert.match(html, /<h2>Вывод<\/h2>/); assert.match(html, /<strong>Важно<\/strong>/);
  assert.match(html, /<li>Договор<\/li>/); assert.match(html, /<table>/);
  assert.match(html, /Источник plan/);
  assert.doesNotMatch(html, /<script|<img|href="javascript/);
  assert.equal(safeMarkdownUrl('data:text/html,hi'), '');
  assert.equal(safeMarkdownUrl('//example.com'), '');
  assert.equal(safeMarkdownUrl('source:plan'), '');
  assert.equal(safeMarkdownUrl('source:plan', true), 'source:plan');
});

test('actual ML product marker becomes a distinct bank offer and sources stay outside it', () => {
  const markdown = 'Обоснованный аналитический вывод.\n\n**Решение от Альфа-Банка**\n\n**[Факторинг](https://alfabank.ru/corporate/credit/factoring/)** — вариант для работы с отсрочкой.\n\nУсловия применения: согласовать с банком.\n\n## Источники\n\n- Аналитический отчёт.';
  const html = renderToStaticMarkup(createElement(MarkdownBody, { children: markdown }));
  assert.match(html, /<aside[^>]*bank-product/);
  assert.match(html, /Предложение Альфа-Банка/);
  assert.ok(html.indexOf('Обоснованный аналитический вывод') < html.indexOf('<aside'));
  assert.ok(html.indexOf('</aside>') < html.indexOf('Источники'));
  assert.match(html, /https:\/\/alfabank.ru\/corporate\/credit\/factoring\//);
  const plain = renderToStaticMarkup(createElement(MarkdownBody, { children: 'Позиция [Альфа-Банка](https://alfabank.ru/) в аналитическом обзоре.' }));
  assert.doesNotMatch(plain, /bank-product/);
});

test('heading form of bank offer is supported without swallowing next analytical section', () => {
  const html = renderToStaticMarkup(createElement(MarkdownBody, { children: '### Решение от Альфа-Банка\n\nПродукт.\n\n### Анализ\n\nАналитический вывод.' }));
  assert.match(html, /<aside/);
  assert.ok(html.indexOf('</aside>') < html.indexOf('Анализ'));
});

test('article presentation keeps original Markdown available and removes duplicated footer only with a source panel', async () => {
  const { articleBody } = await import('../src/shared/ui/markdown/bank-product');
  const markdown = '# Статья\n\n> **Сгенерировано ИИ**\n\n**Категория:** Финансы\n\nОсновной вывод.\n\n## Источники\n\n- [S1] Отчёт';
  assert.match(articleBody(markdown), /Источники/);
  assert.equal(articleBody(markdown, true).trim(), 'Основной вывод.');
  assert.match(markdown, /Сгенерировано ИИ/);
});
