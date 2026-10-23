import { makeAutoObservable } from 'mobx';
import { calculateImpact, defaultAnalysisView, type AnalysisView, type CompanyId, type PeriodId } from './analysis';

class InsightAnalysisStore {
  companyId: CompanyId = defaultAnalysisView.companyId;
  period: PeriodId = defaultAnalysisView.period;
  priceChangePct = defaultAnalysisView.priceChangePct;

  constructor() { makeAutoObservable(this, {}, { autoBind: true }); }

  get view(): AnalysisView { return { companyId: this.companyId, period: this.period, priceChangePct: this.priceChangePct }; }
  get impact() { return calculateImpact(this.view); }

  setCompany(companyId: CompanyId) { this.companyId = companyId; }
  setPeriod(period: PeriodId) { this.period = period; }
  setPriceChange(value: number) {
    if (Number.isFinite(value) && Math.abs(value) <= 30) this.priceChangePct = value;
  }
  applyView(view: AnalysisView) {
    this.setCompany(view.companyId);
    this.setPeriod(view.period);
    this.setPriceChange(view.priceChangePct);
  }
  reset() { this.applyView(defaultAnalysisView); }
}

export const insightAnalysisStore = new InsightAnalysisStore();
