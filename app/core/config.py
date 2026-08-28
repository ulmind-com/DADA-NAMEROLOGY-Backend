from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    PROJECT_NAME: str = "DADA'S NUMEROLOGY"
    API_V1: str = "/api/v1"
    ENV: str = "development"
    DEBUG: bool = True

    # --- security
    SECRET_KEY: str = "change-me-in-production-please-use-a-long-random-string"
    ACCESS_TOKEN_MINUTES: int = 60 * 24          # 1 day
    REFRESH_TOKEN_DAYS: int = 60
    SIGNUP_TOKEN_MINUTES: int = 20
    ALGORITHM: str = "HS256"

    # --- database
    DATABASE_URL: str = "sqlite:///./dada_numerology.db"

    # --- otp
    OTP_LENGTH: int = 6
    OTP_TTL_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_SECONDS: int = 45
    OTP_DEV_ECHO: bool = True   # in dev the OTP is returned in the response + logged

    # --- email (SMTP)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "DADA'S NUMEROLOGY <no-reply@dadanumerology.com>"
    SMTP_TLS: bool = True

    # --- google oauth (comma separated: web / ios / android client ids)
    GOOGLE_CLIENT_IDS_RAW: str = ""

    # --- cors (comma separated, or *)
    CORS_ORIGINS_RAW: str = "*"

    # --- bootstrap admin
    ADMIN_EMAIL: str = "admin@dadanumerology.com"
    ADMIN_PASSWORD: str = "Admin@12345"

    @staticmethod
    def _split(raw: str) -> list[str]:
        return [s.strip() for s in raw.split(",") if s.strip()]

    @property
    def GOOGLE_CLIENT_IDS(self) -> list[str]:
        return self._split(self.GOOGLE_CLIENT_IDS_RAW)

    @property
    def CORS_ORIGINS(self) -> list[str]:
        return self._split(self.CORS_ORIGINS_RAW) or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
