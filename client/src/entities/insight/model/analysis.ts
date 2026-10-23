export const companies = [
  { id: 'development', name: 'Северстрой Девелопмент' },
  { id: 'contracting', name: 'Северстрой Подряд' },
  { id: 'infrastructure', name: 'Северстрой Инфраструктура' },
] as const;

export type CompanyId = 'group' | typeof companies[number]['id'];
export type PeriodId = 'october' | 'november' | 'december' | 'quarter';
export type AnalysisView = { companyId: CompanyId; period: PeriodId; priceChangePct: number };

export const periods: Record<PeriodId, string> = {
  october: 'Октябрь 2026',
  november: 'Ноябрь 2026',
  december: 'Декабрь 2026',
  quarter: 'IV квартал 2026',
};
export const defaultAnalysisView: AnalysisView = { companyId: 'group', period: 'quarter', priceChangePct: 10 };

type PurchasePlanRow = {
  companyId: Exclude<CompanyId, 'group'>;
  month: string;
  volume: number;
  fixedVolume: number;
  price: number;
};

// Synthetic purchasing plan, deliberately separate from the public market report.
export const purchasePlan: readonly PurchasePlanRow[] = [
  { companyId: 'development', month: '2026-10', volume: 350, fixedVolume: 140, price: 60_000 },
  { companyId: 'development', month: '2026-11', volume: 250, fixedVolume: 125, price: 60_000 },
  { companyId: 'development', month: '2026-12', volume: 400, fixedVolume: 200, price: 60_000 },
  { companyId: 'contracting', month: '2026-10', volume: 180, fixedVolume: 140, price: 60_000 },
  { companyId: 'contracting', month: '2026-11', volume: 220, fixedVolume: 180, price: 60_000 },
  { companyId: 'contracting', month: '2026-12', volume: 300, fixedVolume: 200, price: 60_000 },
  { companyId: 'infrastructure', month: '2026-10', volume: 120, fixedVolume: 0, price: 60_000 },
  { companyId: 'infrastructure', month: '2026-11', volume: 130, fixedVolume: 30, price: 60_000 },
  { companyId: 'infrastructure', month: '2026-12', volume: 200, fixedVolume: 70, price: 60_000 },
];

export type CompanyImpact = {
  id: Exclude<CompanyId, 'group'>;
  name: string;
  volume: number;
  fixedVolume: number;
  openVolume: number;
  budget: number;
  exposedBudget: number;
  delta: number;
};

export function calculateImpact(view: AnalysisView) {
  if (!Number.isFinite(view.priceChangePct) || Math.abs(view.priceChangePct) > 30) {
    throw new RangeError('Сценарное изменение цены должно быть от −30 до +30%.');
  }
  const monthByPeriod = { october: '2026-10', november: '2026-11', december: '2026-12' };
  const rows: CompanyImpact[] = companies.filter(company => view.companyId === 'group' || company.id === view.companyId).map(company => {
    const records = purchasePlan.filter(row => row.companyId === company.id && (view.period === 'quarter' || row.month === monthByPeriod[view.period]));
    const volume = records.reduce((sum, row) => sum + row.volume, 0);
    const fixedVolume = records.reduce((sum, row) => sum + row.fixedVolume, 0);
    const budget = records.reduce((sum, row) => sum + row.volume * row.price, 0);
    const exposedBudget = records.reduce((sum, row) => sum + (row.volume - row.fixedVolume) * row.price, 0);
    return { ...company, volume, fixedVolume, openVolume: volume - fixedVolume, budget, exposedBudget,
      delta: Math.round(exposedBudget * view.priceChangePct / 100) };
  });
  const total = rows.reduce((sum, row) => ({
    volume: sum.volume + row.volume,
    fixedVolume: sum.fixedVolume + row.fixedVolume,
    openVolume: sum.openVolume + row.openVolume,
    budget: sum.budget + row.budget,
    exposedBudget: sum.exposedBudget + row.exposedBudget,
    delta: sum.delta + row.delta,
  }), { volume: 0, fixedVolume: 0, openVolume: 0, budget: 0, exposedBudget: 0, delta: 0 });
  return { rows, total };
}

const moneyFormatter = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 });
const numberFormatter = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 });
export const formatMoney = (value: number) => moneyFormatter.format(value);
export const formatNumber = (value: number) => numberFormatter.format(value);
export const formatMillions = (value: number) => `${value > 0 ? '+' : ''}${formatNumber(value / 1_000_000)} млн ₽`;
export const formatRate = (value: number) => `${value > 0 ? '+' : ''}${formatNumber(value)}%`;
export const getCompanyName = (id: CompanyId) => companies.find(company => company.id === id)?.name ?? 'Вся группа';
export const describeView = (view: AnalysisView) => `${getCompanyName(view.companyId)} · ${periods[view.period]} · цена ${formatRate(view.priceChangePct)}`;

export const marketSource = {
  title: 'worldsteel Short Range Outlook — October 2026',
  publisher: 'World Steel Association',
  date: '12 октября 2026',
  url: 'https://worldsteel.org/media/press-releases/2026/worldsteel-short-range-outlook-october-2026/',
  summary: 'worldsteel ожидает почти неизменный мировой спрос на сталь в 2026 году и рост на 1,7% в 2027 году.',
  limitation: 'Обзор посвящён спросу. Он не подтверждает изменение закупочных цен вашей компании; процент в расчёте задаётся отдельно.',
} as const;

export function getPurchasePlanCsv() {
  return '\uFEFF' + [
    'УЧЕБНЫЕ ДАННЫЕ;Не являются данными клиента или банка',
    'Компания;Месяц;План закупок, т;Зафиксированная цена, т;Плановая цена, руб/т',
    ...purchasePlan.map(row => [getCompanyName(row.companyId), row.month, row.volume, row.fixedVolume, row.price].join(';')),
  ].join('\r\n');
}
