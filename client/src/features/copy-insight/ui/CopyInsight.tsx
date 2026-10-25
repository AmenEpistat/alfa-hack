import { useState } from 'react';
import { Copy } from 'lucide-react';
import { Button } from 'antd';
import {
  insightTitle as title, insightSummary as summary, marketSource,
  getInsightValidity, insightValidity, type InsightEntry,
} from '@/entities/insight';
import './copy-insight.scss';

export function CopyInsight({ entry }: { entry?: InsightEntry }) {
  const [copyStatus, setCopyStatus] = useState('');
  const copyText = async () => {
    const text = [entry?.title ?? title, entry?.summary ?? summary, ...(entry?.sections.map(section => `${section.title}\n${section.text}`) ?? []), getInsightValidity().label, insightValidity.reviewTrigger,
      'Следующий шаг: запросить у поставщика стоимость ближайших заказов и срок, на который он её подтверждает.',
      `Рыночный контекст: ${marketSource.url}`, marketSource.limitation,
      'Процент изменения цены — условие сценария. Вероятность изменения и влияние на прибыль не рассчитаны.',
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
