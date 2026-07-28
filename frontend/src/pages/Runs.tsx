import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Agent, Run } from "../types";

export function Runs() {
  const [searchParams] = useSearchParams();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentId, setAgentId] = useState(searchParams.get("agent") || "");
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<Run[]>([]);
  const [activeRun, setActiveRun] = useState<Run | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    api.listAgents().then((list) => {
      setAgents(list);
      if (!agentId && list.length > 0) setAgentId(list[0].id);
    });
  }, []);

  useEffect(() => {
    if (agentId) api.listRunsForAgent(agentId).then(setHistory).catch(() => {});
  }, [agentId]);

  useEffect(() => {
    if (!activeRun || activeRun.status !== "running") return;
    const timer = setInterval(async () => {
      const updated = await api.getRun(activeRun.id);
      setActiveRun(updated);
      if (updated.status !== "running") {
        clearInterval(timer);
        if (agentId) api.listRunsForAgent(agentId).then(setHistory);
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [activeRun]);

  async function handleRun() {
    if (!agentId || !message.trim()) return;
    setSending(true);
    try {
      const run = await api.startRun(agentId, message);
      setActiveRun(run);
      setMessage("");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="page page-narrow">
      <h1 className="page-title">Runs</h1>
      <p className="page-subtitle">Pick an agent, send it a message, watch it run through Temporal.</p>

      <div className="form-section">
        <label className="form-label">Agent</label>
        <select className="input" value={agentId} onChange={(e) => setAgentId(e.target.value)}>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
      </div>

      <div className="form-section">
        <label className="form-label">Message</label>
        <textarea
          className="input textarea"
          placeholder="Say something to the agent…"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
        <button
          className="btn btn-primary"
          onClick={handleRun}
          disabled={sending || !agentId || !message.trim()}
        >
          {sending ? "Starting…" : "Run"}
        </button>
      </div>

      {activeRun && (
        <div className="form-section run-result">
          <div className="form-section-label">RESULT</div>
          <div className="badge-row">
            <span className={`badge status-${activeRun.status}`}>{activeRun.status}</span>
          </div>
          <p className="run-output">
            {activeRun.status === "running" ? "Waiting on the workflow…" : activeRun.output_text}
          </p>
        </div>
      )}

      <div className="section">
        <div className="section-header">
          <h2>History</h2>
        </div>
        {history.length === 0 && <p className="empty-state">No runs yet for this agent.</p>}
        <div className="list">
          {history.map((run) => (
            <div key={run.id} className="list-row">
              <span className={`status-dot status-${run.status}`} />
              <span className="list-row-main">{run.input_message}</span>
              <span className="list-row-meta">{run.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
