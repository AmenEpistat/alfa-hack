import { reaction } from 'mobx';
import { sessionStore } from '@/entities/session';
import { insightPreferencesStore, insightAnalysisStore } from '@/entities/insight';

export function startModelSync() {
  return reaction(() => sessionStore.user?.id ?? null, (userId) => {
    insightPreferencesStore.setUser(userId);
    insightAnalysisStore.reset();
  }, { fireImmediately: true });
}
