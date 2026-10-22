"""Application settings (env-prefixed ``HR_``, optional ``.env`` in backend/)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HR_", env_file=".env", extra="ignore")

    # Connection the app itself uses: non-superuser role created by migration 0002.
    app_database_url: str = (
        "postgresql+asyncpg://hr_app:hr_app_dev@127.0.0.1:5432/hr_dev"
    )
    # Privileged connection used only by Alembic (schema owner runs migrations).
    migration_database_url: str = (
        "postgresql+asyncpg://peyman@/postgres?host=/var/run/postgresql"
    )
    # Password assigned to the hr_app login role when migrations (re)create it.
    app_db_password: str = "hr_app_dev"

    cookie_secure: bool = True  # false only for plain-http local dev
    session_lifetime_seconds: int = 60 * 60 * 24 * 30  # 30 days

    # Secrets for fastapi-users token features (verification/reset arrive with
    # ticket 18's System Mailbox; present now so the manager is wired once).
    reset_password_token_secret: str = "change-me-reset"
    verification_token_secret: str = "change-me-verify"

    # Where `vite build` output lives, served by FastAPI when present.
    frontend_dist: str = "../frontend/dist"

    # --- Resume parsing (ticket 11, spec §7.3) ---
    # Model names live in config, never in code (spec §4.5): workhorse and
    # escalation tier for the one strict structured-output call. base_url
    # points the SDK at a gateway when one is in use.
    openai_api_key: str = ""
    openai_base_url: str | None = None
    resume_extract_model: str = "gpt-5.6-luna"
    resume_extract_model_escalation: str = "gpt-6.1-sol"
    resume_extract_confidence_threshold: float = 0.6
    resume_text_cap_chars: int = 24_000
    resume_max_bytes: int = 10 * 1024 * 1024
    # Poll cadence for the Postgres jobs-table worker loop.
    worker_poll_seconds: float = 1.0


settings = Settings()
