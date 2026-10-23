import { useState } from 'react';
import { Button, Modal, Table, Tag, type TableColumnsType } from 'antd';
import { Download, ExternalLink, FileSpreadsheet } from 'lucide-react';
import { formatMoney, formatNumber, getCompanyName, getPurchasePlanCsv, marketSource, purchasePlan } from '@/entities/insight';
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

export function OpenInsightSource() {
  const [planOpen, setPlanOpen] = useState(false);
  return <section className="insight-sources" id="insight-sources" aria-labelledby="insight-sources-heading">
    <h2 id="insight-sources-heading">Источники и допущения</h2>
    <div className="insight-source">
      <div className="insight-source-meta"><Tag color="blue">Рыночный контекст</Tag><span>{marketSource.publisher} · <time dateTime="2026-10-12">{marketSource.date}</time></span></div>
      <h3>{marketSource.title}</h3>
      <p>{marketSource.summary}</p>
      <p className="insight-source-limitation">{marketSource.limitation}</p>
      <Button href={marketSource.url} target="_blank" rel="noopener noreferrer" icon={<ExternalLink size={15} aria-hidden="true" />}>Открыть первоисточник</Button>
      <small>worldsteel.org · оригинал на английском · откроется в новой вкладке</small>
    </div>
    <div className="insight-source">
      <div className="insight-source-meta"><Tag color="orange">Учебные данные</Tag><span>План закупок · версия 22.10.2026</span></div>
      <h3>Из чего получились суммы</h3>
      <p>Девять записей: три вымышленные компании, октябрь — декабрь 2026. Для каждой записи указаны плановый объём, объём с фиксированной ценой и цена за тонну.</p>
      <div className="insight-source-actions">
        <Button onClick={() => setPlanOpen(true)} icon={<FileSpreadsheet size={15} aria-hidden="true" />}>Посмотреть исходные данные</Button>
        <Button type="text" href={csvHref} download="uchebny-plan-zakupok.csv" icon={<Download size={15} aria-hidden="true" />}>Скачать CSV</Button>
      </div>
      <details className="source-assumptions"><summary>Допущения и ограничения расчёта</summary>
        <ul><li>Меняется цена только закупок без фиксации. Зафиксированные цены считаются неизменными на выбранном горизонте.</li>
          <li>Процент изменения задаёт пользователь; он не получен из обзора worldsteel.</li>
          <li>Плановая цена — 60 000 ₽/т. НДС, логистика и объём закупок не пересчитываются.</li>
          <li>Данных о выручке и полной себестоимости нет. Прибыль и маржу этот расчёт не определяет.</li></ul>
      </details>
    </div>
    <Modal title="Учебный план закупок стали" open={planOpen} onCancel={() => setPlanOpen(false)} width={860} destroyOnHidden
      footer={<Button onClick={() => setPlanOpen(false)}>Закрыть</Button>}>
      <p>Это исходный набор для сценарного расчёта. Все компании и объёмы вымышлены. При фильтрации в разборе выбираются строки из этого набора.</p>
      <Table<PlanRow> aria-label="Исходный план закупок" size="small" columns={columns} dataSource={[...purchasePlan]}
        rowKey={row => `${row.companyId}:${row.month}`} pagination={false} scroll={{ x: 680 }} />
    </Modal>
  </section>;
}
