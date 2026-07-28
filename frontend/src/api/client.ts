import type {
  Agent,
  Conversation,
  ConversationDetail,
  Run,
  Skill,
  Tool,
  Turn,
} from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8080";

const TOKEN_KEY = "mklabs-token";

export const auth = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

/** Set by the app shell so an expired token can bounce us back to the login
 * screen from anywhere, without every call site handling it. */
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = auth.get();
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers || {}),
    },
  });
  if (res.status === 401) {
    auth.clear();
    onUnauthorized?.();
    throw new Error("Your session expired. Sign in again.");
  }
  if (!res.ok) {
    // Surface the API's own message where it has one — a failed agent turn
    // carries the provider error, which is what the user needs to see.
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string" ? body.detail : "";
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail || `${options?.method || "GET"} ${path} failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  authStatus: () => request<{ required: boolean }>("/auth/status"),
  login: (password: string) =>
    request<{ token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  listAgents: () => request<Agent[]>("/agents"),
  getAgent: (id: string) => request<Agent>(`/agents/${id}`),
  createAgent: (payload: Partial<Agent>) =>
    request<Agent>("/agents", { method: "POST", body: JSON.stringify(payload) }),
  updateAgent: (id: string, payload: Partial<Agent>) =>
    request<Agent>(`/agents/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteAgent: (id: string) => request<void>(`/agents/${id}`, { method: "DELETE" }),
  uploadKnowledgeFile: async (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const token = auth.get();
    const res = await fetch(`${API_URL}/agents/${id}/knowledge-file`, {
      method: "POST",
      body: form,
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!res.ok) throw new Error("Knowledge file upload failed");
    return res.json() as Promise<Agent>;
  },

  listSkills: () => request<Skill[]>("/skills"),
  listTools: () => request<Tool[]>("/tools"),

  listConversations: () => request<Conversation[]>("/conversations"),
  getConversation: (id: string) => request<ConversationDetail>(`/conversations/${id}`),
  createConversation: (agentId: string) =>
    request<Conversation>("/conversations", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId }),
    }),
  deleteConversation: (id: string) =>
    request<void>(`/conversations/${id}`, { method: "DELETE" }),
  sendMessage: (conversationId: string, content: string) =>
    request<Turn>(`/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),

  listRuns: () => request<Run[]>("/runs"),
  listRunsForAgent: (agentId: string) => request<Run[]>(`/agents/${agentId}/runs`),
  getRun: (id: string) => request<Run>(`/runs/${id}`),
};
