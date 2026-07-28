import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { IconCube, IconSparkle } from "../components/Icon";
import { ToolLogo } from "../components/ToolLogo";
import type { Agent, Skill, Tool } from "../types";

const PROVIDER_MODELS: Record<string, string[]> = {
  anthropic: ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"],
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
  const [role, setRole] = useState(
    (location.state as { initialDescription?: string } | null)?.initialDescription || ""
  );
  const [provider, setProvider] = useState<"anthropic" | "openai">("anthropic");
  const [model, setModel] = useState(PROVIDER_MODELS.anthropic[0]);
  const [skills, setSkills] = useState<string[]>([]);
  const [tools, setTools] = useState<string[]>([]);
  const [availableSkills, setAvailableSkills] = useState<Skill[]>([]);
  const [availableTools, setAvailableTools] = useState<Tool[]>([]);
  const [knowledgeFileName, setKnowledgeFileName] = useState<string | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [touched, setTouched] = useState<{ name?: boolean; role?: boolean }>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listSkills().then(setAvailableSkills).catch(() => {});
    api.listTools().then(setAvailableTools).catch(() => {});
    if (id) {
      api.getAgent(id).then((agent: Agent) => {
        setName(agent.name);
        setRole(agent.role);
        setProvider(agent.provider);
        setModel(agent.model);
        setSkills(agent.skills);
        setTools(agent.tools);
        setKnowledgeFileName(agent.knowledge_file_name);
      });
    }
  }, [id]);

  const nameError = !name.trim() ? "Name is required." : null;
  const roleError = !role.trim() ? "Role is required." : null;
  const canSave = !nameError && !roleError && Boolean(model);

  function toggleSkill(skillId: string) {
    setSkills((prev) =>
      prev.includes(skillId) ? prev.filter((s) => s !== skillId) : [...prev, skillId]
    );
  }

  async function handleSave() {
    setTouched({ name: true, role: true });
    if (!canSave || saving) return;
    setSaving(true);
    setError(null);
    try {
      const payload = { name: name.trim(), role: role.trim(), provider, model, skills, tools };
      const agent = isEdit ? await api.updateAgent(id!, payload) : await api.createAgent(payload);
      if (pendingFile) await api.uploadKnowledgeFile(agent.id, pendingFile);
      navigate("/agents");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the agent.");
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
            Name, role and model are required.
          </p>
        </div>
        <button className="btn btn-primary" onClick={handleSave} disabled={saving || !canSave}>
          {saving ? "Saving…" : isEdit ? "Save agent" : "Create agent"}
        </button>
      </div>

      {error && <div className="chat-error" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="form-section">
        <div className="form-section-label">
          Identity <span className="req">required</span>
        </div>
        <div className="form-row" style={{ alignItems: "flex-start" }}>
          <div className="icon-box"><IconSparkle size={19} /></div>
          <div style={{ flex: 1 }}>
            <label className="form-label" htmlFor="agent-name">Name your agent</label>
            <input
              id="agent-name"
              className={"input" + (touched.name && nameError ? " invalid" : "")}
              placeholder="e.g. Equity Research Assistant"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, name: true }))}
              aria-invalid={Boolean(touched.name && nameError)}
            />
            {touched.name && nameError && <p className="field-error">{nameError}</p>}
          </div>
        </div>
      </div>

      <div className="form-section">
        <div className="form-section-label">
          Role <span className="req">required</span>
        </div>
        <textarea
          className={"input textarea" + (touched.role && roleError ? " invalid" : "")}
          placeholder="What is this agent responsible for?"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          onBlur={() => setTouched((t) => ({ ...t, role: true }))}
          aria-invalid={Boolean(touched.role && roleError)}
        />
        {touched.role && roleError && <p className="field-error">{roleError}</p>}
      </div>

      <div className="form-section">
        <div className="form-section-label">
          Model <span className="req">required</span>
        </div>
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
        <select
          className="input"
          style={{ marginTop: 10 }}
          value={model}
          onChange={(e) => setModel(e.target.value)}
        >
          {PROVIDER_MODELS[provider].map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      <div className="form-section">
        <div className="form-section-label">Skills</div>
        <p className="section-hint">
          Context the agent reasons with — it shapes which tool the model reaches for.
        </p>
        <div className="tool-grid">
          {availableSkills.map((skill) => (
            <label
              key={skill.id}
              className={"tool-check" + (skills.includes(skill.id) ? " checked" : "")}
            >
              <input
                type="checkbox"
                checked={skills.includes(skill.id)}
                onChange={() => toggleSkill(skill.id)}
              />
              <div>
                <div className="tool-name">{skill.name}</div>
                <div className="tool-desc">{skill.description}</div>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div className="form-section">
        <div className="form-section-label">
          Tools <span className="soon">Demo — not connected</span>
        </div>
        <p className="section-hint">
          Data sources the agent can call. The dispatch path is live; the adapters
          are stubs, so these stay disabled for now.
        </p>
        <div className="tool-grid">
          {availableTools.map((tool) => (
            <div key={tool.id} className="tool-check tool-card disabled" aria-disabled="true">
              <ToolLogo id={tool.id} />
              <div>
                <div className="tool-name">{tool.name}</div>
                <div className="tool-desc">{tool.description}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="form-section">
        <div className="form-section-label">Knowledge &amp; files</div>
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
