import { Avatar, Button } from 'antd';
import { Bell, Mail } from 'lucide-react';
import { observer } from 'mobx-react-lite';
import { sessionStore } from '@/entities/session';
import { Logout } from '@/features/logout';
import { router, routes } from '@/shared/routing';

export const WorkspaceHeader = observer(function WorkspaceHeader() {
  return <header className="workspace-header">
      <div className="header-tools"><Button type="text" size="small" aria-label="Сообщения" onClick={() => router.navigate(routes.section('Сообщения'))} icon={<Mail size={16} aria-hidden="true" />} /><Button type="text" size="small" aria-label="Уведомления" onClick={() => router.navigate(routes.section('Уведомления'))} icon={<Bell size={16} aria-hidden="true" />} /></div>
      <div className="header-company"><Avatar shape="square" size={29} className="company-monogram" aria-hidden="true">С</Avatar><div><strong>Мои компании</strong><span>ГК «Северстрой» · 3 компании</span></div></div>
      <div className="header-profile"><Avatar size={27} className="profile-avatar" aria-hidden="true">{sessionStore.user?.initials}</Avatar><span>{sessionStore.user?.name}<small>Демодоступ</small></span></div>
      <Logout />
    </header>;
});
