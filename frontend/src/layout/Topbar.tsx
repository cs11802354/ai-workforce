import { useTheme } from "../lib/theme";

export function Topbar() {
  const [theme, setTheme] = useTheme();

  return (
    <header className="topbar">
      <div className="topbar-search">
        <span>⌕</span>
        <span>Search…</span>
        <kbd>⌘K</kbd>
      </div>
      <div className="topbar-actions">
        <button className="icon-btn" aria-label="Notifications" title="Notifications">
          🔔
          <span className="notif-dot" />
        </button>
        <button
          className="icon-btn"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label="Toggle theme"
          title="Toggle theme"
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </div>
    </header>
  );
}
