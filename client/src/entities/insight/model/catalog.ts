import { insightId, insightSummary, insightTitle } from './insight';
import type { CitationAnchor, InsightSourceId } from './sources';
export type GenerationMethod = 'ai' | 'ai_assisted' | 'editorial' | 'rules';

export type InsightEntry = {
  id: string;
  topic: string;
  title: string;
  summary: string;
  cover: 'steel' | 'contracts' | 'budget';
  categoryId?: number | string;
  categoryName?: string;
  coverUrl?: string;
  coverBackground?: string;
  sections: { title: string; text: string; citations?: CitationAnchor[] }[];
  content?: string;
  audienceType?: string;
  productRecommendations?: Record<string, unknown>[];
  sourceIds?: InsightSourceId[];
  isSaved?: boolean;
  preparedAt?: string;
  expiresAt?: string;
  generationMethod?: GenerationMethod;
};

// Three editorial angles on the same prepared demo materials, not a live news feed.
export const insightCatalog: InsightEntry[] = [
  {
    id: insightId, topic: 'Рынок', title: insightTitle, summary: insightSummary, cover: 'steel',
    sections: [
      { title: 'Начните с ближайшего заказа', text: 'Найдите договоры, в которых поставщик ещё может изменить цену. Запросите стоимость следующей поставки и срок, на который он её подтверждает. Именно эти закупки требуют внимания в первую очередь.' },
      { title: 'Обзор рынка — повод проверить, а не покупать', text: 'worldsteel ожидает почти неизменный мировой спрос на сталь в 2026 году и рост на 1,7% в 2027 году. Обзор описывает спрос, а не цену в вашем договоре. Решение о закупке стоит принимать после сверки предложений поставщиков и бюджета проекта.', citations: [{ after: 'рост на 1,7% в 2027 году.', sourceId: 'market' }] },
      { title: 'Что это значит для вашей группы', text: 'В профиле «Северстроя» указано строительство. Но одной отрасли недостаточно, чтобы оценить расходы: нужны фактические объёмы и условия договоров. Расчёт по плану закупок можно запросить в чате.', citations: [{ after: 'указано строительство.', sourceId: 'profile' }, { after: 'Расчёт по плану закупок можно запросить в чате.', sourceId: 'plan' }] },
    ],
  },
  {
    id: 'price-fixation', topic: 'Закупки', title: 'Какие закупки зависят от цены поставщика',
    summary: 'Отделите заказы с подтверждённой стоимостью от тех, для которых цену ещё могут пересмотреть.', cover: 'contracts',
    sections: [
      { title: 'Разделите план на две части', text: 'В плане закупок стали есть объём с зафиксированной ценой и объём без фиксации. В сценарии изменения цены пересчитывается только вторая часть.', citations: [{ after: 'объём без фиксации.', sourceId: 'plan' }] },
      { title: 'Проверьте срок фиксации', text: 'Для реального заказа нужно сверить подтверждённую цену, объём и период поставки. Если срок подтверждения закончился, прежняя цена уже не даёт оснований считать будущие расходы неизменными.' },
      { title: 'С чего начать разговор с поставщиком', text: 'Уточните стоимость ближайшего заказа, дату окончания предложения и условия её пересмотра. После этого обновите план закупок.' },
    ],
  },
  {
    id: 'purchase-budget', topic: 'Финансы', title: 'Как проверить запас бюджета на материалы',
    summary: 'Один сценарий изменения цены поможет увидеть, какую сумму стоит обсудить с финансовой командой.', cover: 'budget',
    sections: [
      { title: 'Проверьте одно допущение', text: 'Укажите в чате компанию, период и предполагаемое изменение цены. Расчёт покажет разницу в закупочных расходах для объёма, цена которого ещё не зафиксирована.' },
      { title: 'Как получается сумма', text: 'Стоимость закупок без фиксации умножается на изменение цены. Для всей группы при росте цены на 10% это 63,9 млн ₽ × 10% = 6,39 млн ₽ дополнительных расходов. Процент задаёт пользователь; это не прогноз рынка.', citations: [{ after: '6,39 млн ₽ дополнительных расходов.', sourceId: 'plan' }] },
      { title: 'Что обсудить с финансовой командой', text: 'Сравните получившуюся разницу с доступным бюджетом проекта и проверьте возможность пересмотра сметы. Расчёт не оценивает прибыль: данных о выручке и полной себестоимости в нём нет.' },
    ],
  },
];

export function findInsight(id: string) { return insightCatalog.find(entry => entry.id === id); }
