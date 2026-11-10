import type {
  ChatSession,
  ChatSessionCreateRequest,
  CreateAndRunRequest,
  CreateAndRunResponse,
  IssueCreateRequest,
  IssueListResponse,
  Project,
  ProjectListResponse,
  QuotaResponse,
  Run,
  RunCreateRequest,
  RunDiffResponse,
  RunListResponse,
  RunReviewRequest,
  RunReviewResponse,
  StorageInfoResponse,
  StoragePruneResponse,
} from './types';

function getApiBase(): string {
  const custom = localStorage.getItem('AGY_API_BASE');
  if (custom) return custom.replace(/\/+$/, '');
  return '';
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const base = getApiBase();
  const url = `${base}${endpoint}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new Error(errorDetail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  // Projects
  getProjects: () => request<ProjectListResponse>('/api/projects'),
  selectProject: (id: string) => request<Project>(`/api/projects/${id}/select`, { method: 'POST' }),
  registerProject: (path: string) => request<Project>('/api/projects', {
    method: 'POST',
    body: JSON.stringify({ path }),
  }),

  // Issues
  getActiveIssues: () => request<IssueListResponse>('/api/projects/active/issues'),
  createActiveIssue: (payload: IssueCreateRequest) => request<unknown>('/api/projects/active/issues', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),

  // Runs
  getRuns: (status?: string, projectId?: string) => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (projectId) params.set('project_id', projectId);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return request<RunListResponse>(`/api/runs${qs}`);
  },
  getRun: (id: string) => request<Run>(`/api/runs/${id}`),
  startRun: (payload: RunCreateRequest) => request<Run>('/api/runs', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  abortRun: (id: string) => request<Run>(`/api/runs/${id}/abort`, {
    method: 'POST',
  }),
  getRunDiff: (id: string) => request<RunDiffResponse>(`/api/runs/${id}/diff`),
  submitReview: (id: string, payload: RunReviewRequest) => request<RunReviewResponse>(`/api/runs/${id}/review`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  }),

  // System & Quota & Storage
  getQuota: (forceRefresh = false) => {
    const qs = forceRefresh ? '?force_refresh=true' : '';
    return request<QuotaResponse>(`/api/system/quota${qs}`);
  },
  getStorageInfo: (projectId?: string) => {
    const qs = projectId ? `?project_id=${projectId}` : '';
    return request<StorageInfoResponse>(`/api/system/storage${qs}`);
  },
  pruneStorage: (projectId?: string) => {
    const qs = projectId ? `?project_id=${projectId}` : '';
    return request<StoragePruneResponse>(`/api/system/storage/prune${qs}`, {
      method: 'POST',
    });
  },

  // Interactive AI Formulation Chat
  createChatSession: (payload: ChatSessionCreateRequest) =>
    request<ChatSession>('/api/chat-sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getChatSession: (sessionId: string) =>
    request<ChatSession>(`/api/chat-sessions/${sessionId}`),

  sendChatMessage: (sessionId: string, content: string) =>
    request<ChatSession>(`/api/chat-sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),

  terminateChatSession: (sessionId: string) =>
    request<ChatSession>(`/api/chat-sessions/${sessionId}/terminate`, {
      method: 'POST',
    }),

  createAndRunFromChat: (sessionId: string, payload: CreateAndRunRequest) =>
    request<CreateAndRunResponse>(`/api/chat-sessions/${sessionId}/create-and-run`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getChatStreamUrl: (sessionId: string) => {
    const base = getApiBase();
    return `${base}/api/chat-sessions/${sessionId}/stream`;
  },

  // SSE Stream URL
  getRunStreamUrl: (id: string) => {
    const base = getApiBase();
    return `${base}/api/runs/${id}/stream`;
  },
};
