import assert from 'node:assert/strict';
import { test } from 'node:test';
import { calculateImpact, defaultAnalysisView, formatMoney, getPurchasePlanCsv, purchasePlan } from '../src/entities/insight/model/analysis';
import { answerInsightQuestion } from '../src/entities/insight/model/answer';
import { insightAnalysisStore } from '../src/entities/insight/model/analysis-store';
import { getInsightValidity } from '../src/entities/insight/model/validity';

test('validity is independent from purchasing period and expires at the Moscow deadline', () => {
  assert.equal(getInsightValidity(new Date('2026-10-22T12:00:00+03:00')).reviewDate, '29 октября');
  assert.equal(getInsightValidity(new Date('2026-10-29T23:59:59.999+03:00')).expired, false);
  assert.equal(getInsightValidity(new Date('2026-10-30T00:00:00+03:00')).expired, true);
  assert.equal(getInsightValidity(new Date('2027-01-01T00:00:00+03:00')).label, 'Срок актуальности истёк');
});

test('questions about expiry explain the review rule without switching purchasing periods', () => {
  const answer = answerInsightQuestion('До какой даты актуально решение?', defaultAnalysisView);
  assert.equal(answer.kind, 'validity');
  assert.match(answer.paragraphs.join(' '), /29 октября/);
  assert.match(answer.paragraphs.join(' '), /демо/);
  assert.equal(answer.suggestedView, undefined);
});

test('quarter totals reconcile to the nine purchase records and exclude fixed prices', () => {
  assert.equal(purchasePlan.length, 9);
  const { rows, total } = calculateImpact(defaultAnalysisView);
  assert.equal(rows.length, 3);
  assert.deepEqual(total, {
    volume: 2150, fixedVolume: 1085, openVolume: 1065,
    budget: 129_000_000, exposedBudget: 63_900_000, delta: 6_390_000,
  });
  assert.deepEqual(rows.map(row => row.delta), [3_210_000, 1_080_000, 2_100_000]);
});

test('October is a subset, and a company selection never includes sibling records', () => {
  assert.deepEqual(calculateImpact({ ...defaultAnalysisView, period: 'october' }).total, {
    volume: 650, fixedVolume: 280, openVolume: 370,
    budget: 39_000_000, exposedBudget: 22_200_000, delta: 2_220_000,
  });
  const { rows, total } = calculateImpact({ companyId: 'contracting', period: 'october', priceChangePct: 10 });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].id, 'contracting');
  assert.equal(total.openVolume, 40);
  assert.equal(total.delta, 240_000);
});

test('zero, negative and fractional scenarios do not change purchasing volumes', () => {
  assert.equal(calculateImpact({ ...defaultAnalysisView, priceChangePct: 0 }).total.delta, 0);
  assert.equal(calculateImpact({ ...defaultAnalysisView, priceChangePct: -5 }).total.delta, -3_195_000);
  assert.equal(calculateImpact({ ...defaultAnalysisView, priceChangePct: 2.5 }).total.delta, 1_597_500);
  assert.equal(calculateImpact({ ...defaultAnalysisView, priceChangePct: -30 }).total.volume, 2150);
  for (const priceChangePct of [31, -31, NaN, Infinity]) {
    assert.throws(() => calculateImpact({ ...defaultAnalysisView, priceChangePct }), RangeError);
  }
});

test('monthly views reconcile to the complete quarter', () => {
  const november = calculateImpact({ ...defaultAnalysisView, period: 'november' }).total.delta;
  const december = calculateImpact({ ...defaultAnalysisView, period: 'december' }).total.delta;
  assert.equal(november, 1_590_000);
  assert.equal(december, 2_580_000);
  assert.equal(2_220_000 + november + december, 6_390_000);
});

test('CSV carries synthetic-data provenance and all source records', () => {
  const csv = getPurchasePlanCsv();
  assert.ok(csv.startsWith('\uFEFFУЧЕБНЫЕ ДАННЫЕ;'));
  assert.equal(csv.split('\r\n').length, 11);
  assert.ok(csv.includes('Северстрой Подряд;2026-10;180;140;60000'));
});

test('answers use the selected company and period, not default group totals', () => {
  const answer = answerInsightQuestion('Как посчитано влияние?', { companyId: 'contracting', period: 'october', priceChangePct: 5 });
  assert.equal(answer.kind, 'method');
  assert.match(answer.context, /Подряд.*Октябрь/);
  assert.ok(answer.paragraphs.join(' ').includes(formatMoney(120_000)));
  assert.ok(!answer.paragraphs.join(' ').includes(formatMoney(6_390_000)));
  assert.deepEqual(answer.references, ['plan']);
});

test('a question can propose another view without silently modifying the current view', () => {
  const view = { ...defaultAnalysisView };
  const answer = answerInsightQuestion('Покажи влияние для инфраструктуры за октябрь', view);
  assert.equal(answer.kind, 'calculation');
  assert.deepEqual(answer.suggestedView, { companyId: 'infrastructure', period: 'october', priceChangePct: 10 });
  assert.ok(answer.paragraphs.join(' ').includes(formatMoney(720_000)));
  assert.deepEqual(view, defaultAnalysisView);
});

test('hypothetical price changes recalculate the same data, including decreases', () => {
  const growth = answerInsightQuestion('Что будет при росте цены на 15%?', defaultAnalysisView);
  assert.equal(growth.suggestedView?.priceChangePct, 15);
  assert.ok(growth.paragraphs.join(' ').includes(formatMoney(9_585_000)));
  const decline = answerInsightQuestion('А если цена снизится на 5%?', defaultAnalysisView);
  assert.equal(decline.suggestedView?.priceChangePct, -5);
  assert.ok(decline.paragraphs.join(' ').includes(formatMoney(3_195_000)));
  assert.match(decline.paragraphs.join(' '), /уменьшится/);
  const decimal = answerInsightQuestion('Если рост цены 2,55%?', defaultAnalysisView);
  assert.equal(decimal.suggestedView?.priceChangePct, 2.55);
  assert.equal(answerInsightQuestion('Если цена вырастет на 15 процентов?', defaultAnalysisView).suggestedView?.priceChangePct, 15);
});

test('comparison ranks exposure and declares the scope when a single company is selected', () => {
  const answer = answerInsightQuestion('У кого больше закупок без фиксации?', { ...defaultAnalysisView, companyId: 'contracting' });
  assert.equal(answer.kind, 'comparison');
  assert.match(answer.paragraphs[0], /Девелопмент/);
  assert.ok(answer.paragraphs.join(' ').includes(formatMoney(1_080_000)));
  assert.match(answer.paragraphs.at(-1)!, /три учебные компании/);
  assert.equal(answer.suggestedView?.companyId, 'group');
});

test('source answers distinguish market demand from a purchasing-price scenario', () => {
  const answer = answerInsightQuestion('На каком источнике основан разбор?', defaultAnalysisView);
  assert.equal(answer.kind, 'source');
  assert.deepEqual(answer.references, ['market', 'plan']);
  assert.match(answer.paragraphs.join(' '), /не подтверждает.*цен/);
  assert.equal(answerInsightQuestion('Что worldsteel пишет про спрос в 2027 году?', defaultAnalysisView).kind, 'source');
});

test('missing periods, unsupported percentages and unrelated facts do not invent data', () => {
  for (const question of [
    'Покажи за прошлый квартал', 'Покажи за сентябрь', 'Как изменится прибыль?', 'Покажи бюджет на 2030 год',
    'Какой курс доллара?', 'Сколько лет моему коту?', 'Что будет при росте цены на 50%?',
    'Какая вероятность роста цены?', 'Как приготовить суп 10%?',
    'Сравни рост цены 10% и 15%',
  ]) {
    assert.equal(answerInsightQuestion(question, defaultAnalysisView).kind, 'unsupported', question);
  }
});

test('view store can apply an answer scenario and reset it for the next session', () => {
  try {
    insightAnalysisStore.applyView({ companyId: 'infrastructure', period: 'october', priceChangePct: 15 });
    assert.equal(insightAnalysisStore.impact.total.delta, 1_080_000);
    insightAnalysisStore.setPriceChange(NaN);
    assert.equal(insightAnalysisStore.priceChangePct, 15);
    insightAnalysisStore.reset();
    assert.deepEqual(insightAnalysisStore.view, defaultAnalysisView);
  } finally { insightAnalysisStore.reset(); }
});
