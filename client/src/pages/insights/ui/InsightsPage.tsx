import { useState } from 'react';
import { Alert, Button, Empty } from 'antd';
import { ArrowUpRight } from 'lucide-react';
import { observer } from 'mobx-react-lite';
import { insightsStore, insightPreferencesStore as preferences, InsightCover } from '@/entities/insight';
import { SaveInsight } from '@/features/save-insight';
import { router, routes } from '@/shared/routing';
import './insights.scss';

export const InsightsPage = observer(function InsightsPage() {
  const [topic, setTopic] = useState('Все темы');
  const [savedOnly, setSavedOnly] = useState(false);
  const visible = insightsStore.catalog.filter(entry => (topic === 'Все темы' || entry.topic === topic) && (!savedOnly || preferences.isSaved(entry.id)));
  const savedCount = insightsStore.catalog.filter(entry => preferences.isSaved(entry.id)).length;
  const topics = ['Все темы', ...new Set(insightsStore.catalog.map(entry => entry.topic))];
  const preparedDates = insightsStore.catalog.map(entry => Date.parse(entry.preparedAt ?? '')).filter(Number.isFinite);
  const edition = preparedDates.length ? new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', timeZone: 'Europe/Moscow' }).format(new Date(Math.max(...preparedDates))) : '';
  return <div className="insights-journal">
    <header className="journal-heading"><div><p className="journal-kicker">{insightsStore.catalog.some(entry => entry.audienceType) ? 'Для вашей роли' : 'Общая подборка'}</p><h1>Бизнес-инсайты</h1><p className="journal-description">Что меняется. Как это касается вас. С чего начать.</p></div>
      {edition && <span className="journal-edition">{edition}</span>}
    </header>
    {preferences.error && <Alert type="error" title={preferences.error} action={<Button size="small" onClick={() => void preferences.load()}>Повторить</Button>} />}
    <nav className="journal-navigation" aria-label="Темы инсайтов">
      <div className="journal-topics">{topics.map(label => <Button key={label} type="text" className={topic === label && !savedOnly ? 'is-active' : ''} aria-pressed={topic === label && !savedOnly} onClick={() => { setTopic(label); setSavedOnly(false); }}>{label}</Button>)}</div>
      <Button type="text" className={savedOnly ? 'is-active' : ''} aria-pressed={savedOnly} onClick={() => { setSavedOnly(!savedOnly); setTopic('Все темы'); }}>Сохранённое{savedCount ? ` · ${savedCount}` : ''}</Button>
    </nav>
    <div className="journal-section-heading"><h2>{savedOnly ? 'Сохранённое' : topic === 'Все темы' ? 'В фокусе' : topic}</h2><span>{visible.length} {visible.length === 1 ? 'материал' : 'материала'}</span></div>
    {visible.length ? <div className="journal-grid">{visible.map(entry => <article className="journal-card" key={entry.id}>
      <a className="journal-card-link" href={`#${routes.insight(entry.id)}`} onClick={event => { event.preventDefault(); router.navigate(routes.insight(entry.id)); }}>
        <InsightCover variant={entry.cover} imageUrl={entry.coverUrl} background={entry.coverBackground} />
        <span className="journal-card-topic">{entry.topic}</span><h3>{entry.title}</h3><p>{entry.summary}</p>
      </a>
      <div className="journal-card-meta"><div><Button type="text" aria-label={`Открыть: ${entry.title}`} icon={<ArrowUpRight size={18} aria-hidden="true" />} onClick={() => router.navigate(routes.insight(entry.id))} /><SaveInsight id={entry.id} iconOnly /></div></div>
    </article>)}</div> : <Empty className="journal-empty" image={Empty.PRESENTED_IMAGE_SIMPLE} description="Сохраните интересный материал — он появится здесь." />}
    {insightsStore.profile && <footer className="journal-footer">Подборка · {insightsStore.profile.name}</footer>}
  </div>;
});
