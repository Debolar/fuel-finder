"""Settings come from environment variables, so the same image runs anywhere."""

import os


class Settings:
    def __init__(self) -> None:
        # When DATABASE_URL is set, stations are stored in PostgreSQL.
        # When it is empty, an in-memory store is used (data is lost on restart).
        self.database_url = os.getenv("DATABASE_URL", "")
        self.app_version = os.getenv("APP_VERSION", "dev")
        self.environment = os.getenv("APP_ENV", "local")
        self.port = int(os.getenv("PORT", "8000"))


settings = Settings()
