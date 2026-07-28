/**
 * Trust Panel — the page that renders a multi-model consensus report.
 *
 * Deliberately imports nothing from the host application: it declares its own
 * types and does its own fetch, so the directory can be dropped into another
 * React app by adding one route. The only shared surface is the CSS custom
 * properties (--surface, --border, --text …), which any theme can supply.
 *
 * The layout follows one idea: a reader should not be able to accept the answer
 * without also seeing how contested it is. So the trust badge sits next to the
 * answer rather than below the fold, and the agreement matrix — every claim
 * against every model — is the first thing under it. Burying disagreement in a
 * collapsed section would defeat the point of running a panel.
 */

import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8080";

// Where the host app keeps its bearer token. Overridable via the `tokenKey`
// prop because this default is a duplicate of a constant that lives in the host
// application, and duplicated constants drift — this one already did once, when
// the app was rebranded and the page silently started sending no auth header.
const DEFAULT_TOKEN_KEY = "mklabs-token";

// ---------------------------------------------------------------- types

type Stance = "supports" | "rejects" | "conditional" | "unaddressed";
type Verdict = "unanimous" | "majority" | "conditional" | "conflict" | "single_source";
type CitationStatus = "verified" | "unsupported" | "broken" | "unverified";
type TrustStatus = "high" | "mixed" | "contested" | "degraded";

interface Evidence {
  source_id: string | null;
  quote: string;
  url: string | null;
}

interface ClaimCluster {
  id: string;
  canonical_text: string;
  stances: Record<string, Stance>;
  member_claims: Record<string, string>;
  evidence: Evidence[];
  citation_status: CitationStatus;
  disputed_citations: number;
  confidence: number;
  verdict: Verdict;
}

interface PanelMember {
  model: string;
  provider: string;
  role: string;
}

interface TrustReport {
  query: string;
  route: {
    domain: string;
    complexity: string;
    requires_tools: boolean;
    panel: PanelMember[];
    rationale: string;
  };
  recommended_answer: string;
  trust_status: TrustStatus;
  agreements: ClaimCluster[];
  disagreements: ClaimCluster[];
  unconfirmed: ClaimCluster[];
  evidence: ClaimCluster[];
  uncertainties: string[];
  failures: { model: string; reason: string; stage: string }[];
  cross_examined: number;
  elapsed_ms: number;
}

interface Example {
  label: string;
  query: string;
  use_corpus: boolean;
  note: string;
}

// ---------------------------------------------------------------- labels

const TRUST_COPY: Record<TrustStatus, { label: string; blurb: string }> = {
  high: {
    label: "High",
    blurb: "Every model agreed and every citation checked out against the sources.",
  },
  mixed: {
    label: "Mixed",
    blurb: "The panel broadly agreed, but something is unconfirmed or unsourced.",
  },
  contested: {
    label: "Contested",
    blurb: "Models directly contradicted each other and the evidence did not settle it.",
  },
  degraded: {
    label: "Degraded",
    blurb: "Too few models answered to form a consensus. Treat this as one opinion.",
  },
};

const VERDICT_LABEL: Record<Verdict, string> = {
  unanimous: "all models",
  majority: "most models",
  conditional: "conditional",
  conflict: "contradicted",
  single_source: "one model",
};

const CITATION_LABEL: Record<CitationStatus, string> = {
  verified: "source verified",
  unsupported: "quote not found in source",
  broken: "cited source does not exist",
  unverified: "no source to check",
};

const STANCE_GLYPH: Record<Stance, string> = {
  supports: "✓",
  rejects: "✕",
  conditional: "~",
  unaddressed: "·",
};

// ---------------------------------------------------------------- fetch

async function request<T>(path: string, tokenKey: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem(tokenKey);
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json())?.detail ?? "";
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------- page

export function TrustPanel({ tokenKey = DEFAULT_TOKEN_KEY }: { tokenKey?: string } = {}) {
  const [query, setQuery] = useState("");
  const [examples, setExamples] = useState<Example[]>([]);
  const [corpus, setCorpus] = useState<Record<string, string>>({});
  const [useCorpus, setUseCorpus] = useState(true);
  const [report, setReport] = useState<TrustReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSources, setShowSources] = useState(false);

  useEffect(() => {
    request<{ examples: Example[]; corpus: Record<string, string> }>("/trust/examples", tokenKey)
      .then((d) => {
        setExamples(d.examples);
        setCorpus(d.corpus);
        if (d.examples[0]) setQuery(d.examples[0].query);
      })
      .catch(() => setExamples([]));
  }, [tokenKey]);

  async function run(q = query, withCorpus = useCorpus) {
    if (!q.trim() || busy) return;
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      setReport(
        await request<TrustReport>("/trust/query", tokenKey, {
          method: "POST",
          body: JSON.stringify({ query: q, corpus: withCorpus ? corpus : {} }),
        })
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="tp">
      <header className="tp-head">
        <h1>Multi-model trust</h1>
        <p>
          One question, several models, answered independently. The report below shows
          what they agreed on, where they contradicted each other, and which citations
          survive a check against the sources.
        </p>
      </header>

      <section className="tp-ask panel">
        <textarea
          className="tp-input"
          value={query}
          rows={3}
          placeholder="Ask something the models might disagree about…"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run();
          }}
        />
        <div className="tp-ask-foot">
          <label className="tp-toggle">
            <input
              type="checkbox"
              checked={useCorpus}
              onChange={(e) => setUseCorpus(e.target.checked)}
            />
            <span>
              Ground in {Object.keys(corpus).length} sources
              {useCorpus ? "" : " (off — citations cannot be verified)"}
            </span>
          </label>
          <button className="btn btn-primary" onClick={() => run()} disabled={busy || !query.trim()}>
            {busy ? "Running panel…" : "Run panel"}
          </button>
        </div>

        {examples.length > 0 && (
          <div className="tp-examples">
            {examples.map((ex) => (
              <button
                key={ex.label}
                className="tp-chip"
                title={ex.note}
                disabled={busy}
                onClick={() => {
                  setQuery(ex.query);
                  setUseCorpus(ex.use_corpus);
                  run(ex.query, ex.use_corpus);
                }}
              >
                {ex.label}
              </button>
            ))}
            <button className="tp-chip tp-chip-ghost" onClick={() => setShowSources((s) => !s)}>
              {showSources ? "Hide sources" : "View sources"}
            </button>
          </div>
        )}

        {showSources && (
          <div className="tp-sources">
            {Object.entries(corpus).map(([id, text]) => (
              <div key={id} className="tp-source">
                <code>{id}</code>
                <span>{text}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {busy && <PanelRunning />}
      {error && <div className="tp-error panel">{error}</div>}
      {report && <Report report={report} />}
    </div>
  );
}

function PanelRunning() {
  return (
    <div className="tp-running panel">
      <div className="tp-dots">
        <span />
        <span />
        <span />
      </div>
      <div>
        <strong>Querying the panel</strong>
        <p>
          Models answer in parallel, then a normalizer groups their claims and a
          cross-examiner reviews any contradiction. Usually 20–40 seconds.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- report

function Report({ report }: { report: TrustReport }) {
  const trust = TRUST_COPY[report.trust_status];
  const models = report.route.panel.map((m) => m.model);
  const matrix = [...report.agreements, ...report.disagreements, ...report.unconfirmed];

  return (
    <>
      <section className={`tp-answer panel trust-${report.trust_status}`}>
        <div className="tp-answer-top">
          <span className="tp-label">Recommended answer</span>
          <span className={`tp-badge trust-${report.trust_status}`}>{trust.label} trust</span>
        </div>
        <p className="tp-answer-text">{report.recommended_answer}</p>
        <p className="tp-answer-why">{trust.blurb}</p>

        <div className="tp-meta">
          {report.route.panel.map((m) => (
            <span key={m.model} className="tp-model">
              <em>{m.provider}</em>
              {m.model}
              {m.role !== "generalist" && <b>{m.role}</b>}
            </span>
          ))}
          <span className="tp-meta-sep" />
          <span>{report.route.domain}</span>
          <span>{report.route.complexity} complexity</span>
          <span>{(report.elapsed_ms / 1000).toFixed(1)}s</span>
          {report.cross_examined > 0 && <span>{report.cross_examined} cross-examined</span>}
        </div>
      </section>

      {report.failures.length > 0 && (
        <section className="tp-failures panel">
          <span className="tp-label">Panel failures</span>
          {report.failures.map((f) => (
            <div key={f.model} className="tp-failure">
              <strong>{f.model}</strong>
              <span className="tp-stage">{f.stage}</span>
              <span>{f.reason}</span>
            </div>
          ))}
        </section>
      )}

      {matrix.length > 0 && (
        <section className="tp-matrix panel">
          <span className="tp-label">Agreement matrix</span>
          <div className="tp-matrix-scroll">
            <table>
              <thead>
                <tr>
                  <th>Claim</th>
                  {models.map((m) => (
                    <th key={m} className="tp-model-col">
                      {m}
                    </th>
                  ))}
                  <th>Verdict</th>
                </tr>
              </thead>
              <tbody>
                {matrix.map((c) => (
                  <tr key={c.id} className={`verdict-${c.verdict}`}>
                    <td className="tp-claim-cell">{c.canonical_text}</td>
                    {models.map((m) => {
                      const stance = c.stances[m] ?? "unaddressed";
                      return (
                        <td key={m} className={`tp-cell stance-${stance}`} title={stance}>
                          {STANCE_GLYPH[stance]}
                        </td>
                      );
                    })}
                    <td>
                      <span className={`tp-verdict verdict-${c.verdict}`}>
                        {VERDICT_LABEL[c.verdict]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="tp-legend">
            <span className="stance-supports">✓</span> supports
            <span className="stance-rejects">✕</span> contradicts
            <span className="stance-conditional">~</span> conditional
            <span className="stance-unaddressed">·</span> did not address
          </p>
        </section>
      )}

      <div className="tp-grid">
        <ClusterCard
          title="Where models agree"
          empty="Nothing was corroborated by more than one model."
          clusters={report.agreements}
        />
        <ClusterCard
          title="Where models disagree"
          empty="No model contradicted another."
          clusters={report.disagreements}
        />
      </div>

      {report.unconfirmed.length > 0 && (
        <ClusterCard
          title="Raised by one model only"
          hint="Nobody contradicted these — nobody else addressed them either. Often the most useful part of a panel, and the part a majority vote would throw away."
          empty=""
          clusters={report.unconfirmed}
        />
      )}

      <section className="tp-evidence panel">
        <span className="tp-label">Supporting evidence</span>
        {report.evidence.length === 0 && <p className="tp-empty">No citations were offered.</p>}
        {report.evidence.map((c) => (
          <div key={c.id} className="tp-ev-claim">
            <div className="tp-ev-head">
              <span>{c.canonical_text}</span>
              <span className={`tp-cite cite-${c.citation_status}`}>
                {CITATION_LABEL[c.citation_status]}
              </span>
            </div>
            {c.disputed_citations > 0 && (
              <p className="tp-ev-warn">
                {c.disputed_citations} of {c.evidence.length} citations did not check out.
              </p>
            )}
            {c.evidence.map((e, i) => (
              <blockquote key={i}>
                <code>{e.source_id ?? "no source"}</code>
                {e.quote}
              </blockquote>
            ))}
          </div>
        ))}
      </section>

      {report.uncertainties.length > 0 && (
        <section className="tp-uncertain panel">
          <span className="tp-label">Remaining uncertainty</span>
          <ul>
            {report.uncertainties.map((u, i) => (
              <li key={i}>{u}</li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

function ClusterCard({
  title,
  clusters,
  empty,
  hint,
}: {
  title: string;
  clusters: ClaimCluster[];
  empty: string;
  hint?: string;
}) {
  return (
    <section className="tp-clusters panel">
      <span className="tp-label">{title}</span>
      {hint && <p className="tp-hint">{hint}</p>}
      {clusters.length === 0 && <p className="tp-empty">{empty}</p>}
      {clusters.map((c) => (
        <div key={c.id} className={`tp-cluster verdict-${c.verdict}`}>
          <p className="tp-cluster-text">{c.canonical_text}</p>
          <div className="tp-cluster-meta">
            <span className={`tp-verdict verdict-${c.verdict}`}>{VERDICT_LABEL[c.verdict]}</span>
            <span className={`tp-cite cite-${c.citation_status}`}>
              {CITATION_LABEL[c.citation_status]}
            </span>
            <span className="tp-conf">confidence {(c.confidence * 100).toFixed(0)}%</span>
          </div>
          {Object.entries(c.stances).filter(([, s]) => s === "rejects").length > 0 && (
            <p className="tp-rejects">
              Contradicted by{" "}
              {Object.entries(c.stances)
                .filter(([, s]) => s === "rejects")
                .map(([m]) => m)
                .join(", ")}
            </p>
          )}
        </div>
      ))}
    </section>
  );
}
