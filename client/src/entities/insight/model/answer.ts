import {
  calculateImpact, describeView, formatMoney, formatNumber, formatRate, getCompanyName, marketSource,
  type AnalysisView, type CompanyId,
} from './analysis';
import { getInsightValidity, insightValidity } from './validity';
import type { InsightSourceId } from './sources';

export type InsightAnswer = {
  kind: 'calculation' | 'method' | 'comparison' | 'contracts' | 'source' | 'actions' | 'relevance' | 'validity' | 'unsupported';
  paragraphs: string[];
  context: string;
  references: InsightSourceId[];
  citations: Record<number, InsightSourceId[]>;
  suggestedView?: AnalysisView;
};

function getAnswerCitations(kind: InsightAnswer['kind'], paragraphs: string[], references: InsightSourceId[]): InsightAnswer['citations'] {
  switch (kind) {
    case 'method': case 'contracts': case 'calculation': return { 0: ['plan'], 1: ['plan'] };
    case 'source': return { 0: ['market'], 1: ['market'], 2: ['plan'] };
    case 'relevance': return { 0: ['profile'] };
    case 'comparison': return Object.fromEntries(paragraphs.slice(0, -1).map((_, index) => [index, ['plan']]));
    case 'unsupported': return references.includes('market') ? { 0: ['market'] } : {};
    default: return {};
  }
}

function readRequestedView(question: string, current: AnalysisView): AnalysisView {
  let companyId: CompanyId = current.companyId;
  if (/вс[еяй].*групп|по компани|сравн.*компани/.test(question)) companyId = 'group';
  else if (/инфраструкт/.test(question)) companyId = 'infrastructure';
  else if (/девелоп/.test(question)) companyId = 'development';
  else if (/подряд/.test(question)) companyId = 'contracting';
  let period = current.period;
  if (/октябр/.test(question)) period = 'october';
  else if (/ноябр/.test(question)) period = 'november';
  else if (/декабр/.test(question)) period = 'december';
  else if (/квартал/.test(question)) period = 'quarter';
  return { ...current, companyId, period };
}

// Prepared-material answers: no model/API call and no claims beyond the supplied dataset.
export function answerInsightQuestion(rawQuestion: string, current: AnalysisView): InsightAnswer {
  const question = rawQuestion.trim().normalize('NFKC').toLocaleLowerCase('ru-RU').replaceAll('ё', 'е');
  const view = readRequestedView(question, current);
  const reply = (kind: InsightAnswer['kind'], paragraphs: string[], references: InsightAnswer['references'] = ['plan']): InsightAnswer => {
    const citations = getAnswerCitations(kind, paragraphs, references);
    return { kind, paragraphs, citations, references: [...new Set(Object.values(citations).flat())], context: describeView(view),
    ...(kind !== 'unsupported' && (view.companyId !== current.companyId || view.period !== current.period || view.priceChangePct !== current.priceChangePct)
      ? { suggestedView: { ...view } } : {}),
    };
  };

  if (/срок.*(годност|актуал|действ)|до.*(когда|дат)|актуал|устаре|пересмотр|обновлять/.test(question)) {
    const validity = getInsightValidity();
    return { kind: 'validity', context: 'Актуальность разбора', references: [], citations: {}, paragraphs: [
      validity.expired ? `Срок актуальности истёк: пересмотр был назначен на ${validity.reviewDate}. Вывод нужно проверить заново.` : `Разбор актуален до ${validity.reviewDate}. После этой даты вывод нужно перепроверить.`,
      insightValidity.reviewTrigger,
      insightValidity.policy,
    ] };
  }

  if (/курс|доллар|кредит|прибыл|марж|выручк|дивиденд|погод|биткоин|крипт/.test(question)) {
    return reply('unsupported', ['Для этого вопроса в разборе недостаточно данных. Здесь есть только план закупок стали и сценарий изменения цены; данных о прибыли, выручке, курсах валют и кредитных условиях нет.'], []);
  }
  if (/вероятност|гаранти|точно.*подорож|будет ли.*рост/.test(question)) {
    return reply('unsupported', ['Вероятность изменения цены по этим материалам определить нельзя. Процент в расчёте — сценарное допущение пользователя; обзор worldsteel описывает спрос и не является прогнозом ваших закупочных цен.'], ['market']);
  }
  const aboutMarket = /первоисточ|источник|отчет|worldsteel|спрос|прогноз/.test(question);
  const hasUnavailableYear = [...question.matchAll(/\b(20\d{2})\b/g)].some(match => match[1] !== '2026');
  if (!aboutMarket && (hasUnavailableYear || /прошл|предыдущ|январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|(?:перв|втор|трет).{0,5}квартал|(?:^|\s)(?:i|ii|iii|1|2|3)\s*кв/.test(question))) {
    return reply('unsupported', ['В этом разборе доступны октябрь, ноябрь, декабрь 2026 и IV квартал 2026 целиком. Данные другого периода не подключены.'], []);
  }

  const percentages = [...question.matchAll(/([−-]?\d+(?:[.,]\d+)?)\s*(?:%|процент(?:а|ов)?)/g)];
  if (percentages.length > 1) return reply('unsupported', ['Для одного расчёта укажите одно изменение цены. Два сценария можно проверить последовательно; объём закупок и доля фиксации в плане остаются прежними.'], []);
  const percentage = percentages[0];
  if (percentage) {
    let value = Number(percentage[1].replace(',', '.').replace('−', '-'));
    if (/снизи|сниже|упад|паден|подешев|минус/.test(question)) value = -Math.abs(value);
    if (Math.abs(value) > 30) return reply('unsupported', ['В этом сценарии можно проверить изменение цены от −30 до +30%. Укажите процент в этих пределах; вероятность такого изменения мы не оцениваем.'], []);
    if (!/цен|стал|рост|подорож|сниж|паден|упад|будет|если|сценар|бюджет|измени/.test(question) && !/^[−-]?\d+(?:[.,]\d+)?\s*%\??$/.test(question)) {
      return reply('unsupported', ['Уточните, относится ли процент к изменению цены стали. Здесь можно пересчитать закупочный бюджет; другие показатели в сценарий не входят.'], []);
    }
    view.priceChangePct = Math.round(value * 100) / 100;
  }

  const { total } = calculateImpact(view);
  if (/формул|метод|как.*(счит|рассчит|получ)|откуда.*(сумм|цифр)|почему.*(сумм|так)/.test(question)) {
    return reply('method', [
      `Считаем только объём без зафиксированной цены: ${formatNumber(total.volume)} − ${formatNumber(total.fixedVolume)} = ${formatNumber(total.openVolume)} т. Его плановая стоимость — ${formatMoney(total.exposedBudget)}.`,
      `Изменение бюджета = стоимость незакреплённых закупок × изменение цены: ${formatMoney(total.exposedBudget)} × ${formatRate(view.priceChangePct)} = ${formatMoney(total.delta)}.`,
      'В этом расчёте не меняются объём закупок, НДС, логистика и выручка. Поэтому это изменение закупочного бюджета, а не оценка прибыли или маржи.',
    ]);
  }
  if (/почему.*(нам|мне|нас|наш|показан|касает)|зачем.*(разбор|инсайт)|что.*значит.*(бизнес|компани|нас|меня|групп)/.test(question)) {
    return reply('relevance', [
      'В профиле группы указано строительство, поэтому разбор посвящён стоимости материалов. Отрасль сама по себе не доказывает влияние на расходы.',
      'Чтобы оценить влияние на компанию, сверьте объёмы из плана с условиями фиксации цен и договорами на проекты.',
    ]);
  }
  if (aboutMarket || /откуда|доказ/.test(question)) {
    return reply('source', [
      `Рыночный контекст: ${marketSource.summary}`,
      marketSource.limitation,
      'Суммы и объёмы рассчитаны по плану закупок. Нажмите «План закупок» рядом с расчётом, чтобы проверить исходные записи.',
    ], ['market', 'plan']);
  }
  if (/что.*делать|следующ.*шаг|снизить.*риск|рекоменд|что.*провер/.test(question)) {
    return reply('actions', [
      'Сначала найдите договоры, в которых поставщик ещё может изменить цену. Запросите актуальную стоимость ближайших заказов и срок, на который поставщик её подтверждает.',
      'Сравните стоимость с бюджетом проекта. Если расходы выросли, проверьте, можно ли пересмотреть смету с заказчиком.',
      'Сам обзор рынка не означает, что нужно закупать сталь заранее. Сначала проверьте свои договоры и предложения поставщиков.',
    ]);
  }
  if (/зафиксир|защищ|фиксирован|нефикс|договор/.test(question)) {
    return reply('contracts', [
      `В выбранном плане цена зафиксирована для ${formatNumber(total.fixedVolume)} из ${formatNumber(total.volume)} т. Эти закупки исключены из сценарного изменения бюджета.`,
      `Остаётся ${formatNumber(total.openVolume)} т без фиксации на ${formatMoney(total.exposedBudget)}. При цене ${formatRate(view.priceChangePct)} изменение составит ${formatMoney(total.delta)}.`,
      'Фиксация в плане означает неизменность цены на выбранном горизонте. Проверьте, что срок фиксации покрывает период поставки.',
    ]);
  }
  if (/кто|больше|по компани|сравн|разрез/.test(question) && !percentage) {
    view.companyId = 'group';
    const comparison = calculateImpact(view).rows.sort((a, b) => b.exposedBudget - a.exposedBudget);
    const leader = comparison[0];
    return reply('comparison', [
      `По группе за выбранный период больше всего закупок без фиксации у «${leader.name}»: ${formatNumber(leader.openVolume)} т на ${formatMoney(leader.exposedBudget)}.`,
      ...comparison.map(row => `${row.name}: открытый объём ${formatNumber(row.openVolume)} т; изменение бюджета при ${formatRate(view.priceChangePct)} — ${formatMoney(row.delta)}.`),
      'Сравнение включает все три компании за указанный период.',
    ]);
  }
  if (percentage || /влиян|бюджет|удорож|расход.*стал|эффект.*стал|покажи.*(групп|закуп|стал)|октябр|ноябр|декабр|квартал|инфраструкт|девелоп|подряд/.test(question)) {
    return reply('calculation', [
      `${getCompanyName(view.companyId)}: плановая стоимость закупок — ${formatMoney(total.budget)}, из неё ${formatMoney(total.exposedBudget)} приходится на объём без фиксации цены.`,
      `При изменении цены на ${formatRate(view.priceChangePct)} закупочный бюджет ${total.delta < 0 ? 'уменьшится' : total.delta > 0 ? 'увеличится' : 'не изменится'}${total.delta === 0 ? '.' : ` на ${formatMoney(Math.abs(total.delta))}.`}`,
      'Это сценарий изменения цены, а не прогноз стоимости стали. Долю этих затрат в общей себестоимости и влияние на прибыль по имеющимся данным определить нельзя.',
    ]);
  }
  return reply('unsupported', [
    'В подготовленных материалах нет ответа на этот вопрос. Могу объяснить расчёт бюджета стали, сравнить компании, показать фиксацию цен и указать источники.',
    'Попробуйте: «Как посчитано влияние?», «У кого больше закупок без фиксации?» или «Что будет при росте цены на 15%?»',
  ], []);
}
