import { Button } from 'antd';
import { useEffect, type ReactNode } from 'react';
import { Menu, X } from 'lucide-react';
import { observer } from 'mobx-react-lite';
import { Brand } from '@/shared/ui/brand';
import { router, routes } from '@/shared/routing';
import { shellStore as store } from '../model/shell-store';
import { Sidebar } from './Sidebar';
import { WorkspaceHeader } from './WorkspaceHeader';
import './bank-shell.scss';

export const BankShell = observer(function BankShell({ children }: { children: ReactNode }) {
  useEffect(() => { store.closeMobileMenu(); }, [router.path]);
  return (
    <div className="app-shell" onKeyDown={(event) => { if (event.key === 'Escape') store.closeMobileMenu(); }}>
      <header className="mobile-header">
        <Button type="text" className="mobile-toggle" aria-label={store.mobileMenuOpen ? 'Закрыть меню' : 'Открыть меню'}
          aria-expanded={store.mobileMenuOpen} aria-controls="sidebar" onClick={store.toggleMobileMenu}
          icon={store.mobileMenuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />} />
        <span className="mobile-brand"><Brand /></span>
      </header>
      {store.mobileMenuOpen && <button type="button" className="menu-backdrop" aria-label="Закрыть меню"
        onClick={store.closeMobileMenu} />}
      <Sidebar />
      <main className="workspace" aria-label="Рабочая область">
        <WorkspaceHeader />
        <div className={`page-content${router.path === routes.home ? ' page-content--home' : ''}`}>{children}</div>
      </main>
    </div>
  );
});
