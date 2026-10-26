import { apiRequest, resolveApiAssetUrl } from '@/shared/api';
import type { GenerationMethod, InsightEntry } from '../model/catalog';
import type { AnalysisView } from '../model/analysis';
import type { InsightAnswer } from '../model/answer';
import type { InsightSource, InsightSourceId } from '../model/sources';

export type InsightDto = {
  id: string; topic: string; title: string; summary: string; cover: string;
  category_id?: number | string | null; category_name?: string | null; cover_url?: string | null; cover_background?: string | null;
  audience_type?: string | null; product_recommendations?: Record<string, unknown>[];
  content?: string; sections?: { title: string; text: string }[]; source_ids?: InsightSourceId[];
  is_saved?: boolean; prepared_at?: string; expires_at?: string; generation_method?: GenerationMethod;
};
export type PurchasePlanRecord = { company_id: string; company_name: string; month: string; volume: number; fixed_volume: number; price: number };
export type GroupProfile = { name: string; industry: string; source_id: InsightSourceId; companies: { id: string; name: string }[] };
export type ServerView = { company_id: AnalysisView['companyId']; period: AnalysisView['period']; price_change_pct: number };
export type AnswerDto = {
  kind?: InsightAnswer['kind']; question: string; paragraphs: string[]; content?: string; context: string;
  references: InsightSourceId[]; citations?: Record<number, InsightSourceId[]>; suggested_view?: ServerView | null; generation_method?: GenerationMethod;
};
export const toServerView = (view: AnalysisView): ServerView => ({ company_id: view.companyId, period: view.period, price_change_pct: view.priceChangePct });
export const fromServerView = (view: ServerView): AnalysisView => ({ companyId: view.company_id, period: view.period, priceChangePct: view.price_change_pct });

export function parseInsight(dto: InsightDto): InsightEntry {
  const content = dto.content ?? dto.sections?.map(section => `## ${section.title}\n\n${section.text}`).join('\n\n');
  if (!dto.id || typeof dto.title !== 'string' || typeof dto.summary !== 'string' || typeof content !== 'string') throw new Error('Сервер вернул некорректный формат инсайта.');
  return { id: dto.id, topic: dto.topic, title: dto.title, summary: dto.summary,
    cover: (['steel', 'contracts', 'budget'].includes(dto.cover) ? dto.cover : 'steel') as InsightEntry['cover'],
    audienceType: dto.audience_type ?? undefined, productRecommendations: dto.product_recommendations ?? [],
    categoryId: dto.category_id ?? undefined, categoryName: dto.category_name ?? undefined,
    coverUrl: resolveApiAssetUrl(dto.cover_url),
    coverBackground: /^#[0-9a-f]{6}$/i.test(dto.cover_background ?? '') ? dto.cover_background! : undefined,
    sections: dto.sections ?? [], content, sourceIds: dto.source_ids ?? [],
    isSaved: dto.is_saved ?? false, preparedAt: dto.prepared_at, expiresAt: dto.expires_at,
    generationMethod: dto.generation_method ?? 'editorial',
  };
}
export function parseAnswer(dto: AnswerDto): InsightAnswer {
  if (!Array.isArray(dto.paragraphs) || typeof dto.context !== 'string' || !Array.isArray(dto.references)) throw new Error('Сервер вернул некорректный формат ответа.');
  return { kind: dto.kind ?? 'unsupported', paragraphs: dto.paragraphs, content: dto.content ?? dto.paragraphs.join('\n\n'),
    context: dto.context, references: dto.references, citations: dto.citations ?? {},
    ...(dto.suggested_view ? { suggestedView: fromServerView(dto.suggested_view) } : {}), generationMethod: dto.generation_method ?? 'rules',
  };
}
export const fetchInsights = async () => (await apiRequest<InsightDto[]>('/insights')).map(parseInsight);
export const fetchInsight = async (id: string) => parseInsight(await apiRequest<InsightDto>(`/insights/${encodeURIComponent(id)}`));
export function parseSources(sources: (InsightSource & { id: InsightSourceId })[]) {
  if (!Array.isArray(sources)) throw new Error('Сервер вернул некорректный список источников.');
  return sources.map(source => {
    if ((typeof source.id !== 'string' || !source.id) || !['external', 'bank', 'client', 'synthetic'].includes(source.origin) || typeof source.label !== 'string' || typeof source.publisher !== 'string') throw new Error('Сервер вернул некорректный источник.');
    if (source.url) {
      const url = new URL(source.url);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Сервер вернул небезопасную ссылку источника.');
    }
    return source;
  });
}
export const fetchSources = async () => parseSources(await apiRequest<(InsightSource & { id: InsightSourceId })[]>('/insights/meta/sources'));
export const fetchInsightSources = async (id: string) => parseSources(await apiRequest<(InsightSource & { id: InsightSourceId })[]>(`/insights/${encodeURIComponent(id)}/sources`));
export const fetchPlan = () => apiRequest<PurchasePlanRecord[]>('/insights/meta/purchase-plan');
export const fetchProfile = () => apiRequest<GroupProfile>('/insights/meta/profile');
export const askInsight = async (id: string, question: string, view: AnalysisView, signal?: AbortSignal, history: { role: 'user' | 'assistant'; content: string }[] = []) => parseAnswer(await apiRequest<AnswerDto>('/insights/ask', { timeoutMs: 120_000, method: 'POST', body: JSON.stringify({ insight_id: id, question, view: toServerView(view), history }), signal }));
