import { Button, Menu, Tag, type MenuProps } from 'antd';
import {
  ArrowRightLeft, BookOpen, Building2, CreditCard, FileInput, FileText,
  FilePlus2, Inbox, LayoutGrid, Lightbulb, List, Plus, Settings2, Users,
} from 'lucide-react';
import { observer } from 'mobx-react-lite';
import { router, routes } from '@/shared/routing';
import { Brand } from '@/shared/ui/brand';
import { shellStore as store } from '../model/shell-store';

const items: MenuProps['items'] = [
  { key: routes.section('Все сервисы и продукты'), icon: <LayoutGrid size={17} aria-hidden="true" />, label: 'Все сервисы' },
  { type: 'divider' },
  { key: routes.insights, icon: <Lightbulb size={17} aria-hidden="true" />, label: 'Бизнес-инсайты' },
  { key: routes.section('Заявки'), icon: <FileText size={17} aria-hidden="true" />,
    label: <span className="sidebar-menu-label">Заявки<Tag color="blue">НОВОЕ</Tag></span> },
  { key: routes.section('Новый платёж'), icon: <Plus size={17} aria-hidden="true" />, label: 'Новый платёж' },
  { key: routes.section('Лента операций'), icon: <Inbox size={17} aria-hidden="true" />, label: 'Лента операций' },
  { key: routes.section('Платежи в работе'), icon: <ArrowRightLeft size={17} aria-hidden="true" />, label: 'Платежи в работе' },
  { key: routes.section('Импорт реестров'), icon: <FileInput size={17} aria-hidden="true" />, label: 'Импорт реестров' },
  { key: routes.section('Выписка'), icon: <FileText size={17} aria-hidden="true" />, label: 'Выписка' },
  { key: routes.section('Счета'), icon: <List size={17} aria-hidden="true" />, label: 'Счета' },
  { key: routes.section('Контрагенты'), icon: <Users size={17} aria-hidden="true" />, label: 'Контрагенты' },
  { key: routes.section('Справки'), icon: <FilePlus2 size={17} aria-hidden="true" />, label: 'Справки' },
  { key: routes.section('Счета на оплату'), icon: <BookOpen size={17} aria-hidden="true" />, label: 'Счета на оплату' },
  { key: routes.section('Карты'), icon: <CreditCard size={17} aria-hidden="true" />, label: 'Карты' },
  { type: 'divider' },
  { key: routes.section('Госзакупки'), icon: <Building2 size={17} aria-hidden="true" />, label: 'Госзакупки' },
];

export const Sidebar = observer(function Sidebar() {
  return <aside className={`sidebar${store.mobileMenuOpen ? ' is-open' : ''}`} id="sidebar">
    <a className="brand" href="#/" aria-label="Альфа-Бизнес — на главную"
      onClick={(event) => { event.preventDefault(); router.navigate(routes.home); }}><Brand /></a>
    <nav className="navigation" aria-label="Основная навигация">
      <Menu className="sidebar-menu" mode="inline" inlineIndent={8} selectedKeys={[router.path.startsWith(routes.insights) ? routes.insights : router.path]}
        items={items} onClick={({ key }) => router.navigate(key)} />
    </nav>
    <Button type="text" className="menu-settings" icon={<Settings2 size={17} aria-hidden="true" />}
      onClick={() => router.navigate(routes.section('Настройка меню'))}>Настроить меню</Button>
  </aside>;
});
