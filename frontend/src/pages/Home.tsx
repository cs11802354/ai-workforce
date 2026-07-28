import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../api/client";
import { avatarStyle, tint } from "../lib/colors";
import { formatDuration } from "../lib/format";
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

  const completedRuns = runs.filter((r) => r.status === "completed");
  const failedRuns = runs.filter((r) => r.status === "failed");
  const finishedCount = completedRuns.length + failedRuns.length;
  const successRate = finishedCount > 0 ? Math.round((completedRuns.length / finishedCount) * 100) : null;

  const runCountByAgent = new Map<string, number>();
  runs.forEach((r) => runCountByAgent.set(r.agent_id, (runCountByAgent.get(r.agent_id) || 0) + 1));
  let mostActiveAgentName = "—";
  let mostActiveCount = 0;
  runCountByAgent.forEach((count, agentId) => {
    if (count > mostActiveCount) {
      mostActiveCount = count;
      mostActiveAgentName = agentById.get(agentId)?.name || "—";
    }
  });

  const durations = completedRuns
    .filter((r) => r.completed_at)
    .map((r) => new Date(r.completed_at!).getTime() - new Date(r.created_at).getTime());
  const avgDurationMs = durations.length > 0 ? durations.reduce((a, b) => a + b, 0) / durations.length : null;

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

      {loading ? (
        <div className="stat-grid">
          <div className="stat-card-item"><div className="skeleton skeleton-stat" style={{ width: "100%" }} /></div>
          <div className="stat-card-item"><div className="skeleton skeleton-stat" style={{ width: "100%" }} /></div>
          <div className="stat-card-item"><div className="skeleton skeleton-stat" style={{ width: "100%" }} /></div>
        </div>
      ) : (
        <div className="stat-grid">
          <div className="stat-card-item">
            <div className="stat-icon" style={tint("#6366F1")}>⚙</div>
            <div>
              <div className="stat-value">{agents.length}</div>
              <div className="stat-label">Agents</div>
            </div>
          </div>
          <div className="stat-card-item">
            <div className="stat-icon" style={tint("#0EA5E9")}>▶</div>
            <div>
              <div className="stat-value">{runs.length}</div>
              <div className="stat-label">Runs total</div>
            </div>
          </div>
          <div className="stat-card-item">
            <div className="stat-icon" style={tint("#14B8A6")}>⚡</div>
            <div>
              <div className="stat-value">{runsToday}</div>
              <div className="stat-label">Runs today</div>
            </div>
          </div>
        </div>
      )}

      <div className="section">
        <div className="section-header">
          <h2>Analytics</h2>
        </div>
        {loading ? (
          <div className="stat-grid">
            <div className="stat-card-item"><div className="skeleton skeleton-stat" style={{ width: "100%" }} /></div>
            <div className="stat-card-item"><div className="skeleton skeleton-stat" style={{ width: "100%" }} /></div>
            <div className="stat-card-item"><div className="skeleton skeleton-stat" style={{ width: "100%" }} /></div>
            <div className="stat-card-item"><div className="skeleton skeleton-stat" style={{ width: "100%" }} /></div>
          </div>
        ) : (
          <div className="stat-grid">
            <div className="stat-card-item">
              <div className="stat-icon" style={tint("#17a76b")}>✓</div>
              <div>
                <div className="stat-value">{successRate === null ? "—" : `${successRate}%`}</div>
                <div className="stat-label">Success rate</div>
              </div>
            </div>
            <div className="stat-card-item">
              <div className="stat-icon" style={tint("#e0454f")}>✕</div>
              <div>
                <div className="stat-value">{failedRuns.length}</div>
                <div className="stat-label">Failed runs</div>
              </div>
            </div>
            <div className="stat-card-item">
              <div className="stat-icon" style={tint("#6366F1")}>★</div>
              <div>
                <div className="stat-value stat-value-sm">{mostActiveAgentName}</div>
                <div className="stat-label">Most active agent</div>
              </div>
            </div>
            <div className="stat-card-item">
              <div className="stat-icon" style={tint("#0EA5E9")}>◷</div>
              <div>
                <div className="stat-value">{avgDurationMs === null ? "—" : formatDuration(avgDurationMs)}</div>
                <div className="stat-label">Avg run duration</div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="section">
        <div className="section-header">
          <h2>Recent runs</h2>
          <Link to="/runs">View all</Link>
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
