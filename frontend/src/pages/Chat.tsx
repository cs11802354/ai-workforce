import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { buttonClass } from "../components/Button";
import { IconArrowUp, IconPlus, IconX } from "../components/Icon";
import { Markdown } from "../components/Markdown";
import { avatarStyle } from "../lib/colors";
import type { Agent, Conversation, Message } from "../types";

export function Chat() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [railOpen, setRailOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const draftRef = useRef<HTMLTextAreaElement>(null);

  const agentById = new Map(agents.map((a) => [a.id, a]));
  const active = conversations.find((c) => c.id === activeId) || null;
  const activeAgent = active ? agentById.get(active.agent_id) : undefined;

  useEffect(() => {
    Promise.all([api.listAgents().then(setAgents), api.listConversations().then(setConversations)])
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // ?agent=<id> (from the Agents page) starts a fresh conversation.
  useEffect(() => {
    const agentId = searchParams.get("agent");
    if (!agentId) return;
    setSearchParams({}, { replace: true });
    api.createConversation(agentId).then((conversation) => {
      setConversations((prev) => [conversation, ...prev]);
      setActiveId(conversation.id);
      setMessages([]);
    });
  }, [searchParams, setSearchParams]);

  // rows={1} plus a fixed CSS height means long/multi-line drafts would
  // overflow upward into the message list instead of growing the box. Grow it
  // to fit the content, capped by the CSS max-height (which then scrolls).
  useEffect(() => {
    const el = draftRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [draft]);

  useEffect(() => {
    if (!activeId) return;
    api
      .getConversation(activeId)
      .then((detail) => setMessages(detail.messages))
      .catch(() => setMessages([]));
  }, [activeId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function startConversation(agentId: string) {
    const conversation = await api.createConversation(agentId);
    setConversations((prev) => [conversation, ...prev]);
    setActiveId(conversation.id);
    setMessages([]);
    setRailOpen(false);
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || !activeId || sending) return;

    setDraft("");
    setError(null);
    setSending(true);

    // Optimistic user bubble so the thread doesn't sit empty during the turn.
    const pending: Message = {
      id: `pending-${Date.now()}`,
      role: "user",
      content: text,
      tool_name: null,
      seq: messages.length,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, pending]);

    try {
      const turn = await api.sendMessage(activeId, text);
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== pending.id),
        turn.user_message,
        ...turn.tool_messages,
        turn.assistant_message,
      ]);
      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeId
            ? { ...c, title: turn.conversation_title, last_message_at: new Date().toISOString() }
            : c
        )
      );
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== pending.id));
      setDraft(text);
      setError(err instanceof Error ? err.message : "The agent turn failed.");
    } finally {
      setSending(false);
    }
  }

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm("Delete this conversation?")) return;
    await api.deleteConversation(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeId === id) {
      setActiveId(null);
      setMessages([]);
    }
  }

  if (!loading && agents.length === 0) {
    return (
      <div className="page">
        <h1 className="page-title">Chat</h1>
        <p className="page-subtitle">Talk to an agent.</p>
        <p className="empty-state">Create an agent first — there's nobody to talk to yet.</p>
      </div>
    );
  }

  return (
    <div className="chat">
      <aside className={"chat-rail" + (railOpen ? " open" : "")}>
        <div className="chat-rail-head">
          <span className="chat-rail-title">Conversations</span>
        </div>

        <div className="chat-new">
          <select
            className="input"
            value=""
            onChange={(e) => e.target.value && startConversation(e.target.value)}
          >
            <option value="">＋ New chat with…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </div>

        <div className="chat-rail-list">
          {conversations.length === 0 && <p className="chat-rail-empty">No conversations yet.</p>}
          {conversations.map((c) => {
            const agent = agentById.get(c.agent_id);
            return (
              <button
                key={c.id}
                className={"chat-rail-item" + (c.id === activeId ? " active" : "")}
                onClick={() => {
                  setActiveId(c.id);
                  setRailOpen(false);
                }}
              >
                {agent && (
                  <span className="list-row-avatar" style={avatarStyle(agent.id)}>
                    {agent.name.charAt(0).toUpperCase()}
                  </span>
                )}
                <span className="chat-rail-item-text">
                  <span className="chat-rail-item-title">{c.title}</span>
                  <span className="chat-rail-item-sub">{agent?.name || "Unknown agent"}</span>
                </span>
                <span
                  className="chat-rail-delete"
                  role="button"
                  tabIndex={0}
                  aria-label="Delete conversation"
                  onClick={(e) => handleDelete(c.id, e)}
                  onKeyDown={(e) => e.key === "Enter" && handleDelete(c.id, e as never)}
                >
                  <IconX size={13} />
                </span>
              </button>
            );
          })}
        </div>
      </aside>

      <section className="chat-main">
        <div className="chat-head">
          <button className={buttonClass("ghost", { size: "sm", className: "chat-rail-toggle" })} onClick={() => setRailOpen((o) => !o)}>
            <IconPlus size={14} /> Chats
          </button>
          {activeAgent ? (
            <div className="chat-head-agent">
              <span className="agent-avatar" style={avatarStyle(activeAgent.id)}>
                {activeAgent.name.charAt(0).toUpperCase()}
              </span>
              <div>
                <div className="agent-name">{activeAgent.name}</div>
                <div className="agent-desc">{activeAgent.model}</div>
              </div>
            </div>
          ) : (
            <div className="agent-desc">Pick or start a conversation</div>
          )}
        </div>

        <div className="chat-thread">
          {!activeId && (
            <p className="empty-state">
              Start a new chat from the picker, or open one from the list.
            </p>
          )}

          {messages.map((m) =>
            // Tool-call trace (e.g. "used artifact_generator") is hidden for
            // now — the assistant's reply already surfaces what matters (the
            // artifact link), so the raw trace is just noise in the thread.
            m.role === "tool" ? null : (
              <div key={m.id} className={`chat-bubble chat-${m.role}`}>
                {m.role === "assistant" ? <Markdown content={m.content} /> : m.content}
              </div>
            )
          )}

          {sending && (
            <div className="chat-bubble chat-assistant chat-typing">
              <span />
              <span />
              <span />
            </div>
          )}

          {error && <div className="chat-error">{error}</div>}
          <div ref={endRef} />
        </div>

        <form className="chat-composer" onSubmit={handleSend}>
          <textarea
            ref={draftRef}
            className="input"
            rows={1}
            placeholder={activeId ? "Send a message…" : "Start a conversation first"}
            value={draft}
            disabled={!activeId || sending}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend(e);
              }
            }}
          />
          <button
            type="submit"
            className="hero-search-submit"
            disabled={!activeId || sending || !draft.trim()}
            aria-label="Send"
          >
            <IconArrowUp size={16} />
          </button>
        </form>
      </section>
    </div>
  );
}
