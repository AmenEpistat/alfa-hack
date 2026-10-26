import { makeAutoObservable, runInAction } from 'mobx';
import { apiRequest } from '@/shared/api';
import { insightId } from './insight';

export type Feedback = 'useful' | 'not-useful' | null;
export type Preference = { insight_id: string; is_saved: boolean; feedback: Feedback; reason: string | null };
export type PreferencesRequest = <T>(path: string, options?: RequestInit) => Promise<T>;

export class InsightPreferencesStore {
  private userId: string | null = null;
  private version = 0;
  items: Record<string, Preference> = {};
  pending: Record<string, boolean> = {};
  errors: Record<string, string> = {};
  error = '';
  constructor(private request: PreferencesRequest = apiRequest) { makeAutoObservable(this, {}, { autoBind: true }); }
  get saved() { return this.isSaved(insightId); }
  get savedIds() { return Object.values(this.items).filter(item => item.is_saved).map(item => item.insight_id); }
  setUser(userId: string | null) { this.version++; this.userId = userId; this.items = {}; this.pending = {}; this.errors = {}; this.error = ''; }
  isSaved(id: string) { return this.items[id]?.is_saved ?? false; }
  feedbackFor(id: string) { return this.items[id]?.feedback ?? null; }
  reasonFor(id: string) { return this.items[id]?.reason ?? ''; }
  async load() {
    const version = this.version;
    if (!this.userId) return;
    this.error = '';
    try {
      const items = await this.request<Preference[]>('/preferences');
      if (version === this.version) runInAction(() => { this.items = Object.fromEntries(items.map(item => [item.insight_id, item])); });
    } catch (error) { if (version === this.version) runInAction(() => { this.error = error instanceof Error ? error.message : 'Не удалось загрузить сохранённое.'; }); }
  }
  private async mutate(id: string, path: string, body?: unknown) {
    if (!this.userId || this.pending[id]) return;
    const version = this.version;
    this.pending[id] = true; this.errors[id] = '';
    try {
      const item = await this.request<Preference>(path, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
      if (version === this.version) runInAction(() => { this.items[id] = item; });
    } catch (error) { if (version === this.version) runInAction(() => { this.errors[id] = error instanceof Error ? error.message : 'Не удалось сохранить изменение.'; }); }
    finally { if (version === this.version) runInAction(() => { this.pending[id] = false; }); }
  }
  toggleSavedFor(id: string) { return this.mutate(id, `/preferences/${encodeURIComponent(id)}/toggle`); }
  setFeedback(id: string, feedback: Feedback) { return this.mutate(id, '/preferences/feedback', { insight_id: id, feedback: this.feedbackFor(id) === feedback ? null : feedback, reason: null }); }
  setReason(id: string, reason: string) { return this.mutate(id, '/preferences/feedback', { insight_id: id, feedback: this.feedbackFor(id), reason }); }
}
export const insightPreferencesStore = new InsightPreferencesStore();
