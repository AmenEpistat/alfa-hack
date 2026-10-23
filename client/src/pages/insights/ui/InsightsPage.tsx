import { useState } from 'react';
import { Button, Empty } from 'antd';
import { ArrowUpRight } from 'lucide-react';
import { observer } from 'mobx-react-lite';
import { insightCatalog, insightPreferencesStore as preferences, InsightCover } from '@/entities/insight';
import { SaveInsight } from '@/features/save-insight';
import { router, routes } from '@/shared/routing';
import './insights.scss';

const topics = ['Все темы', 'Рынок', 'Закупки', 'Финансы'];

export const InsightsPage = observer(function InsightsPage() {
  const [topic, setTopic] = useState('Все темы');
  const [savedOnly, setSavedOnly] = useState(false);
  const visible = insightCatalog.filter(entry => (topic === 'Все темы' || entry.topic === topic) && (!savedOnly || preferences.isSaved(entry.id)));
  const savedCount = insightCatalog.filter(entry => preferences.isSaved(entry.id)).length;
  return <div className="insights-journal">
    <header className="journal-heading"><div><p className="journal-kicker">Для вашего бизнеса</p><h1>Бизнес-инсайты</h1><p className="journal-description">Что меняется. Как это касается вас. С чего начать.</p></div>
      <span className="journal-edition">Демо-подборка · 22 октября</span>
    </header>
    <nav className="journal-navigation" aria-label="Темы инсайтов">
      <div className="journal-topics">{topics.map(label => <Button key={label} type="text" className={topic === label && !savedOnly ? 'is-active' : ''} aria-pressed={topic === label && !savedOnly} onClick={() => { setTopic(label); setSavedOnly(false); }}>{label}</Button>)}</div>
      <Button type="text" className={savedOnly ? 'is-active' : ''} aria-pressed={savedOnly} onClick={() => { setSavedOnly(!savedOnly); setTopic('Все темы'); }}>Сохранённое{savedCount ? ` · ${savedCount}` : ''}</Button>
    </nav>
    <div className="journal-section-heading"><h2>{savedOnly ? 'Сохранённое' : topic === 'Все темы' ? 'В фокусе' : topic}</h2><span>{visible.length} {visible.length === 1 ? 'материал' : 'материала'}</span></div>
    {visible.length ? <div className="journal-grid">{visible.map(entry => <article className="journal-card" key={entry.id}>
      <a className="journal-card-link" href={`#${routes.insight(entry.id)}`} onClick={event => { event.preventDefault(); router.navigate(routes.insight(entry.id)); }}>
        <InsightCover variant={entry.cover} />
        <span className="journal-card-topic">{entry.topic}</span><h3>{entry.title}</h3><p>{entry.summary}</p>
      </a>
      <div className="journal-card-meta"><span>{entry.minutes} мин чтения</span><div><Button type="text" aria-label={`Открыть: ${entry.title}`} icon={<ArrowUpRight size={18} aria-hidden="true" />} onClick={() => router.navigate(routes.insight(entry.id))} /><SaveInsight id={entry.id} iconOnly /></div></div>
    </article>)}</div> : <Empty className="journal-empty" image={Empty.PRESENTED_IMAGE_SIMPLE} description="Сохраните интересный материал — он появится здесь." />}
    <footer className="journal-footer">Подборка для строительной группы · На основе подготовленных материалов, без обновления в реальном времени</footer>
  </div>;
});
