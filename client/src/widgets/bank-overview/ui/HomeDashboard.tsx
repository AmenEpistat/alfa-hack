import { Button, ConfigProvider } from 'antd';
import { useState } from 'react';
import { ArrowDownToLine, ArrowRight, CreditCard, Eye, EyeOff, FileInput, FilePlus2, Plus, Settings2, Wallet } from 'lucide-react';
import { router, routes } from '@/shared/routing';
import './bank-overview.scss';

const workItems = [
  { label: 'Подписать и отправить', count: 1, attention: true },
  { label: 'В работе у банка', count: 7, attention: true },
  { label: 'Отклонённые', count: 4, attention: true },
  { label: 'Черновики', count: 1 },
  { label: 'Оплатить', count: 1 },
  { label: 'Доработать', count: 0 },
  { label: 'Принять предложение', count: 3 },
];

export function HomeDashboard() {
  const [balancesVisible, setBalancesVisible] = useState(true);
  const amount = (value: string) => balancesVisible ? value : '••••••';
  return <>
    <h1 className="sr-only">Главная</h1>
    <div className="bank-actions" aria-label="Быстрые действия">
      <Button type="default" onClick={() => router.navigate(routes.section('Выписка'))}><ArrowDownToLine size={17} aria-hidden="true" />Скачать выписку</Button>
      <Button type="default" onClick={() => router.navigate(routes.section('Импорт реестров'))}><FileInput size={17} aria-hidden="true" />Импорт платежей</Button>
      <Button type="default" onClick={() => router.navigate(routes.section('Новый платёж'))}><FilePlus2 size={17} aria-hidden="true" />Создать платёж</Button>
      <Button type="default" className="more-actions" onClick={() => router.navigate(routes.section('Все сервисы и продукты'))}>Ещё</Button>
    </div>
    <ConfigProvider theme={{ token: { colorText: '#e9e8eb', colorBgTextHover: '#ffffff14', colorBgTextActive: '#ffffff1c' } }}>
    <section className="bank-overview" aria-label="Сводка группы компаний">
      <div className="bank-overview-grid">
        <div className="balance-panel">
          <p className="balance-caption">В 3 компаниях</p>
          <strong className="balance-amount">{amount('18 450 000,00')} <span>RUB</span></strong>
          <p className="balance-hint">↳ {amount('20 450 000,00')} RUB с овердрафтом</p>
          <div className="currency-balances"><span>{amount('4 000,00')} CNY</span><span>{amount('40 000,00')} KZT</span><span className="currency-more">+2</span></div>
          <div className="balance-context"><span className="green-plus"><Plus size={12} aria-hidden="true" /></span><span>Все счета группы в одном месте</span></div>
          <div className="balance-shortcuts">
            <Button type="text" onClick={() => router.navigate(routes.section('Счета'))}><span><Wallet size={19} aria-hidden="true" /></span><span>Счета<small>2 в рублях, 2 в валюте</small></span></Button>
            <Button type="text" onClick={() => router.navigate(routes.section('Карты'))}><span><CreditCard size={19} aria-hidden="true" /></span><span>Бизнес-карты<small>Реквизиты и операции</small></span></Button>
          </div>
        </div>
        <div className="work-panel"><h2>Дела в работе</h2><div>
          {workItems.map((item) => <Button type="text" key={item.label} className={item.count === 0 ? 'is-empty' : ''}
            onClick={() => router.navigate(routes.section('Платежи в работе'))}><span>{item.label}</span><span className={`work-count${item.attention ? ' needs-attention' : ''}`}>{item.count}</span></Button>)}
        </div></div>
        <button type="button" className="card-promo" onClick={() => router.navigate(routes.section('Карты'))}>
          <strong>Умная карта для всех</strong><span>Для расходов вашей команды</span>
          <span className="card-illustration" aria-hidden="true"><span className="card-letter">А</span><span className="card-chip" /><span className="card-number">0000 &nbsp; 0000 &nbsp; 0000</span><span className="card-type">BUSINESS</span></span>
          <span className="card-promo-caption">Посмотреть карты <ArrowRight size={13} aria-hidden="true" /></span>
        </button>
      </div>
      <div className="bank-overview-footer"><Button type="text" onClick={() => router.navigate(routes.section('Реквизиты'))}>Реквизиты</Button><Button type="text" onClick={() => router.navigate(routes.section('Тариф'))}>Тариф</Button></div>
    </section>
    </ConfigProvider>
    <div className="summary-navigation">
      <nav aria-label="Разделы сводки"><Button type="text" aria-current="page" className="is-current" onClick={() => router.navigate(routes.home)}>Сводка</Button>
        {['Остатки по компаниям', 'Мультибанк', 'Металлы'].map((label) => <Button type="text" key={label} onClick={() => router.navigate(routes.section(label))}>{label}</Button>)}
      </nav>
      <div className="summary-controls"><Button type="text" size="small" aria-label={balancesVisible ? 'Скрыть суммы' : 'Показать суммы'} aria-pressed={!balancesVisible} onClick={() => setBalancesVisible(!balancesVisible)} icon={balancesVisible ? <Eye size={17} aria-hidden="true" /> : <EyeOff size={17} aria-hidden="true" />} /><Button type="text" size="small" aria-label="Настроить сводку" onClick={() => router.navigate(routes.section('Настройка сводки'))} icon={<Settings2 size={17} aria-hidden="true" />} /></div>
    </div>
  </>;
}
