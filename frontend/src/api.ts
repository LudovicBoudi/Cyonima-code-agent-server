export interface User {
  id: number | string;
  email: string;
  name: string;
  is_staff?: boolean;
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
  local_path?: string;
  container_status?: string;
}

export interface Session {
  id: string;
  workspace: string;
  workspace_name: string;
  title: string;
  model: string;
  reasoning: string;
  local_path?: string;
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

export interface CatalogModel {
  id: string;
  name: string;
  quantization: string;
  license: string;
  ram_min_gb: number;
  model_type: "general" | "coding";
  ollama_tag: string;
  installed: boolean;
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

export interface AdminUser {
  id: number | string;
  email: string;
  name: string;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  date_joined: string;
  last_login?: string | null;
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

  let res = await fetch(`/api${path}`, { ...opts, headers });
  if (res.status === 401 && !path.startsWith("/auth/")) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${getToken()}`;
      res = await fetch(`/api${path}`, { ...opts, headers });
    }
  }
  if (res.status === 401) {
    clearTokens();
    window.location.href = "/login";
    throw new Error("Non authentifié");
  }
  if (!res.ok) {
    let message = `Erreur ${res.status}`;
    try {
      const body = await res.json();
      const parsed = drfError(body);
      if (parsed) message = parsed;
    } catch {
      /* corps non-JSON */
    }
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

async function tryRefresh(): Promise<boolean> {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) return false;
  try {
    const r = await fetch("/api/auth/refresh/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!r.ok) return false;
    const data = await r.json();
    if (data.access) localStorage.setItem(TOKEN_KEY, data.access);
    if (data.refresh) localStorage.setItem(REFRESH_KEY, data.refresh);
    return true;
  } catch {
    return false;
  }
}

function drfError(body: any): string | null {
  if (typeof body === "string") return body;
  if (Array.isArray(body)) return body.join(", ");
  if (body && typeof body === "object") {
    const parts: string[] = [];
    for (const [key, value] of Object.entries(body)) {
      if (Array.isArray(value)) parts.push(`${key}: ${value.join(", ")}`);
      else if (typeof value === "string") parts.push(`${key}: ${value}`);
      else parts.push(key);
    }
    return parts.join("; ");
  }
  return null;
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
  createWorkspace: (
    orgId: string,
    name: string,
    slug: string,
    gitUrl?: string,
    localPath?: string,
  ) =>
    request<Workspace>(`/orgs/${orgId}/workspaces/`, {
      method: "POST",
      body: JSON.stringify({
        name,
        slug,
        git_url: gitUrl || "",
        local_path: localPath || "",
      }),
    }),

  sessions: async () => listResult<Session>(await request("/sessions/")),
  localDirs: (path?: string) =>
    request<{
      path: string;
      parent: string | null;
      roots: string[];
      dirs: { name: string; path: string }[];
    }>(`/sessions/local_dirs/${path ? `?path=${encodeURIComponent(path)}` : ""}`),
  createSession: (name: string, localPath: string, model?: string) =>
    request<Session>("/sessions/", {
      method: "POST",
      body: JSON.stringify({
        name,
        local_path: localPath,
        model: model || "",
      }),
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
  ollamaCatalog: () =>
    request<{ catalog: CatalogModel[]; total: number }>("/ollama/catalog/"),

  adminUsers: async () =>
    listResult<AdminUser>(await request("/auth/admin/users/")),
  adminCreateUser: (data: {
    email: string;
    name: string;
    password: string;
    is_staff?: boolean;
    is_active?: boolean;
  }) =>
    request<AdminUser>("/auth/admin/users/", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  adminUpdateUser: (id: string, data: Partial<AdminUser & { password: string }>) =>
    request<AdminUser>(`/auth/admin/users/${id}/`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  adminDeleteUser: (id: string) =>
    request<void>(`/auth/admin/users/${id}/`, { method: "DELETE" }),
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
