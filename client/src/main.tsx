import '@/app/styles/index.scss';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App, startModelSync } from '@/app';

const stopModelSync = startModelSync();
if (import.meta.hot) import.meta.hot.dispose(stopModelSync);

createRoot(document.getElementById('root')!).render(
  <StrictMode><App /></StrictMode>,
);
