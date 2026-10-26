import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Input, type GetRef } from 'antd';
import { ArrowUp, RotateCcw } from 'lucide-react';
import { observer } from 'mobx-react-lite';
import { askInsight, insightAnalysisStore as analysis, GenerationLabel, InsightMarkdown, type InsightAnswer, type InsightSourceId } from '@/entities/insight';
import './ask-insight.scss';

type Exchange = { id: string; question: string; answer: InsightAnswer };

export const AskInsight = observer(function AskInsight({ insightId, onOpenSource, onSourcesChange, sourcePanelOpen }: {
  insightId: string;
  onOpenSource: (id: InsightSourceId) => void;
  onSourcesChange: (ids: InsightSourceId[]) => void;
  sourcePanelOpen: boolean;
}) {
  const [draft, setDraft] = useState('');
  const [pendingQuestion, setPendingQuestion] = useState('');
  const [error, setError] = useState('');
  const request = useRef<AbortController | null>(null);
  const [history, setHistory] = useState<Exchange[]>([]);
  const log = useRef<HTMLDivElement>(null);
  const questionInput = useRef<GetRef<typeof Input.TextArea>>(null);
  useEffect(() => {
    analysis.reset();
    return () => { request.current?.abort(); analysis.reset(); };
  }, []);
  useEffect(() => {
    if (log.current && history.length) log.current.scrollTop = log.current.scrollHeight;
  }, [history.length, pendingQuestion]);

  async function ask() {
    const question = draft.trim();
    if (!question || question.length > 500 || request.current) return;
    const controller = new AbortController();
    request.current = controller; setPendingQuestion(question); setDraft(''); setError('');
    try {
      const answer = await askInsight(insightId, question, analysis.view, controller.signal, history.slice(-5).flatMap(item => [{ role: 'user' as const, content: item.question }, { role: 'assistant' as const, content: item.answer.content ?? item.answer.paragraphs.join('\n\n') }]));
      if (controller.signal.aborted) return;
      if (answer.suggestedView) analysis.applyView(answer.suggestedView);
      setHistory(current => [...current, { id: crypto.randomUUID(), question, answer }]);
      onSourcesChange([...new Set([...history.flatMap(exchange => exchange.answer.references), ...answer.references])]);
    } catch (error) {
      if (!controller.signal.aborted) { setError(error instanceof Error ? error.message : 'Не удалось получить ответ.'); setDraft(question); }
    } finally {
      if (!controller.signal.aborted) { setPendingQuestion(''); request.current = null; requestAnimationFrame(() => questionInput.current?.focus({ preventScroll: true })); }
    }
  }

  return <section className="ask-insight" aria-label="Чат по материалам инсайта">
    <div ref={log} className="insight-conversation" role="log" aria-live="polite" aria-label="История уточнений">
      {history.map(({ id, question, answer }) => <article key={id} className="insight-exchange">
        <div className="insight-question"><p>{question}</p></div>
        <div className="insight-answer">
          <InsightMarkdown content={answer.content ?? answer.paragraphs.join('\n\n')} onOpenSource={onOpenSource} previewDisabled={sourcePanelOpen} />
          <GenerationLabel method={answer.generationMethod} />
          <details className="insight-answer-context"><summary>Условия ответа</summary><small>{answer.context}</small></details>
        </div>
      </article>)}
      {pendingQuestion && <article className="insight-exchange"><div className="insight-question"><p>{pendingQuestion}</p></div><p className="chat-pending" role="status">Готовим ответ…</p></article>}
    </div>
    <form className="chat-composer" onSubmit={event => { event.preventDefault(); void ask(); }}>
      {error && <Alert className="chat-error" type="error" title={error} />}
      {history.length > 0 && <Button disabled={Boolean(pendingQuestion)} className="chat-clear" type="text" size="small" aria-label="Очистить историю" title="Очистить историю" onClick={() => { setHistory([]); analysis.reset(); onSourcesChange([]); }} icon={<RotateCcw size={13} aria-hidden="true" />} />}
      <div className="chat-input-row">
        <Input.TextArea ref={questionInput} id="insight-question" aria-label="Уточняющий вопрос" disabled={Boolean(pendingQuestion)} value={draft} onChange={event => setDraft(event.target.value)} placeholder="Что это значит для моего бизнеса?" maxLength={500} autoSize={{ minRows: 1, maxRows: 4 }} onKeyDown={event => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void ask(); }
        }} />
        <Button htmlType="submit" type="primary" aria-label="Отправить вопрос" loading={Boolean(pendingQuestion)} disabled={!draft.trim() || Boolean(pendingQuestion)} icon={<ArrowUp size={18} aria-hidden="true" />} />
      </div>
    </form>
  </section>;
});
