import { makeAutoObservable, runInAction } from 'mobx';
import { fetchInsight, fetchInsightSources, fetchInsights, fetchPlan, fetchProfile, fetchSources, type GroupProfile, type PurchasePlanRecord } from '../api/insights-api';
import type { InsightEntry } from './catalog';
import type { InsightSource, InsightSourceId } from './sources';

class InsightsStore {
  catalog: InsightEntry[] = [];
  openedInsight: InsightEntry | null = null;
  sources: Partial<Record<InsightSourceId, InsightSource>> = {};
  purchasePlan: PurchasePlanRecord[] = [];
  profile: GroupProfile | null = null;
  loading = false;
  ready = false;
  error = '';
  insightError = '';
  private version = 0;
  constructor() { makeAutoObservable(this, {}, { autoBind: true }); }
  reset() { this.version++; this.catalog = []; this.openedInsight = null; this.sources = {}; this.purchasePlan = []; this.profile = null; this.ready = false; this.loading = false; this.error = ''; this.insightError = ''; }
  async load() {
    const version = ++this.version;
    this.loading = true; this.error = '';
    try {
      const [catalog, sources, plan, profile] = await Promise.all([fetchInsights(), fetchSources(), fetchPlan(), fetchProfile()]);
      if (version !== this.version) return;
      runInAction(() => { this.catalog = catalog; this.openedInsight = null; this.sources = Object.fromEntries(sources.map(source => [source.id, source])); this.purchasePlan = plan; this.profile = profile; this.ready = true; });
    } catch (error) { if (version === this.version) runInAction(() => { this.error = error instanceof Error ? error.message : 'Не удалось загрузить инсайты.'; }); }
    finally { if (version === this.version) runInAction(() => { this.loading = false; }); }
  }
  async refreshInsight(id: string) {
    const version = this.version;
    this.insightError = '';
    try {
      const [entry, sources] = await Promise.all([fetchInsight(id), fetchInsightSources(id)]);
      if (version !== this.version) return;
      runInAction(() => { const index = this.catalog.findIndex(item => item.id === id); if (index < 0) this.openedInsight = entry; else this.catalog[index] = entry; this.sources = { ...this.sources, ...Object.fromEntries(sources.map(source => [source.id, source])) }; });
    } catch (error) { if (version === this.version) runInAction(() => { this.insightError = error instanceof Error ? error.message : 'Не удалось открыть инсайт.'; }); }
  }
}
export const insightsStore = new InsightsStore();
