import { useState } from 'react';
import { Button } from 'antd';
import { ArrowLeft } from 'lucide-react';
import { GenerationLabel, InsightMarkdown, InsightCover, InsightValidity, type InsightEntry, type InsightSourceId } from '@/entities/insight';
import { SaveInsight } from '@/features/save-insight';
import { ShareInsight } from '@/features/share-insight';
import { RateInsight } from '@/features/rate-insight';
import { CopyInsight } from '@/features/copy-insight';
import { AskInsight } from '@/features/ask-insight';
import { OpenInsightSource } from '@/features/open-insight-source';
import { articleBody } from '@/shared/ui/markdown';
import { router, routes } from '@/shared/routing';
import './insight.scss';

export function InsightPage({ entry }: { entry: InsightEntry }) {
  const [activeSource, setActiveSource] = useState<InsightSourceId | 'all' | null>(null);
  const [chatSources, setChatSources] = useState<InsightSourceId[]>([]);
  const sourceIds = [...new Set([...(entry.sourceIds ?? []), ...chatSources])];
  const hasChatContext = Boolean(entry.audienceType);
  return <div className="insight-reader">
    <Button type="text" className="reader-back" onClick={() => router.navigate(routes.insights)}><ArrowLeft size={15} aria-hidden="true" /> Все инсайты</Button>
    <div className={`reader-layout${hasChatContext ? '' : ' reader-layout--article-only'}`}>
      <article className="reader-article">
        <header className="reader-heading"><span className="reader-topic">{entry.topic}</span><h1>{entry.title}</h1><p className="reader-lead">{entry.summary}</p>
          <div className="reader-dateline"><InsightValidity compact metadata={entry.preparedAt && entry.expiresAt ? { preparedAt: entry.preparedAt, expiresAt: entry.expiresAt } : undefined} /><GenerationLabel method={entry.generationMethod} /></div>
          <div className="reader-toolbar" aria-label="Действия с инсайтом"><SaveInsight id={entry.id} /><ShareInsight id={entry.id} /><CopyInsight entry={entry} /></div>
        </header>
        <InsightCover variant={entry.cover} imageUrl={entry.coverUrl} background={entry.coverBackground} />
        <div className="reader-body"><InsightMarkdown content={articleBody(entry.content ?? '', Boolean(entry.sourceIds?.length))} onOpenSource={setActiveSource} previewDisabled={activeSource !== null} /></div>
        <OpenInsightSource activeSource={activeSource} sourceIds={sourceIds} onOpen={setActiveSource} onClose={() => setActiveSource(null)} />
        <RateInsight id={entry.id} />
      </article>
      {hasChatContext && <aside className="reader-assistant" aria-label="Чат об инсайте">
        <h2 className="reader-chat-heading">Чат</h2>
        <AskInsight insightId={entry.id} onOpenSource={setActiveSource} onSourcesChange={setChatSources} sourcePanelOpen={activeSource !== null} />
      </aside>}
    </div>
  </div>;
}
