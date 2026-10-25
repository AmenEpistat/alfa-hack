import { useEffect, useRef, useState } from 'react';
import { Button, Input, type GetRef } from 'antd';
import { ArrowUp, RotateCcw } from 'lucide-react';
import { observer } from 'mobx-react-lite';
import { answerInsightQuestion, insightAnalysisStore as analysis, SourceCitation, type InsightAnswer, type InsightSourceId } from '@/entities/insight';
import './ask-insight.scss';

type Exchange = { id: string; question: string; answer: InsightAnswer };

export const AskInsight = observer(function AskInsight({ onOpenSource, onSourcesChange, sourcePanelOpen }: {
  onOpenSource: (id: InsightSourceId) => void;
  onSourcesChange: (ids: InsightSourceId[]) => void;
  sourcePanelOpen: boolean;
}) {
  const [draft, setDraft] = useState('');
  const [history, setHistory] = useState<Exchange[]>([]);
  const log = useRef<HTMLDivElement>(null);
  const questionInput = useRef<GetRef<typeof Input.TextArea>>(null);
  useEffect(() => {
    analysis.reset();
    return () => analysis.reset();
  }, []);
  useEffect(() => {
    if (log.current && history.length) log.current.scrollTop = log.current.scrollHeight;
  }, [history.length]);

  function ask() {
    const question = draft.trim();
    if (!question || question.length > 500) return;
    const answer = answerInsightQuestion(question, analysis.view);
    // Keep explicit conditions from the question for the next message in this chat.
    if (answer.suggestedView) analysis.applyView(answer.suggestedView);
    setHistory(current => [...current, { id: crypto.randomUUID(), question, answer }]);
    onSourcesChange([...new Set([...history.flatMap(exchange => exchange.answer.references), ...answer.references])]);
    setDraft('');
    requestAnimationFrame(() => questionInput.current?.focus({ preventScroll: true }));
  }

  return <section className="ask-insight" aria-label="Чат по материалам инсайта">
    <div ref={log} className="insight-conversation" role="log" aria-live="polite" aria-label="История уточнений">
      {history.map(({ id, question, answer }) => <article key={id} className="insight-exchange">
        <div className="insight-question"><p>{question}</p></div>
        <div className="insight-answer">
          {answer.paragraphs.map((paragraph, index) => <p key={index}>{paragraph}{answer.citations[index]?.map(sourceId => <SourceCitation key={sourceId} sourceId={sourceId} onOpen={onOpenSource} previewDisabled={sourcePanelOpen} />)}</p>)}
          <details className="insight-answer-context"><summary>Условия ответа</summary><small>{answer.context}</small></details>
        </div>
      </article>)}
    </div>
    <form className="chat-composer" onSubmit={event => { event.preventDefault(); ask(); }}>
      {history.length > 0 && <Button className="chat-clear" type="text" size="small" aria-label="Очистить историю" title="Очистить историю" onClick={() => { setHistory([]); analysis.reset(); onSourcesChange([]); }} icon={<RotateCcw size={13} aria-hidden="true" />} />}
      <div className="chat-input-row">
        <Input.TextArea ref={questionInput} id="insight-question" aria-label="Уточняющий вопрос" value={draft} onChange={event => setDraft(event.target.value)} placeholder="Что это значит для моего бизнеса?" maxLength={500} autoSize={{ minRows: 1, maxRows: 4 }} onKeyDown={event => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); ask(); }
        }} />
        <Button htmlType="submit" type="primary" aria-label="Отправить вопрос" disabled={!draft.trim()} icon={<ArrowUp size={18} aria-hidden="true" />} />
      </div>
    </form>
  </section>;
});
