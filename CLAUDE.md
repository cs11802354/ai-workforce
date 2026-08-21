# ai-workforce — orientation

## Architecture (facts)

- Multi-service system defined in `docker-compose.yml`: `postgres`, `temporal` (+ `temporal-ui`), `backend`, `worker`, `frontend`.
- `backend/` is Python, uses Alembic for migrations (`backend/alembic/`, `backend/alembic.ini`), deps in `backend/requirements.txt`.
- `frontend/` is a Vite + TypeScript app (`frontend/package.json`, `vite.config.ts`, `tsconfig.json`).
- The app uses shared-password auth: `APP_PASSWORD` is set on the `backend` service and defined in `.env.example`.
- UI/frontend work: read `DESIGN.md` first — product feel, hierarchy rule, tokens, and component primitives to reuse before adding new markup/CSS.

## Commands

- Run the multi-model-trust eval: `python -m multi_model_trust.eval.eval_harness`

## Behavioral rules (guardrails)

- Do not bypass or skip the multi-model-trust eval step in the deploy pipeline to "fix" a failing deploy — it is an intentional gate: a regression there is meant to stop the deploy, not be worked around.
