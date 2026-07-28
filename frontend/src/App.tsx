import { useCallback, useEffect, useState } from "react";
import { Routes, Route } from "react-router-dom";
import { api, auth, setUnauthorizedHandler } from "./api/client";
import { AppShell } from "./layout/AppShell";
import { Home } from "./pages/Home";
import { Agents } from "./pages/Agents";
import { AgentEditor } from "./pages/AgentEditor";
import { Chat } from "./pages/Chat";
import { Analytics } from "./pages/Analytics";
import { Login } from "./pages/Login";

type Gate = "checking" | "locked" | "open";

export default function App() {
  const [gate, setGate] = useState<Gate>("checking");

  const lock = useCallback(() => setGate("locked"), []);

  useEffect(() => {
    setUnauthorizedHandler(lock);
  }, [lock]);

  useEffect(() => {
    // If the server has no password configured the gate is off entirely, so a
    // local checkout still runs without one.
    api
      .authStatus()
      .then(({ required }) => setGate(!required || auth.get() ? "open" : "locked"))
      .catch(() => setGate(auth.get() ? "open" : "locked"));
  }, []);

  if (gate === "checking") return null;
  if (gate === "locked") return <Login onSuccess={() => setGate("open")} />;

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Home />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="/agents/new" element={<AgentEditor />} />
        <Route path="/agents/:id/edit" element={<AgentEditor />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/analytics" element={<Analytics />} />
      </Route>
    </Routes>
  );
}
