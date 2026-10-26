import { useState } from 'react';
import { observer } from 'mobx-react-lite';
import { apiDownload } from '@/shared/api';
import { Alert, Button, Drawer, Modal, Table, type TableColumnsType } from 'antd';
import { ArrowUpRight, BookOpen, Building2, Download, FileSpreadsheet, Globe2 } from 'lucide-react';
import { formatMoney, formatNumber, insightsStore, type PurchasePlanRecord, type InsightSourceId } from '@/entities/insight';
import './open-insight-source.scss';

type PlanRow = PurchasePlanRecord;
const columns: TableColumnsType<PlanRow> = [
  { title: 'Компания', dataIndex: 'company_name', width: 210 },
  { title: 'Месяц', dataIndex: 'month' },
  { title: 'План, т', dataIndex: 'volume', align: 'right', render: formatNumber },
  { title: 'Цена зафиксирована, т', dataIndex: 'fixed_volume', align: 'right', render: formatNumber },
  { title: 'Плановая цена, ₽/т', dataIndex: 'price', align: 'right', render: formatMoney },
];

export const OpenInsightSource = observer(function OpenInsightSource({ activeSource, sourceIds, onOpen, onClose }: {
  activeSource: InsightSourceId | 'all' | null;
  sourceIds: InsightSourceId[];
  onOpen: (id: InsightSourceId | 'all') => void;
  onClose: () => void;
}) {
  const [downloadError, setDownloadError] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [dataOpen, setDataOpen] = useState<'plan' | 'profile' | null>(null);
  const orderedIds = activeSource && activeSource !== 'all' ? [activeSource, ...sourceIds.filter(id => id !== activeSource)] : sourceIds;
  async function downloadPlan() {
    setDownloading(true); setDownloadError('');
    try {
      const blob = await apiDownload('/insights/export/purchase-plan.csv');
      const url = URL.createObjectURL(blob); const link = document.createElement('a');
      link.href = url; link.download = 'plan-zakupok.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { setDownloadError(error instanceof Error ? error.message : 'Не удалось скачать план.'); }
    finally { setDownloading(false); }
  }
  return <>
    <div className="source-list-entry"><Button type="text" icon={<BookOpen size={15} aria-hidden="true" />} onClick={() => onOpen('all')}>Источники <span className="source-count">{sourceIds.length}</span></Button></div>
    <Drawer title="Источники" open={activeSource !== null} onClose={() => { setDataOpen(null); onClose(); }} size={440} classNames={{ body: 'sources-drawer-body' }}>
      <div className="source-list">{orderedIds.map(id => {
        const source = insightsStore.sources[id];
        if (!source) return null;
        const Icon = id === 'market' ? Globe2 : id === 'plan' ? FileSpreadsheet : Building2;
        return <article key={id} className={`source-document${activeSource === id ? ' is-selected' : ''}`} aria-label={source.title}>
          <div className="source-document-meta"><span className="source-document-icon">{source.origin === 'external' || source.origin === 'synthetic' ? <Icon size={16} aria-hidden="true" /> : <span className="citation-bank-mark" aria-hidden="true">А</span>}</span><div><strong>{source.publisher}{source.origin === 'client' ? ' · данные клиента' : ''}</strong>{source.date && <span>{source.date}</span>}</div></div>
          <h3>{source.title}</h3><p>{source.description}</p><p className="source-document-scope">{source.scope}</p>
          {source.excerpts?.map((quote, index) => <blockquote key={index}>{quote}</blockquote>)}
          <div className="source-document-actions">
            {source.url ? <Button type="link" href={source.url} target="_blank" rel="noopener noreferrer" icon={<ArrowUpRight size={14} aria-hidden="true" />} iconPlacement="end">Открыть публикацию</Button> : (id === 'plan' || id === 'profile') ? <Button type="link" onClick={() => setDataOpen(id === 'plan' ? 'plan' : 'profile')}>{id === 'plan' ? 'Посмотреть данные' : 'Посмотреть профиль'} <ArrowUpRight size={14} aria-hidden="true" /></Button> : null}
            {id === 'plan' && <Button type="text" aria-label="Скачать план закупок в CSV" title="Скачать CSV" loading={downloading} onClick={() => void downloadPlan()} icon={<Download size={15} aria-hidden="true" />} />}
          </div>
        </article>;
      })}</div>
      {downloadError && <Alert type="error" title={downloadError} />}
      <Modal title={dataOpen === 'plan' ? 'План закупок стали' : 'Профиль группы'} open={dataOpen !== null} onCancel={() => setDataOpen(null)} width={dataOpen === 'plan' ? 860 : 480} destroyOnHidden footer={<Button onClick={() => setDataOpen(null)}>Закрыть</Button>}>
        {dataOpen === 'plan' ? <Table<PlanRow> aria-label="Исходный план закупок" size="small" columns={columns} dataSource={[...insightsStore.purchasePlan]} rowKey={row => `${row.company_id}:${row.month}`} pagination={false} scroll={{ x: 680 }} /> : <dl className="source-profile"><dt>Группа</dt><dd>{insightsStore.profile?.name}</dd><dt>Отрасль</dt><dd>{insightsStore.profile?.industry}</dd><dt>Компании</dt><dd>{(insightsStore.profile?.companies ?? []).map(company => <div key={company.id}>{company.name}</div>)}</dd></dl>}
      </Modal>
    </Drawer>
  </>;
});
