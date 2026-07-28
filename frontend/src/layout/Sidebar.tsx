import { NavLink } from "react-router-dom";
import { IconAgents, IconChart, IconHome, IconRuns } from "../components/Icon";

const items = [
  { to: "/", label: "Home", Icon: IconHome, end: true },
  { to: "/agents", label: "Agents", Icon: IconAgents },
  { to: "/runs", label: "Runs", Icon: IconRuns },
  { to: "/analytics", label: "Analytics", Icon: IconChart },
];

export function Sidebar({ collapsed }: { collapsed: boolean }) {
  return (
    <aside className={"sidebar" + (collapsed ? " collapsed" : "")}>
      <div className="sidebar-head">
        <div className="sidebar-row sidebar-brand">
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
            className={({ isActive }) => "sidebar-row sidebar-link" + (isActive ? " active" : "")}
            title={collapsed ? label : undefined}
          >
            <Icon className="sidebar-icon" />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-foot">
        <div className="sidebar-row sidebar-user">
          <div className="user-avatar">M</div>
          {!collapsed && (
            <div className="user-meta">
              <div className="user-name">Local workspace</div>
              <div className="user-sub">manishlab.dev</div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
