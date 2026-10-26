import { useEffect, useState } from 'react';
import { Button, Tooltip } from 'antd';
import { Clock3, Info } from 'lucide-react';
import { getInsightValidity, insightValidity } from '../model/validity';
import './insight-validity.scss';

export function InsightValidity({ compact = false, metadata }: { compact?: boolean; metadata?: { preparedAt: string; expiresAt: string } }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, []);
  if (!metadata) return null;
  const validity = getInsightValidity(now, metadata);

  if (compact) return <p className={`insight-validity-compact${validity.expired ? ' is-expired' : ''}`}>
    <Clock3 size={14} aria-hidden="true" /> {validity.label}
  </p>;

  return <div className={`insight-validity${validity.expired ? ' is-expired' : ''}`} role="status">
    <div className="insight-validity-title"><Clock3 size={17} aria-hidden="true" />
      <strong>{validity.label}</strong>
      <Tooltip trigger="click" title={`Подготовлено ${new Intl.DateTimeFormat('ru-RU', { dateStyle: 'long', timeZone: 'Europe/Moscow' }).format(new Date(metadata.preparedAt))}. ${insightValidity.policy}`}>
        <Button type="text" size="small" aria-label="Как определён срок актуальности" icon={<Info size={14} aria-hidden="true" />} />
      </Tooltip>
    </div>
    <p>{validity.expired ? `Вывод нужно проверить заново: срок пересмотра — ${validity.reviewDate}.` : insightValidity.reviewTrigger}</p>
  </div>;
}
