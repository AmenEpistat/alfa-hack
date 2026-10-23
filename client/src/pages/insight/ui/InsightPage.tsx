import { useState } from 'react';
import { Button } from 'antd';
import { ArrowLeft, ChevronDown } from 'lucide-react';
import { InsightCover, InsightValidity, type InsightEntry } from '@/entities/insight';
import { SaveInsight } from '@/features/save-insight';
import { ShareInsight } from '@/features/share-insight';
import { RateInsight } from '@/features/rate-insight';
import { CopyInsight } from '@/features/copy-insight';
import { AskInsight } from '@/features/ask-insight';
import { OpenInsightSource } from '@/features/open-insight-source';
import { router, routes } from '@/shared/routing';
import './insight.scss';

export function InsightPage({ entry }: { entry: InsightEntry }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  return <div className="insight-reader">
    <Button type="text" className="reader-back" onClick={() => router.navigate(routes.insights)}><ArrowLeft size={15} aria-hidden="true" /> Все инсайты</Button>
    <div className="reader-layout">
      <article className="reader-article">
        <header className="reader-heading"><span className="reader-topic">{entry.topic} <span>· {entry.minutes} мин чтения</span></span><h1>{entry.title}</h1><p className="reader-lead">{entry.summary}</p>
          <div className="reader-dateline"><InsightValidity compact /><span>Учебный инсайт</span></div>
          <div className="reader-toolbar" aria-label="Действия с инсайтом"><SaveInsight id={entry.id} /><ShareInsight id={entry.id} /><CopyInsight entry={entry} /></div>
        </header>
        <InsightCover variant={entry.cover} />
        <div className="reader-body">{entry.sections.map(section => <section key={section.title}><h2>{section.title}</h2><p>{section.text}</p></section>)}</div>
        <details className="reader-sources" open={sourcesOpen} onToggle={event => setSourcesOpen(event.currentTarget.open)}><summary id="article-sources">Источники и исходные данные <ChevronDown size={16} aria-hidden="true" /></summary><OpenInsightSource /></details>
        {entry.id === 'steel-cost' && <RateInsight />}
      </article>
      <aside className="reader-assistant" aria-label="Чат об инсайте">
        <h2 className="reader-chat-heading">Чат</h2>
        <AskInsight onOpenSources={() => {
          setSourcesOpen(true);
          document.getElementById('article-sources')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }} />
      </aside>
    </div>
  </div>;
}
