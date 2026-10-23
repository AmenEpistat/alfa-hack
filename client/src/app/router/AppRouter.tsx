import { lazy, Suspense } from 'react';
import { Spin } from 'antd';
import { observer } from 'mobx-react-lite';
import { sessionStore } from '@/entities/session';
import { insightCatalog } from '@/entities/insight';
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
  const entry = insightCatalog.find(item => path === routes.insight(item.id));
  const isInsight = Boolean(entry);
  if (!sessionStore.user) return <Suspense fallback={loading}><LoginPage returningToInsight={isInsight} /></Suspense>;

  let page;
  if (path === routes.home) page = <HomePage />;
  else if (path === routes.insights) page = <InsightsPage />;
  else if (entry) page = <InsightPage key={entry.id} entry={entry} />;
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
