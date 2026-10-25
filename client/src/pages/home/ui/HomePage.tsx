import { Button } from 'antd';
import { ArrowRight } from 'lucide-react';
import { insightCatalog } from '@/entities/insight';
import { HomeDashboard } from '@/widgets/bank-overview';
import { InsightCard } from '@/widgets/insight-card';
import { router, routes } from '@/shared/routing';
import './home.scss';

export function HomePage() {
  return <>
    <HomeDashboard />
    <section aria-labelledby="home-insights-heading" className="home-insights">
      <div className="home-insights-heading"><h2 id="home-insights-heading">Бизнес-инсайты</h2>
        <Button type="text" onClick={() => router.navigate(routes.insights)}>Все инсайты <ArrowRight size={16} aria-hidden="true" /></Button>
      </div>
      <div className="home-insights-grid">{insightCatalog.map(entry => <InsightCard key={entry.id} entry={entry} />)}</div>
    </section>
  </>;
}
