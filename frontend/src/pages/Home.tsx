import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Agent, Run } from "../types";

export function Home() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);

  useEffect(() => {
    api.listAgents().then(setAgents).catch(() => {});
    api.listRuns().then(setRuns).catch(() => {});
  }, []);

  const runsToday = runs.filter(
    (r) => new Date(r.created_at).toDateString() === new Date().toDateString()
  ).length;

  return (
    <div className="page">
      <h1 className="page-title">Good morning</h1>
      <p className="page-subtitle">What would you like to do?</p>

      <div className="hero-actions">
        <Link to="/agents/new" className="btn btn-primary">+ New agent</Link>
        <Link to="/runs" className="btn btn-ghost">Run an agent</Link>
      </div>

      <div className="stat-row">
        <div className="stat-card">
          <div className="stat-value">{agents.length}</div>
          <div className="stat-label">Agents</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{runs.length}</div>
          <div className="stat-label">Runs total</div>
        </div>
        <div className="stat-card">
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
          {runs.slice(0, 5).map((run) => (
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
