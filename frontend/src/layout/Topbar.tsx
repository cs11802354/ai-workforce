import { IconBell, IconMoon, IconSearch, IconSun } from "../components/Icon";
import { useTheme } from "../lib/theme";

export function Topbar() {
  const [theme, setTheme] = useTheme();

  return (
    <header className="topbar">
      <div className="topbar-search">
        <IconSearch size={15} />
        <span>Search…</span>
        <kbd>⌘K</kbd>
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
      </div>
    </header>
  );
}
