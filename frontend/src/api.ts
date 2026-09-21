export interface User {
  id: number | string;
  email: string;
  name: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: string;
}

export interface Workspace {
  id: string;
  organization: string;
  name: string;
  slug: string;
  status: string;
  container_status?: string;
}

export interface Session {
  id: string;
  workspace: string;
  workspace_name: string;
  title: string;
  model: string;
  reasoning: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "tool" | "system";
  content: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  meta?: any;
}

export interface ToolCall {
  id: string;
  name: string;
  arguments: any;
}

export interface OllamaModel {
  name: string;
  size: number;
}

export interface PermissionRequest {
  id: string;
  call_id: string;
  tool: string;
  arguments: any;
  preview: string;
  status: string;
  created_at: string;
}

const TOKEN_KEY = "cyonima.token";
const REFRESH_KEY = "cyonima.refresh";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setTokens(access: string, refresh: string) {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}
export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`/api${path}`, { ...opts, headers });
  if (res.status === 401) {
    clearTokens();
    window.location.href = "/login";
    throw new Error("Non authentifié");
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function listResult<T>(data: any): T[] {
  if (Array.isArray(data)) return data;
  return data?.results ?? [];
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access: string; refresh: string; user: User }>("/auth/login/", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (email: string, name: string, password: string) =>
    request<User>("/auth/register/", {
      method: "POST",
      body: JSON.stringify({ email, name, password }),
    }),
  me: () => request<User>("/auth/me/"),
  ssoProviders: () =>
    request<{ providers: { id: string; name: string; login_url: string }[] }>(
      "/auth/sso/",
    ),

  orgs: async () => listResult<Organization>(await request("/orgs/")),
  createOrg: (name: string, slug: string) =>
    request<Organization>("/orgs/", {
      method: "POST",
      body: JSON.stringify({ name, slug }),
    }),

  workspaces: async (orgId: string) =>
    listResult<Workspace>(await request(`/orgs/${orgId}/workspaces/`)),
  createWorkspace: (orgId: string, name: string, slug: string, gitUrl?: string) =>
    request<Workspace>(`/orgs/${orgId}/workspaces/`, {
      method: "POST",
      body: JSON.stringify({ name, slug, git_url: gitUrl || "" }),
    }),

  sessions: async (workspaceId?: string) =>
    listResult<Session>(
      await request(`/sessions/${workspaceId ? `?workspace=${workspaceId}` : ""}`),
    ),
  createSession: (workspaceId: string, model?: string) =>
    request<Session>("/sessions/", {
      method: "POST",
      body: JSON.stringify({ workspace: workspaceId, model: model || "" }),
    }),
  deleteSession: (id: string) =>
    request<void>(`/sessions/${id}/`, { method: "DELETE" }),
  forkSession: (id: string) =>
    request<Session>(`/sessions/${id}/fork/`, { method: "POST" }),
  history: (id: string) => request<Message[]>(`/sessions/${id}/history/`),
  permissions: (id: string) =>
    request<PermissionRequest[]>(`/sessions/${id}/permissions/`),
  respondPermission: (id: string, callId: string, approved: boolean) =>
    request<{ status: string }>(`/sessions/${id}/respond/`, {
      method: "POST",
      body: JSON.stringify({ call_id: callId, approved }),
    }),
  gitStatus: (id: string) =>
    request<{ is_repo: boolean; changes: { status: string; path: string }[] }>(
      `/sessions/${id}/git-status/`,
    ),

  ollamaModels: () =>
    request<{ models: OllamaModel[]; default_model: string }>("/ollama/models/"),
  pullModel: (name: string) =>
    request<{ task_id?: string; model: string; status: string }>(
      `/ollama/models/${name}/pull/`,
      { method: "POST" },
    ),
  pullStatus: (taskId: string) =>
    request<{
      task_id: string;
      model: string;
      status: string;
      message: string;
      percent: number;
      completed: number;
      total: number;
    }>(`/ollama/pulls/${taskId}/`),
  deleteModel: (name: string) =>
    request<{ deleted: string }>(`/ollama/models/${name}/`, { method: "DELETE" }),
};

export function wsUrl(sessionId: string): string {
  const token = getToken();
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const base = `${proto}://${location.host}`;
  return `${base}/ws/sessions/${sessionId}/?token=${token}`;
}

export async function sessionToken(): Promise<{
  access: string;
  refresh: string;
  user: User;
}> {
  const res = await fetch("/api/auth/session-token/", { credentials: "include" });
  if (!res.ok) throw new Error("Non authentifié via SSO");
  return res.json();
}
