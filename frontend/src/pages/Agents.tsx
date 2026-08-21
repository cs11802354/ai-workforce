import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { avatarStyle } from "../lib/colors";
import { Badge } from "../components/Badge";
import { buttonClass } from "../components/Button";
import { Card, StatCard, StatGrid } from "../components/Card";
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
        <Link to="/agents/new" className={buttonClass("primary")}><IconPlus size={15} /> New agent</Link>
      </div>

      <StatGrid loading={loading}>
        <StatCard icon={IconAgents} hue="#6366F1" value={agents.length} label="Total agents" />
        <StatCard icon={IconCube} hue="#3B82F6" value={providerCount} label="Providers in use" />
        <StatCard icon={IconLayers} hue="#14B8A6" value={toolCount} label="Distinct tools" />
      </StatGrid>

      {!loading && agents.length === 0 && (
        <p className="empty-state">No agents yet — create your first one.</p>
      )}

      <div className="card-grid">
        {loading && [0, 1, 2].map((i) => <div key={i} className="skeleton skeleton-card" />)}
        {!loading && agents.map((agent, i) => (
          <Card key={agent.id} className="fade-up" style={{ animationDelay: `${i * 40}ms` }}>
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
              <Badge dot>{agent.provider}</Badge>
              <Badge muted>{agent.model}</Badge>
              {agent.skills.map((tool) => (
                <Badge key={tool} muted>{tool}</Badge>
              ))}
            </div>
            <div className="agent-card-actions">
              <Link to={`/agents/${agent.id}/edit`} className={buttonClass("ghost", { size: "sm" })}>Edit</Link>
              <Link to={`/chat?agent=${agent.id}`} className={buttonClass("ghost", { size: "sm" })}>Chat</Link>
              <button className={buttonClass("ghost", { size: "sm", danger: true })} onClick={() => handleDelete(agent.id)}>
                Delete
              </button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
