import { lazy, Suspense, useEffect } from 'react';
import { Alert, Button, Spin } from 'antd';
import { observer } from 'mobx-react-lite';
import { sessionStore } from '@/entities/session';
import { insightsStore } from '@/entities/insight';
import { BankShell } from '@/widgets/bank-shell';
import { router, routes } from '@/shared/routing';

const HomePage = lazy(() => import('@/pages/home').then(({ HomePage }) => ({ default: HomePage })));
const InsightsPage = lazy(() => import('@/pages/insights').then(({ InsightsPage }) => ({ default: InsightsPage })));
const InsightPage = lazy(() => import('@/pages/insight').then(({ InsightPage }) => ({ default: InsightPage })));
const LoginPage = lazy(() => import('@/pages/login').then(({ LoginPage }) => ({ default: LoginPage })));
const PlaceholderPage = lazy(() => import('@/pages/placeholder').then(({ PlaceholderPage }) => ({ default: PlaceholderPage })));
const loading = <div className="route-loading" role="status"><Spin size="large" /><span>Загружаем раздел…</span></div>;

export const AppRouter = observer(function AppRouter() {
  const path = router.path;
  const entry = insightsStore.catalog.find(item => path === routes.insight(item.id))
    ?? (insightsStore.openedInsight && path === routes.insight(insightsStore.openedInsight.id) ? insightsStore.openedInsight : null);
  const isInsight = /^\/insights\/[^/]+$/.test(path);
  const insightId = isInsight ? decodeURIComponent(path.slice('/insights/'.length)) : null;
  useEffect(() => {
    if (sessionStore.user && insightsStore.ready && insightId) void insightsStore.refreshInsight(insightId);
  }, [path, sessionStore.userId, insightsStore.ready]);
  if (sessionStore.initialising) return loading;
  if (!sessionStore.user) return <Suspense fallback={loading}><LoginPage returningToInsight={isInsight} /></Suspense>;

  if (insightsStore.error) return <BankShell><div className="api-error-panel"><Alert type="error" showIcon title="Не удалось загрузить данные" description={insightsStore.error} /><Button onClick={() => void insightsStore.load()}>Повторить</Button></div></BankShell>;
  if (!insightsStore.ready || insightsStore.loading) return <BankShell>{loading}</BankShell>;

  let page;
  if (path === routes.home) page = <HomePage />;
  else if (path === routes.insights) page = <InsightsPage />;
  else if (entry) page = <InsightPage key={entry.id} entry={entry} />;
  else if (isInsight) page = insightsStore.insightError
    ? <div className="api-error-panel"><Alert type="error" showIcon title="Не удалось открыть инсайт" description={insightsStore.insightError} /><Button onClick={() => insightId && void insightsStore.refreshInsight(insightId)}>Повторить</Button></div>
    : loading;
  else {
    let title = 'Страница не найдена';
    let notFound = true;
    if (path.startsWith('/sections/') && path.length > '/sections/'.length) {
      try { title = decodeURIComponent(path.slice('/sections/'.length)); notFound = false; } catch { /* Invalid URL encoding. */ }
    }
    page = <PlaceholderPage title={title} notFound={notFound} />;
  }
  return <BankShell><Suspense fallback={loading}>{page}</Suspense></BankShell>;
});
