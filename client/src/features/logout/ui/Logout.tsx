import { LogOut } from 'lucide-react';
import { Button } from 'antd';
import { sessionStore } from '@/entities/session';

export function Logout() {
  return <Button type="text" className="logout-button" size="small" aria-label="Выйти" title="Выйти"
    icon={<LogOut size={16} aria-hidden="true" />} onClick={sessionStore.logout} />;
}
