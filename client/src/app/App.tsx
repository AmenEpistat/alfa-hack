import { useEffect } from 'react';
import { router } from '@/shared/routing';
import { sessionStore } from '@/entities/session';
import { AppRouter } from './router/AppRouter';
import { UiProvider } from './providers/UiProvider';

export function App() {
  useEffect(() => {
    void sessionStore.bootstrap();
    window.addEventListener('hashchange', router.syncFromLocation);
    window.addEventListener('popstate', router.syncFromLocation);
    return () => {
      window.removeEventListener('hashchange', router.syncFromLocation);
      window.removeEventListener('popstate', router.syncFromLocation);
    };
  }, []);
  return <UiProvider><AppRouter /></UiProvider>;
}
