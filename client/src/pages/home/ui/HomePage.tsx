import { Button } from 'antd';
import { ArrowRight, ShieldCheck } from 'lucide-react';
import { HomeDashboard } from '@/widgets/bank-overview';
import { InsightCard } from '@/widgets/insight-card';
import { router, routes } from '@/shared/routing';
import './home.scss';

export function HomePage() {
  return <>
    <HomeDashboard />
    <section aria-labelledby="important-heading" className="important-section">
      <div className="section-title-row"><div><h2 id="important-heading">Важно для вашего бизнеса</h2><p>Событие, его влияние и ваш следующий шаг</p></div>
        <Button type="text" onClick={() => router.navigate(routes.insights)}>Все инсайты <ArrowRight size={16} aria-hidden="true" /></Button>
      </div>
      <InsightCard home />
    </section>
    <div className="home-footnote"><ShieldCheck size={17} aria-hidden="true" /><p>Счета и план закупок — учебные. В разборе доступен публичный источник рыночного контекста.</p></div>
  </>;
}
