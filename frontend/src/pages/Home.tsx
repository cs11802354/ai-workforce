import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../api/client";
import { avatarStyle } from "../lib/colors";
import { Badge } from "../components/Badge";
import { IconAgents, IconArrowUp, IconBolt, IconChat, IconPlus, IconRuns, IconSparkle } from "../components/Icon";
import { StatCard, StatGrid } from "../components/Card";
import type { Agent, Run } from "../types";

export function Home() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.listAgents().then(setAgents).catch(() => {}),
      api.listRuns().then(setRuns).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const agentById = new Map(agents.map((a) => [a.id, a]));
  const runsToday = runs.filter(
    (r) => new Date(r.created_at).toDateString() === new Date().toDateString()
  ).length;


  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    navigate("/agents/new", { state: { initialDescription: query.trim() } });
  }

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <div className="page">
      <div className="hero">
        <h1 className="page-title">{greeting}</h1>
        <p className="page-subtitle">What would you like to build?</p>

        <form className="hero-search-form" onSubmit={handleSearchSubmit}>
          <div className="hero-search">
            <span className="hero-search-icon"><IconSparkle size={17} /></span>
            <input
              placeholder="Describe an agent, or search your agents…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button type="submit" className="hero-search-submit" aria-label="Go"><IconArrowUp size={16} /></button>
          </div>
        </form>

        <div className="hero-chips">
          <Link to="/agents/new" className="chip"><IconPlus size={14} /> Build a new agent</Link>
          <Link to="/chat" className="chip"><IconChat size={14} /> Chat with an agent</Link>
          <Link to="/agents" className="chip"><IconAgents size={14} /> View all agents</Link>
        </div>
      </div>

      <StatGrid loading={loading}>
        <StatCard icon={IconAgents} hue="#6366F1" value={agents.length} label="Agents" />
        <StatCard icon={IconRuns} hue="#0EA5E9" value={runs.length} label="Runs total" />
        <StatCard icon={IconBolt} hue="#14B8A6" value={runsToday} label="Runs today" />
      </StatGrid>

      <div className="section">
        <div className="section-header">
          <h2>Recent runs</h2>
          <Link to="/chat">Open chat</Link>
        </div>
        {loading && (
          <div>
            <div className="skeleton skeleton-row" />
            <div className="skeleton skeleton-row" />
            <div className="skeleton skeleton-row" />
          </div>
        )}
        {!loading && runs.length === 0 && <p className="empty-state">No runs yet.</p>}
        <div className="list">
          {!loading && runs.slice(0, 5).map((run) => {
            const agent = agentById.get(run.agent_id);
            return (
              <div key={run.id} className="list-row">
                {agent && (
                  <span className="list-row-avatar" style={avatarStyle(agent.id)}>
                    {agent.name.charAt(0).toUpperCase()}
                  </span>
                )}
                <span className="list-row-main">{run.input_message}</span>
                <Badge status={run.status} dot>
                  {run.status}
                </Badge>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
