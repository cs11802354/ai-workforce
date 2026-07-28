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

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
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
    const res = await fetch(`${API_URL}/agents/${id}/knowledge-file`, {
      method: "POST",
      body: form,
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
