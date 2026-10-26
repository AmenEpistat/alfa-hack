import { reaction } from 'mobx';
import { sessionStore } from '@/entities/session';
import { insightPreferencesStore, insightAnalysisStore, insightsStore } from '@/entities/insight';

export function startModelSync() {
  return reaction(() => sessionStore.user?.id ?? null, (userId) => {
    insightPreferencesStore.setUser(userId);
    insightAnalysisStore.reset();
    if (userId) {
      void insightsStore.load();
      void insightPreferencesStore.load();
    } else insightsStore.reset();
  }, { fireImmediately: true });
}
