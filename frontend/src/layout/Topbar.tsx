import { auth } from "../api/client";
import { IconBell, IconMoon, IconPanel, IconPower, IconSearch, IconSun } from "../components/Icon";
import { useTheme } from "../lib/theme";

type Props = {
  collapsed: boolean;
  onToggleSidebar: () => void;
};

export function Topbar({ collapsed, onToggleSidebar }: Props) {
  const [theme, setTheme] = useTheme();

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          className="icon-btn"
          onClick={onToggleSidebar}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <IconPanel size={16} />
        </button>
        <div className="topbar-search">
          <IconSearch size={15} />
          <span>Search…</span>
          <kbd>⌘K</kbd>
        </div>
      </div>
      <div className="topbar-actions">
        <button className="icon-btn" aria-label="Notifications" title="Notifications">
          <IconBell size={16} />
          <span className="notif-dot" />
        </button>
        <button
          className="icon-btn"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label="Toggle theme"
          title="Toggle theme"
        >
          {theme === "dark" ? <IconSun size={16} /> : <IconMoon size={16} />}
        </button>
        {auth.get() && (
          <button
            className="icon-btn"
            onClick={() => {
              auth.clear();
              window.location.reload();
            }}
            aria-label="Sign out"
            title="Sign out"
          >
            <IconPower size={16} />
          </button>
        )}
      </div>
    </header>
  );
}
