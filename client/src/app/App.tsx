import { useEffect } from 'react';
import { router } from '@/shared/routing';
import { AppRouter } from './router/AppRouter';
import { UiProvider } from './providers/UiProvider';

export function App() {
  useEffect(() => {
    window.addEventListener('hashchange', router.syncFromLocation);
    window.addEventListener('popstate', router.syncFromLocation);
    return () => {
      window.removeEventListener('hashchange', router.syncFromLocation);
      window.removeEventListener('popstate', router.syncFromLocation);
    };
  }, []);
  return <UiProvider><AppRouter /></UiProvider>;
}
