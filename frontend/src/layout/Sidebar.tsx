import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { IconAgents, IconChevronLeft, IconChevronRight, IconHome, IconRuns } from "../components/Icon";

const items = [
  { to: "/", label: "Home", Icon: IconHome, end: true },
  { to: "/agents", label: "Agents", Icon: IconAgents },
  { to: "/runs", label: "Runs", Icon: IconRuns },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("sidebar-collapsed") === "1");

  useEffect(() => {
    localStorage.setItem("sidebar-collapsed", collapsed ? "1" : "0");
  }, [collapsed]);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 900px)");
    if (mq.matches) setCollapsed(true);
  }, []);

  return (
    <aside className={"sidebar" + (collapsed ? " collapsed" : "")}>
      <div className="sidebar-head">
        <div className="sidebar-brand">
          <div className="brand-mark">M</div>
          {!collapsed && (
            <div className="brand-text">
              <span className="brand-name">ManLab</span>
              <span className="brand-sub">Agent platform</span>
            </div>
          )}
        </div>
      </div>

      {!collapsed && <div className="sidebar-section-label">Workspace</div>}

      <nav className="sidebar-nav">
        {items.map(({ to, label, Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}
            title={collapsed ? label : undefined}
          >
            <Icon className="sidebar-icon" />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-foot">
        <div className="sidebar-user">
          <div className="user-avatar">M</div>
          {!collapsed && (
            <div className="user-meta">
              <div className="user-name">Local workspace</div>
              <div className="user-sub">manishlab.dev</div>
            </div>
          )}
        </div>
        <button
          className="sidebar-toggle"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <IconChevronRight size={15} /> : <IconChevronLeft size={15} />}
        </button>
      </div>
    </aside>
  );
}
