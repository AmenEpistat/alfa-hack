import { useState } from 'react';
import { Button, Drawer, Modal, Table, type TableColumnsType } from 'antd';
import { ArrowUpRight, BookOpen, Building2, Download, FileSpreadsheet, Globe2 } from 'lucide-react';
import { companies, formatMoney, formatNumber, getCompanyName, getPurchasePlanCsv, insightSources, purchasePlan, type InsightSourceId } from '@/entities/insight';
import './open-insight-source.scss';

type PlanRow = typeof purchasePlan[number];
const csvHref = `data:text/csv;charset=utf-8,${encodeURIComponent(getPurchasePlanCsv())}`;
const columns: TableColumnsType<PlanRow> = [
  { title: 'Компания', dataIndex: 'companyId', render: getCompanyName, width: 210 },
  { title: 'Месяц', dataIndex: 'month' },
  { title: 'План, т', dataIndex: 'volume', align: 'right', render: formatNumber },
  { title: 'Цена зафиксирована, т', dataIndex: 'fixedVolume', align: 'right', render: formatNumber },
  { title: 'Плановая цена, ₽/т', dataIndex: 'price', align: 'right', render: formatMoney },
];

export function OpenInsightSource({ activeSource, sourceIds, onOpen, onClose }: {
  activeSource: InsightSourceId | 'all' | null;
  sourceIds: InsightSourceId[];
  onOpen: (id: InsightSourceId | 'all') => void;
  onClose: () => void;
}) {
  const [dataOpen, setDataOpen] = useState<'plan' | 'profile' | null>(null);
  const orderedIds = activeSource && activeSource !== 'all' ? [activeSource, ...sourceIds.filter(id => id !== activeSource)] : sourceIds;
  return <>
    <div className="source-list-entry"><Button type="text" icon={<BookOpen size={15} aria-hidden="true" />} onClick={() => onOpen('all')}>Источники <span className="source-count">{sourceIds.length}</span></Button></div>
    <Drawer title="Источники" open={activeSource !== null} onClose={() => { setDataOpen(null); onClose(); }} size={440} classNames={{ body: 'sources-drawer-body' }}>
      <div className="source-list">{orderedIds.map(id => {
        const source = insightSources[id];
        const Icon = id === 'market' ? Globe2 : id === 'plan' ? FileSpreadsheet : Building2;
        return <article key={id} className={`source-document${activeSource === id ? ' is-selected' : ''}`} aria-label={source.title}>
          <div className="source-document-meta"><span className="source-document-icon"><Icon size={16} aria-hidden="true" /></span><div><strong>{source.publisher}</strong>{source.date && <span>{source.date}</span>}</div></div>
          <h3>{source.title}</h3><p>{source.description}</p><p className="source-document-scope">{source.scope}</p>
          <div className="source-document-actions">
            {source.url ? <Button type="link" href={source.url} target="_blank" rel="noopener noreferrer" icon={<ArrowUpRight size={14} aria-hidden="true" />} iconPlacement="end">Открыть публикацию</Button> : <Button type="link" onClick={() => setDataOpen(id === 'plan' ? 'plan' : 'profile')}>{id === 'plan' ? 'Посмотреть данные' : 'Посмотреть профиль'} <ArrowUpRight size={14} aria-hidden="true" /></Button>}
            {id === 'plan' && <Button type="text" aria-label="Скачать план закупок в CSV" title="Скачать CSV" href={csvHref} download="plan-zakupok.csv" icon={<Download size={15} aria-hidden="true" />} />}
          </div>
        </article>;
      })}</div>
      <Modal title={dataOpen === 'plan' ? 'План закупок стали' : 'Профиль группы'} open={dataOpen !== null} onCancel={() => setDataOpen(null)} width={dataOpen === 'plan' ? 860 : 480} destroyOnHidden footer={<Button onClick={() => setDataOpen(null)}>Закрыть</Button>}>
        {dataOpen === 'plan' ? <Table<PlanRow> aria-label="Исходный план закупок" size="small" columns={columns} dataSource={[...purchasePlan]} rowKey={row => `${row.companyId}:${row.month}`} pagination={false} scroll={{ x: 680 }} /> : <dl className="source-profile"><dt>Группа</dt><dd>ГК «Северстрой»</dd><dt>Отрасль</dt><dd>Строительство</dd><dt>Компании</dt><dd>{companies.map(company => <div key={company.id}>{company.name}</div>)}</dd></dl>}
      </Modal>
    </Drawer>
  </>;
}
