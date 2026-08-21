# Design rules

Read this before any UI/frontend change. It's rules, not a mood board — if a
rule and the existing code disagree, fix the code or update this file, don't
silently pick one.

## Product feel

This is an internal tool for managing and talking to AI agents — not a
consumer landing page, not a dense dev console. Target feel: **friendly
assistant** (think ChatGPT/Notion AI), not a Grafana/Linear-style dashboard.
That means: generous whitespace over density, soft shadows and rounded
corners over hard edges, calm color over saturated color. Warmth comes from
spacing and tone, not from adding more color.

## Hierarchy rule

**Conversation content leads.** On the Chat page, message content is the
most prominent thing on screen; agent identity, run status, and timestamps
stay small and quiet until the user needs them. On every other page (Agents,
Analytics), the same rule applies to whatever that page's primary object is
— an agent card, a chart — it gets the least chrome and the most visual
weight. Status/metadata (provider, model, timestamps) is always secondary,
never competing with the primary content for attention.

## Tokens

All color, radius, and shadow values live in `frontend/src/styles.css` as
CSS custom properties (`--bg`, `--surface`, `--text`, `--accent`, `--border`,
`--radius`, `--shadow-sm`, etc.), already defined for both light and dark.

- **Never hardcode a hex value or raw color in a component.** Use the CSS
  vars, or the helpers in `frontend/src/lib/colors.ts`
  (`tint()`, `avatarStyle()`, `colorForSeed()`) for anything that needs a
  seeded/tinted accent (avatars, stat icons).
- If a new token is genuinely needed (e.g. a spacing scale, a new semantic
  color), add it to `:root` in `styles.css` next to the existing ones — don't
  invent a one-off value inline.

## Component primitives

Before writing new markup for a button, badge, card, or stat tile, check
`frontend/src/components/`:

- `Button.tsx` — `Button` component + `buttonClass()` helper (use the helper
  for `<Link>`, since a router `Link` can't render as a native `<button>`).
  Variants: `default` / `primary` / `ghost`; sizes: `md` / `sm`; `danger`
  modifier.
- `Badge.tsx` — `Badge` component. Plain / `muted` / `status`
  (`completed` / `failed` / `running`), optional leading `dot`.
- `Card.tsx` — `Card` (generic surface container), plus `StatCard` /
  `StatGrid` for the stat-strip-with-loading-skeleton pattern used on
  Home, Agents, and Analytics.
- `Markdown.tsx` — renders assistant message content; anything that needs to
  show LLM-generated text should go through this, not raw `{content}`.

**Rule of thumb:** if you're about to type `className="btn btn-..."` or
copy-paste a stat-card block, stop — use the primitive instead. If no
primitive fits, extend an existing one with a new variant before adding a
new one-off CSS class. Only add a genuinely new primitive when a pattern is
about to be used in a second place.

## Copy voice

UI copy (labels, empty states, error messages) should match the same voice
the agents themselves are instructed to use
(see `HOUSE_STYLE` in `worker/activities.py`): lead with the answer, be
brief, no preambles or padding, no invented alternatives. A UI that's terse
and calm in its copy but chatty and apologetic in its error messages feels
like two different products.

## Non-goals

- This is not a full style guide or brand book — no logo usage rules, no
  marketing site guidance.
- No Storybook/component-preview tooling yet. Revisit once the primitive set
  in `components/` grows past ~8-10 pieces.
