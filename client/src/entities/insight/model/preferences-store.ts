import { makeAutoObservable } from 'mobx';
import { insightId } from './insight';

export type Feedback = 'useful' | 'not-useful' | null;

type Preferences = {
  saved: boolean;
  hidden: boolean;
  feedback: Feedback;
  reason: string;
  taskCreated: boolean;
  savedIds: string[];
};

const legacyStorageKey = 'alfa-hackathon:steel-insight:v1';
const storageKey = (userId: string) => `alfa-hackathon:${userId}:steel-insight:v1`;

function readPreferences(userId: string | null): Partial<Preferences> {
  if (!userId) return {};
  try {
    const stored = localStorage.getItem(storageKey(userId));
    const legacy = userId === 'anna' ? localStorage.getItem(legacyStorageKey) : null;
    const value = JSON.parse(stored ?? legacy ?? '{}');
    return value && typeof value === 'object' ? value : {};
  } catch {
    return {};
  }
}

class InsightPreferencesStore {
  private userId: string | null = null;
  saved = false;
  hidden = false;
  feedback: Feedback = null;
  reason = '';
  taskCreated = false;
  savedIds: string[] = [];

  constructor() {
    makeAutoObservable(this, {}, { autoBind: true });
  }

  setUser(userId: string | null) {
    this.userId = userId;
    const preferences = readPreferences(userId);
    this.saved = preferences.saved === true;
    this.hidden = preferences.hidden === true;
    this.feedback = preferences.feedback === 'useful' || preferences.feedback === 'not-useful' ? preferences.feedback : null;
    this.reason = typeof preferences.reason === 'string' ? preferences.reason : '';
    this.taskCreated = preferences.taskCreated === true;
    this.savedIds = Array.isArray(preferences.savedIds) ? preferences.savedIds.filter((id): id is string => typeof id === 'string' && id !== insightId) : [];
  }

  private persist() {
    if (!this.userId) return;
    try {
      localStorage.setItem(storageKey(this.userId), JSON.stringify({
        saved: this.saved, hidden: this.hidden, feedback: this.feedback,
        reason: this.reason, taskCreated: this.taskCreated, savedIds: this.savedIds,
      }));
    } catch {
      // The prototype remains usable when browser storage is unavailable.
    }
  }

  toggleSaved() { this.saved = !this.saved; this.persist(); }
  isSaved(id: string) { return id === insightId ? this.saved : this.savedIds.includes(id); }
  toggleSavedFor(id: string) {
    if (id === insightId) { this.toggleSaved(); return; }
    this.savedIds = this.savedIds.includes(id) ? this.savedIds.filter(value => value !== id) : [...this.savedIds, id];
    this.persist();
  }
  setHidden(hidden: boolean) { this.hidden = hidden; this.persist(); }
  setFeedback(feedback: Feedback) {
    this.feedback = this.feedback === feedback ? null : feedback;
    this.reason = '';
    this.persist();
  }
  setReason(reason: string) { this.reason = reason; this.persist(); }
  createTask() { this.taskCreated = true; this.persist(); }
  removeTask() { this.taskCreated = false; this.persist(); }
}

export const insightPreferencesStore = new InsightPreferencesStore();
