/** Browser-only API for the Netlify interface preview. No ML or bank connection. */
type DemoPreference = { insight_id: string; is_saved: boolean; feedback: string | null; reason: string | null };
const users = [
  { id: 'anna', name: 'Анна Смирнова', initials: 'АС', role: 'Финансовый директор', audience_type: 'cfo' },
  { id: 'ilya', name: 'Илья Воронов', initials: 'ИВ', role: 'Казначей', audience_type: 'treasury_head' },
];

const companies = [
  { id: 'development', name: 'Северстрой Девелопмент' },
  { id: 'contracting', name: 'Северстрой Подряд' },
  { id: 'infrastructure', name: 'Северстрой Инфраструктура' },
];

const purchasePlan = [
  { company_id: 'development', company_name: companies[0].name, month: '2026-10', volume: 350, fixed_volume: 140, price: 60_000 },
  { company_id: 'development', company_name: companies[0].name, month: '2026-11', volume: 250, fixed_volume: 125, price: 60_000 },
  { company_id: 'development', company_name: companies[0].name, month: '2026-12', volume: 400, fixed_volume: 200, price: 60_000 },
  { company_id: 'contracting', company_name: companies[1].name, month: '2026-10', volume: 180, fixed_volume: 140, price: 60_000 },
  { company_id: 'contracting', company_name: companies[1].name, month: '2026-11', volume: 220, fixed_volume: 180, price: 60_000 },
  { company_id: 'contracting', company_name: companies[1].name, month: '2026-12', volume: 300, fixed_volume: 200, price: 60_000 },
  { company_id: 'infrastructure', company_name: companies[2].name, month: '2026-10', volume: 120, fixed_volume: 0, price: 60_000 },
  { company_id: 'infrastructure', company_name: companies[2].name, month: '2026-11', volume: 130, fixed_volume: 30, price: 60_000 },
  { company_id: 'infrastructure', company_name: companies[2].name, month: '2026-12', volume: 200, fixed_volume: 70, price: 60_000 },
];

const sources = [
  { id: 'market', label: 'worldsteel', publisher: 'worldsteel.org', origin: 'external', date: '12 октября 2026',
    title: 'worldsteel Short Range Outlook — October 2026',
    description: 'Прогноз мирового спроса на сталь: 1 722 млн т в 2026 году и рост на 1,7% в 2027 году.',
    scope: 'Это прогноз спроса, а не закупочной цены или условий российских поставщиков.',
    url: 'https://worldsteel.org/media/press-releases/2026/worldsteel-short-range-outlook-october-2026/' },
  { id: 'plan', label: 'План закупок', publisher: 'Синтетический план', origin: 'synthetic', date: null,
    title: 'Закупки стали группы «Северстрой» · IV квартал 2026',
    description: 'Девять строк по трём компаниям: месячные объёмы, фиксация цены и базовая стоимость 60 000 ₽ за тонну.',
    scope: 'Числа иллюстрируют сценарий и не относятся к реальному клиенту. Расчёты основаны на строках плана ниже.', url: null },
];

const common = { category_id: 3, category_name: 'Сырьё, энергия и издержки', minutes: 0, generation_method: 'editorial' };
const insightsByUser = {
  anna: [
    { ...common, id: 'steel-cost', topic: 'Рынок', cover: 'steel',
      title: 'Сталь без фиксации цены: где может вырасти бюджет',
      summary: 'В плане группы 1 065 т закупок без зафиксированной цены. Если она окажется на 10% выше базовой, бюджет увеличится на 6,39 млн ₽ — это сценарий, а не прогноз рынка.',
      content: [
        '## Сигнал рынка',
        'worldsteel ожидает почти неизменный мировой спрос на сталь в 2026 году — 1 722 млн т, а в 2027 году прогнозирует рост на 1,7%. При этом спрос вне Китая, по оценке ассоциации, растёт на 1,5% уже в 2026 году. Региональная картина отличается от общей; из неё нельзя вывести цену конкретного договора. [worldsteel](source:market)',
        '## Где бюджет открыт для пересмотра',
        'В синтетическом плане группы на IV квартал — 2 150 т стали на 129 млн ₽ по базовой цене 60 000 ₽/т. Цена зафиксирована для 1 085 т; ещё 1 065 т остаются открытыми. Базовая стоимость открытого объёма — 63,9 млн ₽. [План закупок](source:plan)',
        '| Компания | Без фиксации | Базовая стоимость | При +10% к цене |\n|---|---:|---:|---:|\n| Девелопмент | 535 т | 32,1 млн ₽ | +3,21 млн ₽ |\n| Инфраструктура | 350 т | 21 млн ₽ | +2,1 млн ₽ |\n| Подряд | 180 т | 10,8 млн ₽ | +1,08 млн ₽ |',
        'Суммарные +6,39 млн ₽ получаются только при допущении о росте цены на 10% для объёма без фиксации. Это не прогноз worldsteel и не оценка реальных обязательств клиента. [План закупок](source:plan)',
        '## Что сделать сейчас',
        '1. Сначала проверить договоры Девелопмента: на эту компанию приходится половина открытого объёма.\n2. Для ближайших заказов подтвердить дату, до которой действует цена, и формулу её пересмотра.\n3. Обновить резерв бюджета только после ответа поставщиков; сценарные 6,39 млн ₽ показывают размер возможного отклонения, а не сумму к оплате.',
        '## Когда вывод устареет',
        'Пересчитать открытый объём после подписания спецификаций, переноса поставки или изменения цены в договорах. Прогноз спроса и закупочный план отвечают на разные вопросы — не подменяйте один другим.',
      ].join('\n\n'), source_ids: ['market', 'plan'] },
    { ...common, id: 'price-fixation', topic: 'Закупки', cover: 'contracts',
      title: 'Декабрьские закупки требуют отдельного резерва',
      summary: '430 т, или 40% открытого объёма, приходятся на декабрь. Именно там стоит сначала проверить условия фиксации и дату бюджетного решения.',
      content: [
        '## Где сосредоточен риск',
        'В сценарном плане на октябрь остаются без фиксации 370 т, на ноябрь — 265 т, на декабрь — 430 т. Декабрь даёт 40% всех открытых 1 065 т. При базовой цене его открытый объём стоит 25,8 млн ₽. [План закупок](source:plan)',
        '| Месяц | Объём без фиксации | База по 60 000 ₽/т |\n|---|---:|---:|\n| Октябрь | 370 т | 22,2 млн ₽ |\n| Ноябрь | 265 т | 15,9 млн ₽ |\n| Декабрь | 430 т | 25,8 млн ₽ |',
        '## Что важно в договоре',
        'Для каждой открытой позиции найдите дату фиксации, допустимый коридор пересмотра, валюту расчёта и момент оплаты. Если цена определяется после размещения заказа, резерв нужен до этой даты. Если цена уже закреплена спецификацией, такой объём не стоит включать в сценарий роста.',
        '## Решение для финансовой команды',
        'Начните с декабрьских спецификаций и 535 т открытого объёма Девелопмента. Попросите закупки подтвердить, какие позиции можно закрыть фиксированной ценой до согласования бюджета. Остальные позиции оставьте отдельной строкой риска, а не растворяйте в общем плане. [План закупок](source:plan)',
        'Вывод перестаёт быть актуальным после обновления объёмов, подписания спецификаций или переноса сроков поставки.',
      ].join('\n\n'), source_ids: ['plan'] },
  ],
  ilya: [
    { ...common, id: 'steel-cost', topic: 'Рынок', cover: 'steel',
      title: 'Рынок стали меняется; платёжный календарь зависит от условий поставки',
      summary: 'Мировой спрос в 2026 году почти не растёт, но в плане группы 1 065 т ещё без окончательной цены. Казначейству важнее даты её фиксации и платежа, чем средний прогноз рынка.',
      content: [
        '## Рыночный сигнал и его предел',
        'По прогнозу worldsteel, глобальный спрос на сталь в 2026 году останется около 1 722 млн т, а в 2027 году вырастет на 1,7%. Вне Китая ассоциация ожидает рост спроса уже в 2026 году. Это повод следить за предложениями поставщиков, но не основание менять платёжный календарь без договора. [worldsteel](source:market)',
        '## Что уже видно в плане',
        'Из 2 150 т планируемых закупок цена зафиксирована для 1 085 т. У оставшихся 1 065 т базовая стоимость — 63,9 млн ₽. Расклад открытого объёма по месяцам: октябрь 370 т, ноябрь 265 т, декабрь 430 т. Это синтетический план, по которому можно отработать порядок сверки. [План закупок](source:plan)',
        '## Какие даты нужны казначейству',
        'Для каждой открытой позиции свяжите четыре события: утверждение спецификации, фиксацию цены, аванс и окончательный платёж. Если цена устанавливается после аванса, держите возможную доплату отдельным сценарием. Если платёж в другой валюте, отдельно проверьте курс и дату конвертации — эти условия нельзя вывести из мирового прогноза спроса.',
        '## Следующий шаг',
        'Запросите у закупок список декабрьских заказов без цены и даты решений поставщика. До их подтверждения не переносите сценарную разницу в утверждённый платёжный календарь. [План закупок](source:plan)',
      ].join('\n\n'), source_ids: ['market', 'plan'] },
    { ...common, id: 'price-fixation', topic: 'Платежи', cover: 'contracts',
      title: 'Декабрь: 430 т открытых закупок в платёжном календаре',
      summary: 'На декабрь приходится 40% закупок без фиксированной цены. Для них нужно связать дату согласования цены с авансом и окончательным платежом.',
      content: [
        '## Почему декабрь в фокусе',
        'В синтетическом плане декабрьский объём без фиксации — 430 т против 370 т в октябре и 265 т в ноябре. При базовой цене 60 000 ₽/т это 25,8 млн ₽ будущих платежей, для которых итоговая цена ещё не подтверждена. [План закупок](source:plan)',
        '## Сверка по каждому заказу',
        '1. Укажите, кто и когда фиксирует цену: поставщик, спецификация или формула в договоре.\n2. Проверьте аванс: оплачивается ли он до фиксации и как учитывается при окончательном расчёте.\n3. Поставьте в календарь дату доплаты и срок платежа, а не только месяц поставки.\n4. Отметьте заказы с валютной или индексной привязкой отдельно.',
        '## Что передать финансовому директору',
        'Передайте три числа по декабрю: подтверждённый объём, 430 т открытого объёма и дату, когда цена станет окончательной. Если поставщик предложит новую цену, разницу можно пересчитать по конкретным заказам. Пока предложения нет, любая прибавка остаётся допущением, а не обязательством. [План закупок](source:plan)',
        'Обновите календарь после подписания спецификаций или изменения графика поставки; именно эти события меняют потребность в деньгах.',
      ].join('\n\n'), source_ids: ['plan'] },
  ],
};

const memory = new Map<string, string>();
function readPreferences(userId: string): Record<string, DemoPreference> {
  let raw: string | null;
  try { raw = localStorage.getItem(`alfa-static-preferences:${userId}`) ?? memory.get(userId) ?? null; }
  catch { raw = memory.get(userId) ?? null; }
  if (!raw) return {};
  try { return JSON.parse(raw) as Record<string, DemoPreference>; }
  catch { return {}; }
}
function savePreferences(userId: string, data: Record<string, DemoPreference>) {
  const raw = JSON.stringify(data);
  try { localStorage.setItem(`alfa-static-preferences:${userId}`, raw); }
  catch { memory.set(userId, raw); }
}
function response(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
}
function preference(data: Record<string, DemoPreference>, id: string): DemoPreference {
  return data[id] ?? { insight_id: id, is_saved: false, feedback: null, reason: null };
}

export async function staticDemoResponse(path: string, options: RequestInit = {}, token: string | null = null): Promise<Response> {
  const url = new URL(path, 'https://static-demo.invalid');
  const method = (options.method ?? 'GET').toUpperCase();
  const body = typeof options.body === 'string' ? JSON.parse(options.body) as Record<string, unknown> : {};

  if (url.pathname === '/auth/users' && method === 'GET') return response(users);
  if (url.pathname === '/auth/login' && method === 'POST') {
    const user = users.find(item => item.id === body.user_id);
    return user ? response({ access_token: user.id, user }) : response({ detail: 'Пользователь не найден.' }, 401);
  }
  if (url.pathname === '/auth/me' && method === 'GET') {
    const user = users.find(item => item.id === url.searchParams.get('token'));
    return user ? response(user) : response({ detail: 'Недействительный токен.' }, 401);
  }

  const user = users.find(item => item.id === token);
  if (!user) return response({ detail: 'Войдите в аккаунт, чтобы продолжить.' }, 401);
  const insights = insightsByUser[user.id as keyof typeof insightsByUser].map(item => ({ ...item, audience_type: user.audience_type }));
  const prefs = readPreferences(user.id);
  if (url.pathname === '/insights' && method === 'GET') {
    return response(insights.map(item => ({ ...item, is_saved: preference(prefs, item.id).is_saved })));
  }
  if (url.pathname === '/insights/meta/sources' && method === 'GET') return response(sources);
  if (url.pathname === '/insights/meta/profile' && method === 'GET') return response({ name: 'ГК «Северстрой»', industry: 'Строительство', source_id: 'profile', companies });
  if (url.pathname === '/insights/meta/purchase-plan' && method === 'GET') return response(purchasePlan);
  if (url.pathname === '/insights/meta/categories' && method === 'GET') return response([]);
  if (url.pathname === '/insights/ask' && method === 'POST') return response({ detail: 'Чат доступен при локальном запуске с подключённой моделью.' }, 503);
  if (url.pathname === '/insights/export/purchase-plan.csv' && method === 'GET') {
    const rows = purchasePlan.map(row => [row.company_name, row.month, row.volume, row.fixed_volume, row.price].join(';'));
    return new Response('\ufeffКомпания;Месяц;План, т;Фиксация, т;Цена, ₽/т\r\n' + rows.join('\r\n'), { headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
  }
  const detail = url.pathname.match(/^\/insights\/([^/]+)(\/sources)?$/);
  if (detail && method === 'GET') {
    const item = insights.find(article => article.id === decodeURIComponent(detail[1]));
    if (!item) return response({ detail: 'Инсайт не найден.' }, 404);
    if (detail[2]) return response(sources.filter(source => item.source_ids.includes(source.id)));
    return response({ ...item, is_saved: preference(prefs, item.id).is_saved });
  }
  if (url.pathname === '/preferences' && method === 'GET') return response(Object.values(prefs));
  const toggle = url.pathname.match(/^\/preferences\/([^/]+)\/toggle$/);
  if (toggle && method === 'POST') {
    const id = decodeURIComponent(toggle[1]);
    if (!insights.some(item => item.id === id)) return response({ detail: 'Инсайт не найден.' }, 404);
    prefs[id] = { ...preference(prefs, id), is_saved: !preference(prefs, id).is_saved };
    savePreferences(user.id, prefs);
    return response(prefs[id]);
  }
  if (url.pathname === '/preferences/feedback' && method === 'POST') {
    const id = String(body.insight_id ?? '');
    if (!insights.some(item => item.id === id)) return response({ detail: 'Инсайт не найден.' }, 404);
    prefs[id] = { ...preference(prefs, id), feedback: typeof body.feedback === 'string' ? body.feedback : null,
      reason: typeof body.reason === 'string' ? body.reason : null };
    savePreferences(user.id, prefs);
    return response(prefs[id]);
  }
  return response({ detail: 'Маршрут недоступен в статической версии.' }, 404);
}
