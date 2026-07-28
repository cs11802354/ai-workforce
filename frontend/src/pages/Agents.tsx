import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Agent } from "../types";

export function Agents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => api.listAgents().then(setAgents).finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  async function handleDelete(id: string) {
    if (!confirm("Delete this agent?")) return;
    await api.deleteAgent(id);
    load();
  }

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Agents</h1>
          <p className="page-subtitle">{agents.length} managed</p>
        </div>
        <Link to="/agents/new" className="btn btn-primary">+ New agent</Link>
      </div>

      {loading && <p className="empty-state">Loading…</p>}
      {!loading && agents.length === 0 && (
        <p className="empty-state">No agents yet — create your first one.</p>
      )}

      <div className="card-grid">
        {agents.map((agent) => (
          <div key={agent.id} className="agent-card">
            <div className="agent-card-header">
              <div className="agent-avatar">{agent.name.charAt(0).toUpperCase()}</div>
              <div>
                <div className="agent-name">{agent.name}</div>
                <div className="agent-desc">{agent.description || "No description"}</div>
              </div>
            </div>
            <div className="badge-row">
              <span className="badge">{agent.provider}</span>
              <span className="badge">{agent.model}</span>
              {agent.tools.map((tool) => (
                <span key={tool} className="badge badge-muted">{tool}</span>
              ))}
            </div>
            <div className="agent-card-actions">
              <Link to={`/agents/${agent.id}/edit`} className="btn btn-ghost btn-sm">Edit</Link>
              <Link to={`/runs?agent=${agent.id}`} className="btn btn-ghost btn-sm">Run</Link>
              <button className="btn btn-ghost btn-sm btn-danger" onClick={() => handleDelete(agent.id)}>
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
