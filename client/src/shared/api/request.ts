import { staticDemoResponse } from './static-demo';

export class ApiError extends Error {
  constructor(message: string, public readonly status = 0) { super(message); this.name = 'ApiError'; }
}

export function normalizeApiBase(value = '/api') {
  const base = value.trim().replace(/\/+$/, '');
  if (!base) return '/api';
  if (base.startsWith('/') && !base.startsWith('//')) return base;
  const url = new URL(base);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Некорректный адрес API');
  return `${url.origin}${url.pathname === '/' ? '/api' : url.pathname.replace(/\/+$/, '')}`;
}

const baseUrl = normalizeApiBase(import.meta.env?.VITE_API_URL);
const staticDemo = import.meta.env?.VITE_DEMO_MODE === 'true';
let accessToken: string | null = null;
export function setAccessToken(token: string | null) { accessToken = token; }
export function getApiUrl(path: string) { return `${baseUrl}/${path.replace(/^\/+/, '')}`; }
export function resolveApiAssetUrl(path?: string | null) {
  if (!path) return undefined;
  if (path.startsWith('/api/assets/')) return getApiUrl(path.slice(5));
  try { const url = new URL(path); return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : undefined; }
  catch { return undefined; }
}

async function apiResponse(path: string, options: RequestInit & { timeoutMs?: number } = {}): Promise<Response> {
  const controller = new AbortController();
  const { timeoutMs = 15_000, ...fetchOptions } = options;
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const onAbort = () => controller.abort();
  if (options.signal?.aborted) controller.abort();
  options.signal?.addEventListener('abort', onAbort, { once: true });
  try {
    const headers = new Headers(options.headers);
    if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
    const response = staticDemo
      ? await staticDemoResponse(path, fetchOptions, accessToken)
      : await fetch(getApiUrl(path), { ...fetchOptions, headers, signal: controller.signal });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const message = typeof body?.detail === 'string' ? body.detail : `Ошибка сервера (${response.status}). Повторите запрос.`;
      throw new ApiError(message, response.status);
    }
    return response;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (options.signal?.aborted) throw error;
    throw new ApiError('Не удалось связаться с сервером. Повторите попытку.');
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener('abort', onAbort);
  }
}

export async function apiRequest<T>(path: string, options: RequestInit & { timeoutMs?: number } = {}): Promise<T> {
  const response = await apiResponse(path, options);
  if (response.status === 204) return undefined as T;
  try { return await response.json() as T; }
  catch { throw new ApiError('Сервер вернул данные в неожиданном формате.', response.status); }
}
export async function apiDownload(path: string): Promise<Blob> { return (await apiResponse(path)).blob(); }
