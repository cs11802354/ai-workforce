import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../api/client";
import { avatarStyle } from "../lib/colors";
import type { Agent, Run } from "../types";

export function Home() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.listAgents().then(setAgents).catch(() => {});
    api.listRuns().then(setRuns).catch(() => {});
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

  return (
    <div className="page">
      <div className="hero">
        <h1 className="page-title">Good morning</h1>
        <p className="page-subtitle">What would you like to build?</p>

        <form className="hero-search-form" onSubmit={handleSearchSubmit}>
          <div className="hero-search">
            <span className="hero-search-icon">✦</span>
            <input
              placeholder="Describe an agent, or search your agents…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button type="submit" className="hero-search-submit" aria-label="Go">↑</button>
          </div>
        </form>

        <div className="hero-chips">
          <Link to="/agents/new" className="chip">+ Build a new agent</Link>
          <Link to="/runs" className="chip">▶ Run an agent</Link>
          <Link to="/agents" className="chip">⚙ View all agents</Link>
        </div>
      </div>

      <div className="stat-bar">
        <div className="stat-bar-item">
          <div className="stat-value">{agents.length}</div>
          <div className="stat-label">Agents</div>
        </div>
        <div className="stat-bar-item">
          <div className="stat-value">{runs.length}</div>
          <div className="stat-label">Runs total</div>
        </div>
        <div className="stat-bar-item">
          <div className="stat-value">{runsToday}</div>
          <div className="stat-label">Runs today</div>
        </div>
      </div>

      <div className="section">
        <div className="section-header">
          <h2>Recent runs</h2>
          <Link to="/runs">View all</Link>
        </div>
        {runs.length === 0 && <p className="empty-state">No runs yet.</p>}
        <div className="list">
          {runs.slice(0, 5).map((run) => {
            const agent = agentById.get(run.agent_id);
            return (
              <div key={run.id} className="list-row">
                {agent && (
                  <span className="list-row-avatar" style={avatarStyle(agent.id)}>
                    {agent.name.charAt(0).toUpperCase()}
                  </span>
                )}
                <span className="list-row-main">{run.input_message}</span>
                <span className={`badge status-${run.status}`}>
                  <span className="badge-dot" />
                  {run.status}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
