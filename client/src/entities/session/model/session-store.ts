import { makeAutoObservable } from 'mobx';

export const demoUsers = [
  { id: 'anna', name: 'Анна Смирнова', initials: 'АС', role: 'Финансовый директор' },
  { id: 'ilya', name: 'Илья Воронов', initials: 'ИВ', role: 'Казначей' },
] as const;

const sessionKey = 'alfa-hackathon:demo-session:v1';

function readSession() {
  try { return sessionStorage.getItem(sessionKey); } catch { return null; }
}

class SessionStore {
  userId: string | null = readSession();

  constructor() {
    makeAutoObservable(this, {}, { autoBind: true });
  }

  get user() { return demoUsers.find((user) => user.id === this.userId) ?? null; }

  login(userId: string) {
    if (!demoUsers.some((user) => user.id === userId)) return;
    this.userId = userId;
    try { sessionStorage.setItem(sessionKey, userId); } catch { /* Keep the in-memory demo session. */ }
  }

  logout() {
    this.userId = null;
    try { sessionStorage.removeItem(sessionKey); } catch { /* The in-memory session is already cleared. */ }
  }
}

export const sessionStore = new SessionStore();
