import { Avatar, Button } from 'antd';
import { Bell, Mail } from 'lucide-react';
import { observer } from 'mobx-react-lite';
import { insightsStore } from '@/entities/insight';
import { sessionStore } from '@/entities/session';
import { Logout } from '@/features/logout';
import { router, routes } from '@/shared/routing';

export const WorkspaceHeader = observer(function WorkspaceHeader() {
  const count = insightsStore.profile?.companies.length ?? 0;
  const companyWord = { zero: 'компаний', two: 'компании', one: 'компания', few: 'компании', many: 'компаний', other: 'компании' }[new Intl.PluralRules('ru').select(count)] ?? 'компаний';
  const companyName = insightsStore.profile?.name;
  const companyCaption = count ? `${count} ${companyWord}` : 'Компания не выбрана';
  return <header className="workspace-header">
      <div className="header-tools"><Button type="text" size="small" aria-label="Сообщения" onClick={() => router.navigate(routes.section('Сообщения'))} icon={<Mail size={16} aria-hidden="true" />} /><Button type="text" size="small" aria-label="Уведомления" onClick={() => router.navigate(routes.section('Уведомления'))} icon={<Bell size={16} aria-hidden="true" />} /></div>
      <div className="header-company"><Avatar shape="square" size={29} className="company-monogram" aria-hidden="true">С</Avatar><div><strong>Мои компании</strong><span>{companyName && companyName !== 'Мои компании' ? `${companyName} · ` : ''}{companyCaption}</span></div></div>
      <div className="header-profile"><Avatar size={27} className="profile-avatar" aria-hidden="true">{sessionStore.user?.initials}</Avatar><span>{sessionStore.user?.name}</span></div>
      <Logout />
    </header>;
});
