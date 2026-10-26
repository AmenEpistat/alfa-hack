/** Browser-only API for the Netlify interface preview. No ML or bank connection. */
type DemoPreference = { insight_id: string; is_saved: boolean; feedback: string | null; reason: string | null };
const users = [
  { id: 'anna', name: 'Анна Смирнова', initials: 'АС', role: 'Финансовый директор', audience_type: 'cfo' },
  { id: 'ilya', name: 'Илья Воронов', initials: 'ИВ', role: 'Казначей', audience_type: 'treasury_head' },
];

const sources = [
  { id: 'market', label: 'worldsteel', publisher: 'worldsteel.org', origin: 'external', date: '12 октября 2026',
    title: 'worldsteel Short Range Outlook — October 2026',
    description: 'Публичный обзор мирового спроса на сталь.',
    scope: 'Прогноз спроса не подтверждает изменение цены в договоре конкретного поставщика.',
    url: 'https://worldsteel.org/media/press-releases/2026/worldsteel-short-range-outlook-october-2026/' },
  { id: 'plan', label: 'План закупок', publisher: 'Синтетические данные', origin: 'client', date: null,
    title: 'Пример плана закупок', description: 'Условные данные для просмотра интерфейса.',
    scope: 'Не отражает закупки или счета реального клиента.', url: null },
];

const insights = [
  { id: 'steel-cost', topic: 'Рынок', title: 'Проверьте цены в договорах на сталь',
    summary: 'Уточните стоимость ближайших заказов. Если поставщик может изменить цену, дополнительные расходы придётся учесть в бюджете проекта.',
    cover: 'steel', category_id: 3, category_name: 'Сырьё, энергия и издержки', minutes: 0,
    content: '## Начните с ближайшего заказа\n\nНайдите договоры, в которых поставщик ещё может изменить цену. Зафиксируйте дату, объём и условия пересмотра.\n\n## Обзор рынка — повод проверить договоры\n\nПубличный обзор worldsteel описывает мировой спрос на сталь, но не заменяет проверку конкретных условий поставщика. [worldsteel](source:market)\n\n## Что проверить в компании\n\nСначала сверьте объём закупок и сроки фиксации цены. Числа в примере плана не относятся к реальному клиенту. [План закупок](source:plan)',
    source_ids: ['market', 'plan'], generation_method: 'editorial' },
  { id: 'price-fixation', topic: 'Закупки', title: 'Какие закупки зависят от цены поставщика',
    summary: 'Отделите заказы с подтверждённой стоимостью от тех, для которых цену ещё могут пересмотреть.',
    cover: 'contracts', category_id: 3, category_name: 'Сырьё, энергия и издержки', minutes: 0,
    content: '## Разделите план на две части\n\nВ примере плана есть объём с зафиксированной ценой и объём без фиксации. Для настоящего заказа эти сведения нужно проверить в договоре. [План закупок](source:plan)\n\n## Проверьте срок фиксации\n\nДля каждого заказа сверьте подтверждённую цену, объём и период действия условий поставщика.\n\n## С чего начать разговор с поставщиком\n\nУточните стоимость ближайшего заказа и дату окончания периода фиксации.',
    source_ids: ['plan'], generation_method: 'editorial' },
];

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
  const prefs = readPreferences(user.id);
  if (url.pathname === '/insights' && method === 'GET') {
    return response(insights.map(item => ({ ...item, is_saved: preference(prefs, item.id).is_saved })));
  }
  if (url.pathname === '/insights/meta/sources' && method === 'GET') return response(sources);
  if (url.pathname === '/insights/meta/profile' && method === 'GET') return response({ name: 'Мои компании', industry: '', source_id: 'profile', companies: [] });
  if (url.pathname === '/insights/meta/purchase-plan' && method === 'GET') return response([]);
  if (url.pathname === '/insights/meta/categories' && method === 'GET') return response([]);
  if (url.pathname === '/insights/ask' && method === 'POST') return response({ detail: 'Чат доступен при локальном запуске с подключённой моделью.' }, 503);
  if (url.pathname === '/insights/export/purchase-plan.csv' && method === 'GET') {
    return new Response('\ufeffКомпания;Месяц;План, т;Фиксация, т;Цена, ₽/т\r\n', { headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
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
