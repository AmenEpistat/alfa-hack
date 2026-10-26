import { ThumbsDown, ThumbsUp } from 'lucide-react';
import { Alert, Button } from 'antd';
import { observer } from 'mobx-react-lite';
import { insightPreferencesStore as insights } from '@/entities/insight';
import './rate-insight.scss';

const reasons = ['Не про мой бизнес', 'Уже знаю', 'Непонятно', 'Не доверяю', 'Уже неактуально'];

export const RateInsight = observer(function RateInsight({ id }: { id: string }) {
  return <section className="feedback-panel" aria-labelledby="feedback-heading">
    <div><h2 id="feedback-heading">Этот инсайт полезен?</h2><p>Помогите сделать подборку точнее</p></div>
    <div className="feedback-buttons">
      <Button disabled={insights.pending[id]} color={insights.feedbackFor(id) === 'useful' ? 'primary' : 'default'} variant="outlined" aria-pressed={insights.feedbackFor(id) === 'useful'} onClick={() => insights.setFeedback(id, 'useful')} icon={<ThumbsUp size={17} aria-hidden="true" />}>Полезно</Button>
      <Button disabled={insights.pending[id]} color={insights.feedbackFor(id) === 'not-useful' ? 'primary' : 'default'} variant="outlined" aria-pressed={insights.feedbackFor(id) === 'not-useful'} onClick={() => insights.setFeedback(id, 'not-useful')} icon={<ThumbsDown size={17} aria-hidden="true" />}>Не полезно</Button>
    </div>
    {insights.feedbackFor(id) === 'not-useful' && <div className="feedback-reasons"><p>Что не подошло? Можно не отвечать.</p><div>
      {reasons.map((reason) => <Button disabled={insights.pending[id]} size="small" color={insights.reasonFor(id) === reason ? 'primary' : 'default'} variant="outlined" key={reason} aria-pressed={insights.reasonFor(id) === reason} onClick={() => insights.setReason(id, reason)}>{reason}</Button>)}
    </div></div>}
    {insights.errors[id] && <Alert type="error" title={insights.errors[id]} />}
    {insights.feedbackFor(id) && <p className="feedback-status" role="status">Оценка сохранена.</p>}
  </section>;
});
