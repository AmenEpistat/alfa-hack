import { Fragment, useState } from 'react';
import { Button, Popover } from 'antd';
import { Building2, FileSpreadsheet, Globe2 } from 'lucide-react';
import { type CitationAnchor, type InsightSourceId } from '../model/sources';
import { insightsStore } from '../model/insights-store';
import { observer } from 'mobx-react-lite';
import './source-citation.scss';

export const SourceCitation = observer(function SourceCitation({ sourceId, onOpen, previewDisabled = false }: { sourceId: InsightSourceId; onOpen: (id: InsightSourceId) => void; previewDisabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const source = insightsStore.sources[sourceId];
  if (!source) return null;
  const Icon = sourceId === 'market' ? Globe2 : sourceId === 'plan' ? FileSpreadsheet : Building2;
  function showSource() { setOpen(false); onOpen(sourceId); }
  return <Popover open={open && !previewDisabled} onOpenChange={next => setOpen(next && !previewDisabled)} trigger={['hover', 'focus']} placement="top" content={
    <div className="citation-preview"><span>{source.publisher}{source.origin === 'client' ? ' · данные клиента' : ''}{source.date ? ` · ${source.date}` : ''}</span>
      <strong>{source.title}</strong><p>{source.description}</p>
      <Button type="link" size="small" onMouseDown={event => event.preventDefault()} onClick={showSource}>Подробнее об источнике</Button>
    </div>
  }>
    <button type="button" className="source-citation" aria-label={`Источник: ${source.label}`} onClick={showSource}>
      {source.origin === 'external' ? <Icon size={11} aria-hidden="true" /> : <span className="citation-bank-mark" aria-hidden="true">А</span>}<span>{source.label}</span>
    </button>
  </Popover>;
});

export function CitedText({ text, citations = [], onOpenSource, previewDisabled = false }: {
  text: string; citations?: CitationAnchor[]; onOpenSource: (id: InsightSourceId) => void; previewDisabled?: boolean;
}) {
  const anchors = citations.flatMap(citation => {
    const index = text.indexOf(citation.after);
    return index < 0 ? [] : [{ ...citation, end: index + citation.after.length }];
  }).sort((a, b) => a.end - b.end);
  let start = 0;
  const parts = anchors.map((anchor, index) => {
    const part = text.slice(start, anchor.end);
    start = anchor.end;
    return <Fragment key={`${anchor.sourceId}-${index}`}>{part}<SourceCitation sourceId={anchor.sourceId} onOpen={onOpenSource} previewDisabled={previewDisabled} /></Fragment>;
  });
  return <>{parts}{text.slice(start)}</>;
}
