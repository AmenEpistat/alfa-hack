import { observer } from 'mobx-react-lite';
import { MarkdownContent } from '@/shared/ui/markdown';
import { insightsStore } from '../model/insights-store';
import type { InsightSourceId } from '../model/sources';
import { SourceCitation } from './SourceCitation';

export const InsightMarkdown = observer(function InsightMarkdown({ content, onOpenSource, previewDisabled = false }: {
  content: string; onOpenSource: (id: InsightSourceId) => void; previewDisabled?: boolean;
}) {
  return <MarkdownContent renderCitation={id => insightsStore.sources[id as InsightSourceId]
    ? <SourceCitation sourceId={id as InsightSourceId} onOpen={onOpenSource} previewDisabled={previewDisabled} />
    : <span className="citation-unavailable">Источник недоступен</span>}>{content}</MarkdownContent>;
});
