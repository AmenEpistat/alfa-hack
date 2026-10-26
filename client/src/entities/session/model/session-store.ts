import { makeAutoObservable, runInAction } from 'mobx';
import { apiRequest, ApiError, setAccessToken } from '@/shared/api';

export type User = { id: string; name: string; initials: string; role: string; audience_type: string };
const sessionKey = 'alfa-hackathon:api-session:v1';
function readToken() { try { return sessionStorage.getItem(sessionKey); } catch { return null; } }

class SessionStore {
  user: User | null = null;
  users: User[] = [];
  initialising = true;
  pending = false;
  error = '';
  private token: string | null = readToken();
  private started = false;
  constructor() { makeAutoObservable(this, {}, { autoBind: true }); setAccessToken(this.token); }
  get userId() { return this.user?.id ?? null; }
  async bootstrap() {
    if (this.started) return;
    this.started = true; this.initialising = true; this.error = '';
    try {
      const users = await apiRequest<User[]>('/auth/users');
      runInAction(() => { this.users = users; });
      if (this.token) {
        try {
          const user = await apiRequest<User>(`/auth/me?token=${encodeURIComponent(this.token)}`);
          runInAction(() => { this.user = user; });
        } catch (error) {
          if (error instanceof ApiError && error.status === 401) this.logout();
          else throw error;
        }
      }
    } catch (error) {
      runInAction(() => { this.error = error instanceof Error ? error.message : 'Не удалось загрузить пользователей.'; this.started = false; });
    } finally { runInAction(() => { this.initialising = false; }); }
  }
  async login(userId: string) {
    if (this.pending) return;
    this.pending = true; this.error = '';
    try {
      const result = await apiRequest<{ access_token: string; user: User }>('/auth/login', { method: 'POST', body: JSON.stringify({ user_id: userId }) });
      setAccessToken(result.access_token);
      runInAction(() => { this.token = result.access_token; this.user = result.user; });
      try { sessionStorage.setItem(sessionKey, result.access_token); } catch { /* Session remains in memory. */ }
    } catch (error) { runInAction(() => { this.error = error instanceof Error ? error.message : 'Не удалось войти.'; }); }
    finally { runInAction(() => { this.pending = false; }); }
  }
  logout() {
    this.user = null; this.token = null; setAccessToken(null);
    try { sessionStorage.removeItem(sessionKey); } catch { /* Session already cleared in memory. */ }
  }
}
export const sessionStore = new SessionStore();
