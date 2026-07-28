# AI-use disclosure

Claude (Opus 5, via Claude Code) drafted essentially all of the code in this
directory — the eight source files, the eval harness, the fixture cases, and
this README — working from an architecture I specified up front: router → panel
→ normalize → agreement matrix → cross-examine on material conflict → synthesize
back into one report, with a defined output contract (recommended answer, trust
status, agreements, disagreements, evidence, remaining uncertainty). I directed
the design decisions and the scope; Claude wrote the implementation, ran it, and
iterated against the eval.

What I hand-verified rather than took on trust:

- **The consensus rules.** I read `consensus.py` line by line, since it is the
  only place the product's actual judgments are made. I checked the verdict
  ladder, the confidence floor on conflicts, and the rule that unanimity is
  measured against the whole panel rather than the models that happened to raise
  a claim.
- **The eval's ground truth.** I checked the expected clusters, verdicts,
  conflicts, and citation labels in `fixtures/cases.json` by hand. The metrics
  are only worth what the ground truth is worth, and an eval whose fixtures were
  written by the same model that wrote the code is worth checking.
- **The failure demonstrations.** I ran all three `--mutate` regressions and
  confirmed each exits non-zero, and that the clean run passes.
- **End-to-end behaviour against live models.** I ran real queries through the
  deployed stack — cross-provider panel, verified citations, a query the corpus
  deliberately cannot answer — and read the reports to confirm the pipeline was
  not agreeing with itself by construction.

Two things worth recording because they change how much the code should be
trusted:

- Claude initially proposed clustering claims with sentence embeddings and I
  accepted it. It then measured the approach against the fixtures, found no
  threshold separates the data (table in the README), and reverted to the
  LLM-normalizer design from my original diagram. The measurement, not the
  intuition, settled it.
- The first eval run passed only 3 of 4 metrics and surfaced a genuine bug —
  clusters with a hallucinated citation alongside a good one were being badged
  high trust. That fix came from the eval, not from review.

Claude also wrote the surrounding platform this is mounted in (agents, chat,
Temporal transpiler, auth gate), which is my own ongoing project and not part of
this submission.
