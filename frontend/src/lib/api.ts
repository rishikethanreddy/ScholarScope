import axios, { AxiosError } from 'axios';
import type {
  Candidate,
  ChangeEvent,
  Job,
  Profile,
  Recommendations,
  RecommendationResult,
  Scholarship,
  ScholarshipDetail,
  SessionUser,
  Source,
  Vocabulary,
} from './types';

const TOKEN_KEY = 'scholarscope.token';

export const tokenStore = {
  get: (): string | null => {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (t: string | null) => {
    try {
      if (t) localStorage.setItem(TOKEN_KEY, t);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* storage unavailable: session lasts for this tab only */
    }
  },
};

export const http = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000', timeout: 120_000 });

http.interceptors.request.use((config) => {
  const t = tokenStore.get();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

export function errorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    if (!err.response) return 'Cannot reach the ScholarScope API. Is the backend running?';
    const detail = (err.response.data as { detail?: unknown })?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((d: { msg?: string; loc?: string[] }) => `${d.loc?.slice(-1)[0] ?? ''}: ${d.msg}`).join('; ');
    return `Request failed (HTTP ${err.response.status})`;
  }
  return err instanceof Error ? err.message : 'Unexpected error';
}

const get = async <T,>(url: string, params?: object) => (await http.get<T>(url, { params })).data;
const post = async <T,>(url: string, body?: object) => (await http.post<T>(url, body ?? {})).data;

export const api = {
  // auth
  register: (email: string, password: string) => post<{ token: string; user: SessionUser }>('/api/auth/register', { email, password }),
  login: (email: string, password: string) => post<{ token: string; user: SessionUser }>('/api/auth/login', { email, password }),
  me: () => get<SessionUser>('/api/auth/me'),

  // public
  vocabulary: () => get<Vocabulary>('/api/meta/vocabulary'),
  publicStats: () =>
    get<{
      published_scholarships: number;
      by_verification_status: Record<string, number>;
      enabled_sources: number;
      last_successful_check: string | null;
      material_changes_last_7_days: number;
      llm: { configured: boolean; provider: string; model: string };
      demo_mode: boolean;
    }>('/api/stats/public'),
  scholarships: (params: Record<string, string | undefined>) => get<{ total: number; items: Scholarship[] }>('/api/scholarships', params),
  scholarship: (id: string) => get<ScholarshipDetail>(`/api/scholarships/${id}`),
  scholarshipVersion: (id: string, v: number) => get<{ version: number; reason: string; created_at: string; snapshot: Record<string, unknown> }>(`/api/scholarships/${id}/versions/${v}`),
  feed: (days = 30) => get<{ since: string; changes: ChangeEvent[]; new_scholarships: { id: string; name: string; provider: string | null; first_discovered_at: string; deadline: string | null }[] }>('/api/feed/changes', { days }),

  // student
  profile: () => get<Profile | null>('/api/me/profile'),
  saveProfile: async (p: Profile) => {
    // The API rejects unknown fields, so drop server-managed ones (id, updated_at) that come back with a loaded profile.
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { id: _id, updated_at: _updatedAt, ...editable } = p;
    return (await http.put<Profile>('/api/me/profile', editable)).data;
  },
  deleteAccount: async () => (await http.delete('/api/me/account')).data,
  recommendations: () => get<Recommendations>('/api/me/recommendations'),
  recommendation: (id: string) => get<RecommendationResult>(`/api/me/recommendations/${id}`),
  acknowledgeUpdates: () => post('/api/me/updates/acknowledge'),
  answer: async (scholarship_id: string, criterion_key: string, answer: 'yes' | 'no' | 'unsure') =>
    (await http.put('/api/me/answers', { scholarship_id, criterion_key, answer })).data,
  saved: () => get<{ id: string; status: string; notes: string | null; created_at: string; scholarship: RecommendationResult['scholarship'] }[]>('/api/me/saved'),
  save: (scholarship_id: string, status = 'saved') => post<{ id: string }>('/api/me/saved', { scholarship_id, status }),
  updateSaved: async (id: string, body: { status?: string; notes?: string }) => (await http.patch(`/api/me/saved/${id}`, body)).data,
  unsave: async (id: string) => (await http.delete(`/api/me/saved/${id}`)).data,
  checkDocument: async (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return (await http.post('/api/me/check-document', fd)).data;
  },

  // admin
  admin: {
    overview: () => get<AdminOverview>('/api/admin/overview'),
    sources: () => get<Source[]>('/api/admin/sources'),
    createSource: (body: object) => post<Source>('/api/admin/sources', body),
    updateSource: async (id: string, body: object) => (await http.patch<Source>(`/api/admin/sources/${id}`, body)).data,
    checkSource: (id: string) => post<Job>(`/api/admin/sources/${id}/check`),
    pauseSource: (id: string, note?: string) => post<Source>(`/api/admin/sources/${id}/pause`, { note }),
    resumeSource: (id: string) => post<Source>(`/api/admin/sources/${id}/resume`),
    testSource: (id: string) => post<Record<string, unknown>>(`/api/admin/sources/${id}/test`),
    jobs: (params?: object) => get<Job[]>('/api/admin/jobs', params),
    job: (id: string) => get<Job>(`/api/admin/jobs/${id}`),
    retryJob: (id: string) => post<Job>(`/api/admin/jobs/${id}/retry`),
    candidates: (status = 'pending') => get<Candidate[]>('/api/admin/candidates', { status }),
    candidate: (id: string) => get<Candidate>(`/api/admin/candidates/${id}`),
    approve: (id: string, payload: object | null, note?: string) => post<{ scholarship_id: string }>(`/api/admin/candidates/${id}/approve`, { payload, note }),
    reject: (id: string, note?: string) => post(`/api/admin/candidates/${id}/reject`, { note }),
    link: (id: string, scholarship_id: string) => post<{ scholarship_id: string }>(`/api/admin/candidates/${id}/link`, { scholarship_id }),
    extract: (id: string) => post<Candidate>(`/api/admin/candidates/${id}/extract`),
    changes: (status = 'pending') => get<ChangeEvent[]>('/api/admin/changes', { status }),
    acceptChange: (id: string, note?: string) => post(`/api/admin/changes/${id}/accept`, { note }),
    rejectChange: (id: string, note?: string) => post(`/api/admin/changes/${id}/reject`, { note }),
    quality: () => get<AdminQuality>('/api/admin/quality'),
    datasets: () => get<AdminDataset[]>('/api/admin/datasets'),
    importDataset: async (file: File, version: string, dataset_name: string, mode: string) => {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('version', version);
      fd.append('dataset_name', dataset_name);
      fd.append('mode', mode);
      return (await http.post('/api/admin/datasets/import', fd)).data;
    },
    document: (id: string) => get<Record<string, unknown>>(`/api/admin/documents/${id}`),
    audit: () => get<{ id: string; actor_email: string | null; action: string; entity_type: string; entity_id: string | null; details: Record<string, unknown>; created_at: string }[]>('/api/admin/audit'),
    evaluation: () => get<Record<string, unknown>>('/api/admin/evaluation'),
  },
};

export interface AdminOverview {
  generated_at: string;
  scholarships: { published: number; by_verification_status: Record<string, number>; stale: { id: string; name: string; last_checked_at: string | null }[]; unpublished: number };
  sources: Source[];
  jobs: { last_24h: Record<string, number>; all_time: Record<string, number>; success_rate: number | null; running: number; recent_failures: Job[] };
  review: { pending_candidates: number; pending_changes: number; extraction_failures: number };
  changes_last_7_days: { material: number; cosmetic: number; auto_accepted: number };
  recent_changes: ChangeEvent[];
  datasets: { version: string; imported_at: string; rows: number; created: number; updated: number; rejected: number }[];
  scheduler: { running: boolean; last_tick_at: string | null; last_enqueued: string[]; enabled: boolean };
  llm: { configured: boolean; provider: string; model: string };
}

export interface AdminQuality {
  duplicate_candidates: { a_id: string; a_name: string; b_id: string; b_name: string; score: number; url_match: boolean }[];
  unresolved_fields: Record<string, number>;
  stale: { id: string; name: string; last_checked_at: string | null }[];
  never_checked: { id: string; name: string }[];
  conflicts: { id: string; name: string }[];
}

export interface AdminDataset {
  id: string;
  version: string;
  dataset_name: string;
  file_name: string;
  file_sha256: string;
  imported_at: string;
  rows: number;
  created: number;
  updated: number;
  unchanged: number;
  rejected: number;
  report: { rows: { line: number; external_id: string; status: string; issues: string[] }[]; unknown_counts: Record<string, number>; rows_with_issues: number; mode: string };
}
