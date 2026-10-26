import { marketSource } from './analysis';

export type InsightSourceId = string;
export type CitationAnchor = { after: string; sourceId: InsightSourceId };
export type InsightSource = { label: string; publisher: string; origin: 'external' | 'bank' | 'client'; excerpts?: string[]; date: string | null; title: string; description: string; scope: string; url: string | null };

export const insightSources = {
  market: {
    label: 'worldsteel', publisher: 'worldsteel.org', date: '12 октября 2026',
    title: marketSource.title,
    description: marketSource.summary,
    scope: marketSource.limitation,
    url: marketSource.url,
  },
  plan: {
    label: 'План закупок', publisher: 'Данные группы', date: '22 октября 2026',
    title: 'Закупки стали · IV квартал 2026',
    description: 'Объёмы закупок трёх компаний, доля с фиксированной ценой и плановая стоимость за тонну.',
    scope: 'Расчёт меняет цену только для закупок без фиксации. Процент изменения задаётся в вопросе.',
    url: null,
  },
  profile: {
    label: 'Профиль группы', publisher: 'Данные группы', date: null,
    title: 'ГК «Северстрой» · строительство',
    description: 'Отрасль и состав группы, по которым подобрана тема инсайта.',
    scope: 'Отрасль объясняет выбор темы. Для оценки расходов нужны объёмы закупок и условия договоров.',
    url: null,
  },
} satisfies Record<InsightSourceId, {
  label: string; publisher: string; date: string | null; title: string;
  description: string; scope: string; url: string | null;
}>;
