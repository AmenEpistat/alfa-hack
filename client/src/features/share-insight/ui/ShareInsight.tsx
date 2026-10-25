import { useState } from 'react';
import { Copy, Link2 } from 'lucide-react';
import { Alert, Button, Input, Modal } from 'antd';
import { insightId } from '@/entities/insight';
import { getPageUrl, routes } from '@/shared/routing';
import './share-insight.scss';

export function ShareInsight({ id = insightId }: { id?: string }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);
  const url = getPageUrl(routes.insight(id));
  const localOnly = ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);
  async function copyLink() {
    try { await navigator.clipboard.writeText(url); setCopied(true); setError(false); }
    catch { setError(true); }
  }
  return <>
    <Button type="text" icon={<Link2 size={16} aria-hidden="true" />} onClick={() => { setOpen(true); setCopied(false); setError(false); }}>Поделиться</Button>
    <Modal title="Поделиться инсайтом" open={open} onCancel={() => setOpen(false)} footer={null} width={540}>
      <div className="share-content"><p>После входа получатель попадёт прямо в этот инсайт.</p>
        <label className="share-link-label" htmlFor="insight-share-url">Ссылка на инсайт</label>
        <div className="share-link-row"><Input id="insight-share-url" readOnly value={url} onFocus={event => event.currentTarget.select()} />
          <Button type="primary" onClick={copyLink} icon={<Copy size={16} aria-hidden="true" />}>{copied ? 'Скопировано' : 'Копировать'}</Button>
        </div>
        {error && <p role="status">Не удалось скопировать. Выделите ссылку и скопируйте вручную.</p>}
        {copied && !error && <p className="share-success" role="status">Ссылка скопирована</p>}
        {localOnly && <Alert className="share-local-note" type="info" title="Для открытия на другом устройстве нужен опубликованный адрес приложения." />}
      </div>
    </Modal>
  </>;
}
