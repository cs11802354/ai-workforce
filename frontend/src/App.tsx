import { Routes, Route } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { Home } from "./pages/Home";
import { Agents } from "./pages/Agents";
import { AgentEditor } from "./pages/AgentEditor";
import { Chat } from "./pages/Chat";
import { Analytics } from "./pages/Analytics";

export default function App() {
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
