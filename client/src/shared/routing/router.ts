import { makeAutoObservable } from 'mobx';

export const routes = {
  home: '/',
  insights: '/insights',
  insight: (id: string) => `/insights/${encodeURIComponent(id)}`,
  section: (label: string) => `/sections/${encodeURIComponent(label)}`,
};

class RouterStore {
  path = window.location.hash.slice(1) || '/';

  constructor() { makeAutoObservable(this, {}, { autoBind: true }); }

  navigate(path: string) {
    const hash = `#${path}`;
    if (window.location.hash !== hash) window.history.pushState(null, '', hash);
    this.syncFromLocation();
  }

  syncFromLocation() {
    this.path = window.location.hash.slice(1) || '/';
    window.scrollTo({ top: 0 });
  }
}

export const router = new RouterStore();

export function getPageUrl(path: string) {
  const url = new URL(window.location.href);
  url.search = '';
  url.hash = path;
  return url.toString();
}
