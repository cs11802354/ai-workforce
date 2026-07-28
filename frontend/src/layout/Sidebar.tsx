import { NavLink } from "react-router-dom";

const items = [
  { to: "/", label: "Home", icon: "⌂", end: true },
  { to: "/agents", label: "Agents", icon: "⚙" },
  { to: "/runs", label: "Runs", icon: "▶" },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">M</div>
        <span>ManLab</span>
      </div>
      <nav className="sidebar-nav">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}
          >
            <span className="sidebar-icon">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
