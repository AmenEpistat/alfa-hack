import { ArrowUpRight } from 'lucide-react';
import { InsightCover, type InsightEntry } from '@/entities/insight';
import { SaveInsight } from '@/features/save-insight';
import { router, routes } from '@/shared/routing';
import './insight-card.scss';

export function InsightCard({ entry }: { entry: InsightEntry }) {
  return <article className="home-insight-card">
    <a className="home-insight-link" href={`#${routes.insight(entry.id)}`} onClick={event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      router.navigate(routes.insight(entry.id));
    }}>
      <InsightCover variant={entry.cover} imageUrl={entry.coverUrl} background={entry.coverBackground} />
      <div className="home-insight-copy"><span className="home-insight-topic">{entry.topic}</span><h3>{entry.title}</h3></div>
      <span className="home-insight-read">Читать <ArrowUpRight size={15} aria-hidden="true" /></span>
    </a>
    <div className="home-insight-save"><SaveInsight id={entry.id} iconOnly /></div>
  </article>;
}
