import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { IconCube, IconSparkle } from "../components/Icon";
import type { Agent, Tool } from "../types";

const PROVIDER_MODELS: Record<string, string[]> = {
  anthropic: ["claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5"],
  openai: ["gpt-5", "gpt-5-mini"],
};

const PROVIDERS: { id: "anthropic" | "openai"; Icon: typeof IconSparkle; title: string; desc: string }[] = [
  { id: "anthropic", Icon: IconSparkle, title: "Claude", desc: "Anthropic's models — strong reasoning and long context." },
  { id: "openai", Icon: IconCube, title: "OpenAI", desc: "GPT models — fast, broad general-purpose coverage." },
];

export function AgentEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const isEdit = Boolean(id);

  const [name, setName] = useState("");
  const [description, setDescription] = useState(
    (location.state as { initialDescription?: string } | null)?.initialDescription || ""
  );
  const [provider, setProvider] = useState<"anthropic" | "openai">("anthropic");
  const [model, setModel] = useState(PROVIDER_MODELS.anthropic[0]);
  const [tools, setTools] = useState<string[]>([]);
  const [availableTools, setAvailableTools] = useState<Tool[]>([]);
  const [knowledgeFileName, setKnowledgeFileName] = useState<string | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.listTools().then(setAvailableTools).catch(() => {});
    if (id) {
      api.getAgent(id).then((agent: Agent) => {
        setName(agent.name);
        setDescription(agent.description);
        setProvider(agent.provider);
        setModel(agent.model);
        setTools(agent.tools);
        setKnowledgeFileName(agent.knowledge_file_name);
      });
    }
  }, [id]);

  function toggleTool(toolId: string) {
    setTools((prev) =>
      prev.includes(toolId) ? prev.filter((t) => t !== toolId) : [...prev, toolId]
    );
  }

  async function handleSave() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const payload = { name, description, provider, model, tools };
      const agent = isEdit ? await api.updateAgent(id!, payload) : await api.createAgent(payload);
      if (pendingFile) {
        await api.uploadKnowledgeFile(agent.id, pendingFile);
      }
      navigate("/agents");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page page-narrow">
      <div className="editor-head">
        <div>
          <h1 className="page-title">{isEdit ? "Edit agent" : "New agent"}</h1>
          <p className="page-subtitle" style={{ marginBottom: 0 }}>
            Type into any field to build your agent.
          </p>
        </div>
        <button className="btn btn-primary" onClick={handleSave} disabled={saving || !name.trim()}>
          {saving ? "Saving…" : isEdit ? "Save agent" : "Create agent"}
        </button>
      </div>

      <div className="form-section">
        <div className="form-section-label">IDENTITY</div>
        <div className="form-row" style={{ alignItems: "flex-start" }}>
          <div className="icon-box"><IconSparkle size={19} /></div>
          <div style={{ flex: 1 }}>
            <label className="form-label">Name your agent</label>
            <input
              className="input"
              placeholder="e.g. Support Triage Assistant"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="form-section">
        <div className="form-section-label">ROLE &amp; OBJECTIVES</div>
        <textarea
          className="input textarea"
          placeholder="Describe what this agent is responsible for…"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="form-section">
        <div className="form-section-label">MODEL</div>
        <div className="option-grid">
          {PROVIDERS.map((p) => (
            <button
              key={p.id}
              type="button"
              className={"option-card" + (provider === p.id ? " selected" : "")}
              onClick={() => {
                setProvider(p.id);
                setModel(PROVIDER_MODELS[p.id][0]);
              }}
            >
              <span className="option-card-icon"><p.Icon size={18} /></span>
              <span>
                <div className="option-card-title">{p.title}</div>
                <div className="option-card-desc">{p.desc}</div>
              </span>
            </button>
          ))}
        </div>
        <select className="input" style={{ marginTop: 10 }} value={model} onChange={(e) => setModel(e.target.value)}>
          {PROVIDER_MODELS[provider].map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      <div className="form-section">
        <div className="form-section-label">SKILLS</div>
        <div className="tool-grid">
          {availableTools.map((tool) => (
            <label key={tool.id} className={"tool-check" + (tools.includes(tool.id) ? " checked" : "")}>
              <input
                type="checkbox"
                checked={tools.includes(tool.id)}
                onChange={() => toggleTool(tool.id)}
              />
              <div>
                <div className="tool-name">{tool.name}</div>
                <div className="tool-desc">{tool.description}</div>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div className="form-section">
        <div className="form-section-label">KNOWLEDGE &amp; FILES</div>
        <div className="file-drop">
          <input
            type="file"
            id="knowledge-file"
            onChange={(e) => setPendingFile(e.target.files?.[0] ?? null)}
          />
          <label htmlFor="knowledge-file">
            {pendingFile?.name || knowledgeFileName || "Choose a file to attach"}
          </label>
        </div>
      </div>
    </div>
  );
}
