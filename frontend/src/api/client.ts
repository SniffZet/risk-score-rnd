import type {
  ChurnChart, CustomerDetail, CustomerList, CustomersQuery, ExportQuery, ModelSettings, Providers, SettingsPatch,
  SettingsPreview, SnapshotResult, Summary, Token, Transition, User,
} from './types';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const TOKEN_KEY = 'risk_token';
let token: string | null = null;
try { token = localStorage.getItem(TOKEN_KEY); } catch {}

function setToken(value: string | null) {
  token = value;
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {}
}

try {
  const sso = /[#&]token=([^&]+)/.exec(window.location.hash);
  if (sso) {
    setToken(decodeURIComponent(sso[1]));
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
  }
} catch {}

export const hasToken = () => token !== null;
export const authHeaders = (): Record<string, string> => (token ? { Authorization: `Bearer ${token}` } : {});

let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn: () => void) => { onUnauthorized = fn; };

export function handleUnauthorized() {
  setToken(null);
  onUnauthorized();
}

function errorText(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? JSON.stringify(d)).join('; ');
  return fallback;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { ...authHeaders() };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });

  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    if (res.status === 401 && path !== '/api/v1/auth/login') handleUnauthorized();
    throw new ApiError(res.status, errorText(payload, `${res.status} ${res.statusText}`));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

function query(params: object): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') q.set(k, String(v));
  }
  return q.toString();
}

export const api = {
  providers: () => request<Providers>('GET', '/api/v1/auth/providers'),
  login: async (username: string, password: string) => {
    const t = await request<Token>('POST', '/api/v1/auth/login', { username, password });
    setToken(t.access_token);
    return request<User>('GET', '/api/v1/auth/me');
  },
  me: () => request<User>('GET', '/api/v1/auth/me'),
  logout: async () => {
    try {
      await request<unknown>('POST', '/api/v1/auth/logout');
    } finally {
      setToken(null);
    }
  },

  customers: (q: CustomersQuery) => request<CustomerList>('GET', `/api/v1/customers?${query(q)}`),
  customer: (id: number) => request<CustomerDetail>('GET', `/api/v1/customers/${id}`),
  exportCsv: async (q: ExportQuery) => {
    const res = await fetch(`/api/v1/customers/export.csv?${query(q)}`, { headers: authHeaders() });
    if (res.status === 401) handleUnauthorized();
    if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`);
    return res.blob();
  },

  summary: () => request<Summary>('GET', '/api/v1/analytics/summary'),
  churnChart: () => request<ChurnChart>('GET', '/api/v1/analytics/churn-chart'),
  journal: (q: { account_id?: number; service_id?: number; limit?: number }) =>
    request<Transition[]>('GET', `/api/v1/analytics/journal?${query(q)}`),

  settings: () => request<ModelSettings>('GET', '/api/v1/model/settings'),
  patchSettings: (patch: SettingsPatch) => request<ModelSettings>('PATCH', '/api/v1/model/settings', patch),
  previewSettings: (patch: SettingsPatch) => request<SettingsPreview>('POST', '/api/v1/model/settings/preview', patch),

  putSnapshot: (snapshot: unknown) => request<SnapshotResult>('PUT', '/api/v1/source/snapshot', snapshot),
  patchSnapshot: (partial: unknown) => request<SnapshotResult>('PATCH', '/api/v1/source/snapshot', partial),
};
