import { Button, Card } from 'antd';
import { ArrowRight, Lightbulb, TrendingUp, X } from 'lucide-react';
import { observer } from 'mobx-react-lite';
import { insightId, insightTitle as title, insightSummary as summary, insightPreferencesStore as insights, InsightValidity } from '@/entities/insight';
import { SaveInsight } from '@/features/save-insight';
import { ShareInsight } from '@/features/share-insight';
import { router, routes } from '@/shared/routing';
import './insight-card.scss';

export const InsightCard = observer(function InsightCard({ home = false }: { home?: boolean }) {
  const Heading = home ? 'h3' : 'h2';
  if (insights.hidden) return <div className="empty-insights" role="status">
    <Lightbulb size={24} aria-hidden="true" />
    <div><strong>Вы скрыли этот инсайт</strong><p>Он больше не показывается в подборке.</p></div>
    <Button type="text" onClick={() => insights.setHidden(false)}>Вернуть</Button>
  </div>;

  return <article><Card variant="borderless" style={{ boxShadow: 'none' }} styles={{ body: { padding: 0 } }} className={`insight-card${home ? ' insight-card--featured' : ''}`}>
    <div className="insight-card-top">
      <span className="topic-label"><TrendingUp size={16} aria-hidden="true" /> Строительство · Закупки</span>
      <Button type="text" size="small" aria-label="Скрыть инсайт" onClick={() => insights.setHidden(true)} icon={<X size={17} aria-hidden="true" />} />
    </div>
    <div className="insight-card-layout">
      <div>
        <p className="insight-eyebrow">На что обратить внимание</p>
        <Heading>{title}</Heading>
        <p className="insight-description">{summary}</p>
      </div>
      <div className="insight-symbol" aria-hidden="true"><TrendingUp size={42} strokeWidth={1.5} /></div>
    </div>
    <InsightValidity compact />
    <div className="relevance-note"><span className="small-dot" />
      <span><strong>Почему вам:</strong> отрасль группы — строительство. Состав закупок нужно уточнить.</span>
    </div>
    <div className="insight-card-bottom">
      <Button type="primary" onClick={() => router.navigate(routes.insight(insightId))}>
        Открыть разбор <ArrowRight size={17} aria-hidden="true" />
      </Button>
      <SaveInsight />
      <ShareInsight />
      <span className="sample-label">Учебный сценарий</span>
    </div>
  </Card></article>;
});
