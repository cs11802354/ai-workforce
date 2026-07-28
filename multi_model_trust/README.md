# Multi-model trust

Route one prompt to several models, show where they agree and disagree, attach a
source to every claim, verify those sources, and validate the whole thing before
it reaches a screen.

**Live:** https://app.manishlab.dev/trust (password-gated — ask Manish)
**Eval:** `python -m multi_model_trust.eval.eval_harness` — offline, no API calls, ~1s

---

## The problem this solves

Ask three models the same question and you get three answers that are *mostly*
the same. The differences are where the information is: one model contradicts
another on a number, one cites a source that does not exist, one raises a point
the others never considered.

The obvious move — pick the majority answer — destroys exactly that information.
A minority claim is not noise; it is often the only model that noticed
something. So nothing here votes. Claims are grouped, each model's position on
each claim is recorded, and the report shows the whole matrix.

---

## What comes back

Six things, because a reader has six questions:

| Section | Answers |
|---|---|
| Recommended answer | What should I do? |
| Trust status | How much should I lean on this? |
| Where models agree | What is corroborated? |
| Where models disagree | What is contested, and by whom? |
| Raised by one model only | What did nobody else check? |
| Supporting evidence | Which citations actually hold up? |
| Remaining uncertainty | What should I ask next? |

**Trust status** is derived, not asserted:

- `high` — every model agreed and every citation checked out
- `mixed` — broad agreement, but something is unconfirmed or unsourced
- `contested` — models directly contradicted each other and evidence did not settle it
- `degraded` — fewer than two models answered; this is one opinion, not a consensus

---

## Pipeline

```
query
  │
  ▼
router.py          domain / complexity / requires_tools  →  panel selection
  │                (deterministic: keywords + counts, no model call)
  ▼
panel.py           models answer INDEPENDENTLY, in parallel, in a fixed schema
  │                a model that fails becomes a ModelFailure, not an exception
  ▼
synthesize.py      normalizer groups claims across models + assigns stances
  │
  ▼
consensus.py       verdicts · citation verification · trust status   [PURE]
  │
  ├─ material conflict? ──► synthesize.py  cross-examine (cap 3)
  │                          re-check the evidence, correct stances or say
  │                          "unresolved" — never a coin-flip tie-break
  ▼
synthesize.py      final answer, forbidden from hiding disagreement
  ▼
TrustReport        pydantic-validated, then rendered
```

Panel members never see each other's output. The point of a panel is
independence; showing model B what model A said converts disagreement into
anchoring.

**Skills vs tools**, in the platform's terms: the panel *role* is context
injected into the system prompt (how a model reasons); the corpus is data it may
cite. Roles are why a finance query gets one generalist and one analyst brief —
the same model arguing from two starting positions produces more useful
disagreement than two copies of the same prompt.

---

## Orchestration

Each stage is a Temporal activity; every consensus decision is a pure function
running inside the workflow. That split is forced by Temporal (workflow code
must be deterministic on replay) and it happens to be the right architecture
anyway:

- **Parallel fan-out** — panel members are separate activities. Wall clock is
  the slowest model, not the sum. A 2-model panel returns in ~20–26s.
- **Partial failure stays partial** — one model timing out retries on its own
  schedule and, if it stays down, lands in the report as a `ModelFailure`.
  The answer degrades; it does not disappear.
- **Audit trail** — "here is where they disagreed" is a claim about a process.
  The Temporal event history is the evidence for it, replayable after the fact.

Retries are capped at 2. Model calls fail transiently (retry helps) or because a
key is bad (retry just spends money slowly).

---

## The eval

```bash
python -m multi_model_trust.eval.eval_harness            # replay — offline, deterministic
python -m multi_model_trust.eval.eval_harness --mutate ignore-rejects
python -m multi_model_trust.eval.eval_harness --record  # re-record the tape (live, costs money)
```

**Record and replay.** The normalizer is a model call, so a naive harness would
be non-deterministic, slow, and billed on every CI run. Its output for each
fixture case was recorded once against Haiku 4.5 into
`fixtures/normalizer_tape.json` and is replayed thereafter. The default run
makes no network calls and two runs on the same commit produce identical
numbers. `--record` re-measures the normalizer itself; drift shows up as a
changed tape plus changed scores.

**14 cases, 21 gold clusters**, each targeting one failure mode: paraphrased
agreement, flat contradiction, a wrong number stated confidently, conditional
agreement, a minority claim nobody else raised, a citation to a source that does
not exist, a fabricated quote from a real source, a half-dead panel, a
contradiction nobody is confident about, distinct claims sharing vocabulary, and
partial coverage where every claim is backed by two of three models.

### Metrics

| Metric | What it catches | Gate | Current |
|---|---|---:|---:|
| Clustering F1 | pairwise — claims grouped correctly | 0.85 | **1.000** |
| **Conflict F1** | pairwise over (rejecting claim, opposed claim) | 0.80 | **1.000** |
| Verdict accuracy | unanimous / majority / conditional / conflict / single-source | 0.90 | **1.000** |
| Claim retention | fraction of input claims surviving to the report | 1.00 | **1.000** |
| Citation accuracy | verified / unsupported / broken / unverified | 1.00 | **1.000** |
| Trust-status accuracy | the headline badge | 0.85 | **1.000** |

Conflict F1 is the headline number and is scored pairwise rather than per
cluster, so a conflict found inside a slightly-wrong grouping still counts and
an invented conflict is still punished.

### Watching it fail

A test suite that only ever passes tells you nothing about whether it would
catch a regression. Three plausible one-line regressions ship with the harness:

| `--mutate` | The regression | Result |
|---|---|---|
| `ignore-rejects` | `_verdict` stops checking `rejecting_models` | conflict F1 **1.000 → 0.000**, verdict 0.857 |
| `drop-orphans` | `build_clusters` skips its recovery loop | retention **1.000 → 0.821**, verdict 0.667 |
| `cluster-unanimity` | unanimity measured against claim count, not panel size | verdict **1.000 → 0.809** |

All three exit non-zero. Getting there took two rounds: the first version of
this harness *passed* two of the three, because pairwise clustering F1 is
structurally blind to a dropped single-claim cluster (a cluster of one
contributes no pairs) and no fixture case produced a `majority` verdict for the
third mutation to corrupt. Claim retention and verdict accuracy exist because of
those two misses.

---

## Two findings worth writing down

### Embeddings cannot group claims

The first version clustered claims by cosine similarity over sentence
embeddings. Measured against the fixtures, there is **no threshold that works**:

| Variant | Weakest true pair | Strongest false pair | Margin |
|---|---:|---:|---:|
| cosine, 256 dims | 0.686 | 0.777 | **−0.091** |
| cosine, 1536 dims | 0.640 | 0.765 | **−0.125** |
| numeral-masked cosine, 256 dims | 0.701 | 0.806 | **−0.105** |

The failure is structural. Embeddings measure topical relatedness, so *"Q4
revenue was $48.2M"* and *"Q4 operating margin was 8.4%"* score high while a
genuine paraphrase in different vocabulary scores low. More dimensions made it
worse. Masking numerals made it worse again — the numerals were the only thing
separating revenue from margin from headcount.

Worse still, embeddings are blind to negation: *"margin improved"* and *"margin
did not improve"* are near-identical vectors. A pure-embedding pipeline scores a
flat contradiction as unanimous agreement — the exact failure this system
exists to catch. Grouping claims by meaning is a judgment task, so a model does
it, and the deterministic logic validates the result.

### The eval caught a real bug

An early run badged three cases `high` trust that should not have been.
`verify_citations` took the *strongest* status across a cluster's evidence, so
one good citation masked a hallucinated one sitting beside it — a report
containing a fabricated source was being labelled high trust. Fixed by tracking
`disputed_citations` separately and capping trust when any citation fails.

---

## Files

Eight source files, one eval harness.

| File | Lines | Role |
|---|---:|---|
| `schemas.py` | ~200 | Every wire contract. Nothing reaches the UI unvalidated. |
| `router.py` | ~180 | Classification + panel selection. No model call. |
| `panel.py` | ~230 | Independent parallel model calls; failures captured, not raised. |
| `consensus.py` | ~330 | **Pure.** Clusters → verdicts → citations → trust status. |
| `synthesize.py` | ~250 | The three model-driven stages. |
| `workflow.py` | ~290 | Temporal orchestration. |
| `api.py` | ~140 | Two HTTP routes. No import from the host app. |
| `ui/TrustPanel.tsx` | ~440 | The page. No import from the host app. |
| `eval/eval_harness.py` | ~350 | Record/replay, 6 metrics, 3 injected regressions. |

`eval/fixtures/` holds data, not source: `cases.json`, `corpus.json`,
`normalizer_tape.json`.

The directory is self-contained — `api.py` builds its own Temporal client and
`TrustPanel.tsx` does its own fetch, so mounting it elsewhere is one route each
side. Integration into this repo touched host files that are *not* part of the
eight: a route in `App.tsx`, a nav entry in `Sidebar.tsx`, an icon, the
`.tp-*` block in `styles.css`, registration in `worker.py` and `main.py`, and
build-context changes in the Dockerfiles and `docker-compose.yml`.

---

## Running it

```bash
# Eval — no keys, no network. Python 3.11+ (pydantic 2 syntax).
pip install pydantic
python -m multi_model_trust.eval.eval_harness

# Full stack
cp .env.example .env      # add ANTHROPIC_API_KEY and OPENAI_API_KEY
docker compose up -d --build
open http://localhost:8081/trust
```

`TRUST_PANEL_TIER=economy` (the default) runs Haiku 4.5 + gpt-5-mini; `standard`
runs Sonnet 5 / Opus 5 / gpt-5. Panel *width* matters more than per-model
capability for detecting disagreement, so the demo runs economy.

`TRUST_JUDGE_MODEL=provider:model` overrides the normalizer/cross-examiner.

---

## Limits

Stated plainly, because the gaps matter more than the passing numbers.

- **Every metric currently reads 1.000.** The fixtures were authored alongside
  the code, so this says the implementation matches its own spec, not that it
  generalises. The honest read: the fixture set is not yet hard enough. The next
  case to write is one where the *normalizer itself* is wrong — every current
  case is one it groups correctly.
- **"Verified" means the quote exists, not that it entails the claim.** A model
  can cite a real span that does not support what it said and still score
  verified. Entailment needs a model; this needs a string search, and it catches
  the common failure, which is a citation of something never written.
- **The eval replays the normalizer.** It measures every deterministic decision,
  not the normalizer's own judgment. `--record` re-measures that, but there is
  no gate on it.
- **Cross-examination runs once per conflict, capped at 3.** More rounds buy
  latency, not resolution.
- **The router is keyword-based.** It will misclassify domain-ambiguous queries.
  It is deterministic and testable, which was the higher priority.
- **Two-model panels are common.** Three models would give a genuine tie-break;
  two only ever gives "they disagree". Width is capped by cost.
- **No streaming.** A query blocks for 20–40 seconds.
