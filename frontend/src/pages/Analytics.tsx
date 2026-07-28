import { useEffect, useState } from "react";
import { api } from "../api/client";
import { AreaChart, type Point } from "../components/AreaChart";
import { IconAgents, IconBolt, IconClock, IconRuns } from "../components/Icon";
import { tint } from "../lib/colors";
import type { Agent, Run } from "../types";

const DAY_MS = 24 * 60 * 60 * 1000;

function dayKey(d: Date) {
  return d.toISOString().slice(0, 10);
}

function shortLabel(iso: string) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Milliseconds a run occupied an agent. Running runs count up to now. */
function runDurationMs(run: Run): number {
  const start = new Date(run.created_at).getTime();
  const end = run.completed_at ? new Date(run.completed_at).getTime() : Date.now();
  return Math.max(end - start, 0);
}

export function Analytics() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [days, setDays] = useState(14);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.listAgents().then(setAgents).catch(() => {}),
      api.listRuns().then(setRuns).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const runningRuns = runs.filter((r) => r.status === "running");
  const agentsWithRuns = new Set(runs.map((r) => r.agent_id));
  const agentsInWorkflows = new Set(runningRuns.map((r) => r.agent_id));

  const totalHours = runs.reduce((sum, r) => sum + runDurationMs(r), 0) / 3_600_000;

  // Bucket agent-hours by the day the run started.
  const today = new Date();
  const buckets = new Map<string, number>();
  for (let i = days - 1; i >= 0; i--) {
    buckets.set(dayKey(new Date(today.getTime() - i * DAY_MS)), 0);
  }
  runs.forEach((r) => {
    const key = dayKey(new Date(r.created_at));
    if (buckets.has(key)) {
      buckets.set(key, buckets.get(key)! + runDurationMs(r) / 3_600_000);
    }
  });

  const series: Point[] = Array.from(buckets, ([iso, value]) => ({
    label: shortLabel(iso),
    value: Math.round(value * 100) / 100,
  }));

  const cards = [
    {
      label: "Active agents",
      sub: "with at least one run",
      value: agentsWithRuns.size,
      hue: "#6366F1",
      Icon: IconAgents,
    },
    {
      label: "Agent hours",
      sub: "total compute time",
      value: totalHours < 0.01 && totalHours > 0 ? "<0.01" : totalHours.toFixed(2),
      hue: "#0EA5E9",
      Icon: IconClock,
    },
    {
      label: "Active workflows",
      sub: "running right now",
      value: runningRuns.length,
      hue: "#14B8A6",
      Icon: IconBolt,
    },
    {
      label: "Agents in workflows",
      sub: "currently occupied",
      value: agentsInWorkflows.size,
      hue: "#8B5CF6",
      Icon: IconRuns,
    },
  ];

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Analytics</h1>
          <p className="page-subtitle" style={{ marginBottom: 0 }}>
            Utilisation across {agents.length} agent{agents.length === 1 ? "" : "s"} and {runs.length} run
            {runs.length === 1 ? "" : "s"}.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="stat-grid">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="stat-card-item">
              <div className="skeleton skeleton-stat" style={{ width: "100%" }} />
            </div>
          ))}
        </div>
      ) : (
        <div className="stat-grid">
          {cards.map(({ label, sub, value, hue, Icon }) => (
            <div key={label} className="stat-card-item">
              <div className="stat-icon" style={tint(hue)}>
                <Icon size={18} />
              </div>
              <div>
                <div className="stat-value">{value}</div>
                <div className="stat-label">{label}</div>
                <div className="stat-sub">{sub}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="section">
        <div className="section-header">
          <h2>Agent hours by day</h2>
          <div className="range-group" role="group" aria-label="Time range">
            {[7, 14, 30].map((d) => (
              <button
                key={d}
                className={"range-btn" + (days === d ? " active" : "")}
                onClick={() => setDays(d)}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
        <div className="panel">
          {loading ? (
            <div className="skeleton" style={{ height: 260, borderRadius: 10 }} />
          ) : (
            <AreaChart data={series} series="Agent hours" format={(v) => `${v}h`} />
          )}
        </div>
      </div>
    </div>
  );
}
