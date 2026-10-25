import { useState } from 'react';
import { Button } from 'antd';
import { ArrowLeft } from 'lucide-react';
import { CitedText, InsightCover, InsightValidity, type InsightEntry, type InsightSourceId } from '@/entities/insight';
import { SaveInsight } from '@/features/save-insight';
import { ShareInsight } from '@/features/share-insight';
import { RateInsight } from '@/features/rate-insight';
import { CopyInsight } from '@/features/copy-insight';
import { AskInsight } from '@/features/ask-insight';
import { OpenInsightSource } from '@/features/open-insight-source';
import { router, routes } from '@/shared/routing';
import './insight.scss';

export function InsightPage({ entry }: { entry: InsightEntry }) {
  const [activeSource, setActiveSource] = useState<InsightSourceId | 'all' | null>(null);
  const [chatSources, setChatSources] = useState<InsightSourceId[]>([]);
  const sourceIds = [...new Set([...entry.sections.flatMap(section => section.citations?.map(citation => citation.sourceId) ?? []), ...chatSources])];
  return <div className="insight-reader">
    <Button type="text" className="reader-back" onClick={() => router.navigate(routes.insights)}><ArrowLeft size={15} aria-hidden="true" /> Все инсайты</Button>
    <div className="reader-layout">
      <article className="reader-article">
        <header className="reader-heading"><span className="reader-topic">{entry.topic}</span><h1>{entry.title}</h1><p className="reader-lead">{entry.summary}</p>
          <div className="reader-dateline"><InsightValidity compact /></div>
          <div className="reader-toolbar" aria-label="Действия с инсайтом"><SaveInsight id={entry.id} /><ShareInsight id={entry.id} /><CopyInsight entry={entry} /></div>
        </header>
        <InsightCover variant={entry.cover} />
        <div className="reader-body">{entry.sections.map(section => <section key={section.title}><h2>{section.title}</h2><p><CitedText text={section.text} citations={section.citations} onOpenSource={setActiveSource} previewDisabled={activeSource !== null} /></p></section>)}</div>
        <OpenInsightSource activeSource={activeSource} sourceIds={sourceIds} onOpen={setActiveSource} onClose={() => setActiveSource(null)} />
        {entry.id === 'steel-cost' && <RateInsight />}
      </article>
      <aside className="reader-assistant" aria-label="Чат об инсайте">
        <h2 className="reader-chat-heading">Чат</h2>
        <AskInsight onOpenSource={setActiveSource} onSourcesChange={setChatSources} sourcePanelOpen={activeSource !== null} />
      </aside>
    </div>
  </div>;
}
