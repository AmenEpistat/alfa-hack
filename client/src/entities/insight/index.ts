export { insightId, insightTitle, insightSummary } from './model/insight';
export { insightCatalog, findInsight } from './model/catalog';
export type { InsightEntry } from './model/catalog';
export { insightPreferencesStore } from './model/preferences-store';
export type { Feedback } from './model/preferences-store';
export {
  companies, periods, defaultAnalysisView, purchasePlan, calculateImpact, marketSource,
  formatMoney, formatNumber, formatMillions, formatRate, getCompanyName, describeView, getPurchasePlanCsv,
} from './model/analysis';
export type { CompanyId, PeriodId, AnalysisView, CompanyImpact } from './model/analysis';
export { insightAnalysisStore } from './model/analysis-store';
export { answerInsightQuestion } from './model/answer';
export type { InsightAnswer } from './model/answer';
export { insightValidity, getInsightValidity } from './model/validity';
export { InsightValidity } from './ui/InsightValidity';
export { InsightCover } from './ui/InsightCover';
export { insightSources } from './model/sources';
export type { InsightSourceId, CitationAnchor } from './model/sources';
export { SourceCitation, CitedText } from './ui/SourceCitation';
