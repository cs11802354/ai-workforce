import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { avatarStyle, tint } from "../lib/colors";
import { IconAgents, IconCube, IconLayers, IconPlus } from "../components/Icon";
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

  const providerCount = new Set(agents.map((a) => a.provider)).size;
  const toolCount = new Set(agents.flatMap((a) => a.skills)).size;

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Agents</h1>
          <p className="page-subtitle">{agents.length} managed</p>
        </div>
        <Link to="/agents/new" className="btn btn-primary"><IconPlus size={15} /> New agent</Link>
      </div>

      {loading ? (
        <div className="stat-grid">
          <div className="stat-card-item"><div className="skeleton skeleton-stat" style={{ width: "100%" }} /></div>
          <div className="stat-card-item"><div className="skeleton skeleton-stat" style={{ width: "100%" }} /></div>
          <div className="stat-card-item"><div className="skeleton skeleton-stat" style={{ width: "100%" }} /></div>
        </div>
      ) : (
        <div className="stat-grid">
          <div className="stat-card-item">
            <div className="stat-icon" style={tint("#6366F1")}><IconAgents size={18} /></div>
            <div>
              <div className="stat-value">{agents.length}</div>
              <div className="stat-label">Total agents</div>
            </div>
          </div>
          <div className="stat-card-item">
            <div className="stat-icon" style={tint("#3B82F6")}><IconCube size={18} /></div>
            <div>
              <div className="stat-value">{providerCount}</div>
              <div className="stat-label">Providers in use</div>
            </div>
          </div>
          <div className="stat-card-item">
            <div className="stat-icon" style={tint("#14B8A6")}><IconLayers size={18} /></div>
            <div>
              <div className="stat-value">{toolCount}</div>
              <div className="stat-label">Distinct tools</div>
            </div>
          </div>
        </div>
      )}

      {!loading && agents.length === 0 && (
        <p className="empty-state">No agents yet — create your first one.</p>
      )}

      <div className="card-grid">
        {loading && [0, 1, 2].map((i) => <div key={i} className="skeleton skeleton-card" />)}
        {!loading && agents.map((agent, i) => (
          <div key={agent.id} className="agent-card fade-up" style={{ animationDelay: `${i * 40}ms` }}>
            <div className="agent-card-header">
              <div className="agent-avatar" style={avatarStyle(agent.id)}>
                {agent.name.charAt(0).toUpperCase()}
              </div>
              <div>
                <div className="agent-name">{agent.name}</div>
                <div className="agent-desc">{agent.role}</div>
              </div>
            </div>
            <div className="badge-row">
              <span className="badge">
                <span className="badge-dot" />
                {agent.provider}
              </span>
              <span className="badge badge-muted">{agent.model}</span>
              {agent.skills.map((tool) => (
                <span key={tool} className="badge badge-muted">{tool}</span>
              ))}
            </div>
            <div className="agent-card-actions">
              <Link to={`/agents/${agent.id}/edit`} className="btn btn-ghost btn-sm">Edit</Link>
              <Link to={`/chat?agent=${agent.id}`} className="btn btn-ghost btn-sm">Chat</Link>
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
