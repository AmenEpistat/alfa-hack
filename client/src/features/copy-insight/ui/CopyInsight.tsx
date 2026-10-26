import { useState } from 'react';
import { Copy } from 'lucide-react';
import { Button } from 'antd';
import {
  insightsStore,
  getInsightValidity, type InsightEntry,
} from '@/entities/insight';
import './copy-insight.scss';

export function CopyInsight({ entry }: { entry: InsightEntry }) {
  const [copyStatus, setCopyStatus] = useState('');
  const copyText = async () => {
    const sources = (entry.sourceIds ?? []).flatMap(id => {
      const source = insightsStore.sources[id];
      return source ? [`${source.publisher}: ${source.title}${source.url ? ` — ${source.url}` : ''}`] : [];
    });
    const content = (entry.content ?? '').replace(/\[([^\]]+)\]\(source:([a-z0-9_-]+)\)/gi, '[$1]');
    const text = [entry.title, entry.summary, content,
      ...(entry.generationMethod === 'ai' ? ['Создано AI'] : entry.generationMethod === 'ai_assisted' ? ['Подготовлено с AI'] : []),
      ...(entry.preparedAt && entry.expiresAt ? [getInsightValidity(new Date(), { preparedAt: entry.preparedAt, expiresAt: entry.expiresAt }).label] : []),
      ...sources,
    ].join('\n\n');
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus('Текст скопирован. Его можно отправить коллеге.');
    } catch {
      setCopyStatus('Браузер не разрешил копирование. Можно выделить и скопировать текст разбора.');
    }
  };
  return <>
    <Button type="text" onClick={copyText} icon={<Copy size={16} aria-hidden="true" />}>{copyStatus.startsWith('Текст') ? 'Скопировано' : 'Копировать текст'}</Button>
    {copyStatus && <p className="copy-status sr-only" role="status">{copyStatus}</p>}
  </>;
}
