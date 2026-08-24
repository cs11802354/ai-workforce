from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/app"
    temporal_host: str = "localhost:7233"
    temporal_task_queue: str = "agent-tasks"
    knowledge_dir: str = "/data/knowledge"
    cors_origins: str = "http://localhost:5173,https://app.manishlab.dev"
    # Shared-password gate. Empty = gate disabled (local dev).
    app_password: str = ""
    # Gates POST /internal/*, called by the worker (not end users). Unlike
    # app_password, an empty value does NOT disable the gate — this endpoint
    # is reachable on the public backend URL, so it must always require a key.
    internal_api_key: str = ""

    class Config:
        env_prefix = ""


settings = Settings()
