import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

const MOBILE = "(max-width: 768px)";

export function AppShell() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("sidebar-collapsed") === "1");
  const [isMobile, setIsMobile] = useState(() => window.matchMedia(MOBILE).matches);

  useEffect(() => {
    const mq = window.matchMedia(MOBILE);
    const onChange = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  // On desktop the collapsed rail is a preference worth remembering; on mobile
  // "collapsed" just means the drawer is shut, which shouldn't persist.
  useEffect(() => {
    if (!isMobile) localStorage.setItem("sidebar-collapsed", collapsed ? "1" : "0");
  }, [collapsed, isMobile]);

  // Entering mobile, or moving to a new page on mobile, closes the drawer.
  useEffect(() => {
    if (isMobile) setCollapsed(true);
  }, [isMobile, location.pathname]);

  const drawerOpen = isMobile && !collapsed;

  useEffect(() => {
    document.body.style.overflow = drawerOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [drawerOpen]);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setCollapsed(true);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  return (
    <div className={"app-shell" + (isMobile ? " is-mobile" : "")}>
      <Sidebar collapsed={collapsed} />
      {drawerOpen && (
        <div className="scrim" onClick={() => setCollapsed(true)} aria-hidden="true" />
      )}
      <main className="app-main">
        <Topbar collapsed={collapsed} onToggleSidebar={() => setCollapsed((c) => !c)} />
        <div className="app-content">
          <div className="page-transition" key={location.pathname}>
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
