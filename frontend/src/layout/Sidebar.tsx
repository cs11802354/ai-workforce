import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

const items = [
  { to: "/", label: "Home", icon: "⌂", end: true },
  { to: "/agents", label: "Agents", icon: "⚙" },
  { to: "/runs", label: "Runs", icon: "▶" },
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
      <div className="sidebar-top">
        <div className="sidebar-brand">
          <div className="brand-mark">M</div>
          {!collapsed && <span>ManLab</span>}
        </div>
        <button
          className="sidebar-toggle"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>

      <nav className="sidebar-nav">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}
            title={collapsed ? item.label : undefined}
          >
            <span className="sidebar-icon">{item.icon}</span>
            {!collapsed && item.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="user-avatar">M</div>
        {!collapsed && (
          <div>
            <div className="user-name">ManLab</div>
            <div className="user-sub">Local workspace</div>
          </div>
        )}
      </div>
    </aside>
  );
}
