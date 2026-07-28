import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell() {
  const location = useLocation();

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <Topbar />
        <div className="app-content">
          <div className="page-transition" key={location.pathname}>
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
