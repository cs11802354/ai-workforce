from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.auth import AuthDep, auth_enabled, check_password, issue_token
from app.config import settings
from app.routers import agents, conversations, internal, runs, scheduled_tasks
from multi_model_trust.api import router as trust_router

app = FastAPI(title="Agent Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every data route sits behind the gate; /healthz and /auth/* stay open.
app.include_router(agents.router, dependencies=[AuthDep])
app.include_router(conversations.router, dependencies=[AuthDep])
app.include_router(runs.router, dependencies=[AuthDep])
app.include_router(scheduled_tasks.router, dependencies=[AuthDep])
app.include_router(trust_router, dependencies=[AuthDep])
# Own auth (InternalAuthDep, applied per-route) — not the app-password gate.
app.include_router(internal.router)


class LoginRequest(BaseModel):
    password: str


@app.get("/auth/status")
def auth_status():
    """Lets the client know whether to show a login screen at all."""
    return {"required": auth_enabled()}


@app.post("/auth/login")
def login(payload: LoginRequest):
    if not auth_enabled():
        return {"token": ""}
    if not check_password(payload.password):
        raise HTTPException(401, "Incorrect password")
    return {"token": issue_token()}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
