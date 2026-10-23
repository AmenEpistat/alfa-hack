import { ThumbsDown, ThumbsUp } from 'lucide-react';
import { Button } from 'antd';
import { observer } from 'mobx-react-lite';
import { insightPreferencesStore as insights } from '@/entities/insight';
import './rate-insight.scss';

const reasons = ['Не про мой бизнес', 'Уже знаю', 'Непонятно', 'Не доверяю', 'Уже неактуально'];

export const RateInsight = observer(function RateInsight() {
  return <section className="feedback-panel" aria-labelledby="feedback-heading">
    <div><h2 id="feedback-heading">Этот разбор полезен?</h2><p>Помогите сделать подборку точнее</p></div>
    <div className="feedback-buttons">
      <Button color={insights.feedback === 'useful' ? 'primary' : 'default'} variant="outlined" aria-pressed={insights.feedback === 'useful'} onClick={() => insights.setFeedback('useful')} icon={<ThumbsUp size={17} aria-hidden="true" />}>Полезно</Button>
      <Button color={insights.feedback === 'not-useful' ? 'primary' : 'default'} variant="outlined" aria-pressed={insights.feedback === 'not-useful'} onClick={() => insights.setFeedback('not-useful')} icon={<ThumbsDown size={17} aria-hidden="true" />}>Не полезно</Button>
    </div>
    {insights.feedback === 'not-useful' && <div className="feedback-reasons"><p>Что не подошло? Можно не отвечать.</p><div>
      {reasons.map((reason) => <Button size="small" color={insights.reason === reason ? 'primary' : 'default'} variant="outlined" key={reason} aria-pressed={insights.reason === reason} onClick={() => insights.setReason(reason)}>{reason}</Button>)}
    </div></div>}
    {insights.feedback && <p className="feedback-status" role="status">Спасибо, оценка сохранена в этом браузере.</p>}
  </section>;
});
