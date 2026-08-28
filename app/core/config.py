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

    # --- database (MongoDB Atlas)
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "dada_numerology"
    MONGO_TIMEOUT_MS: int = 8000

    # --- otp
    OTP_LENGTH: int = 6
    OTP_TTL_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_SECONDS: int = 45
    OTP_DEV_ECHO: bool = True   # in dev the OTP is returned in the response + logged

    # --- email
    # Resend is preferred: it is an HTTPS API, so it works on hosts that block
    # outbound SMTP ports. SMTP_* is kept as a fallback transport.
    RESEND_API_KEY: str = ""
    RESEND_FROM: str = ""          # falls back to SMTP_FROM

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
    # Optional regex for origins that change per deploy, e.g. Vercel previews:
    #   ^https://dada-namerology-admin(-[a-z0-9-]+)?\.vercel\.app$
    CORS_ORIGIN_REGEX: str = ""

    @property
    def email_from(self) -> str:
        return self.RESEND_FROM or self.SMTP_FROM

    @property
    def email_enabled(self) -> bool:
        return bool(self.RESEND_API_KEY or self.SMTP_HOST)

    # --- cloudinary (profile photos + stored PDF reports)
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_CLOUD_API_KEY: str = ""
    CLOUDINARY_CLOUD_SECRET: str = ""
    CLOUDINARY_FOLDER: str = "dada-numerology"

    @property
    def cloudinary_enabled(self) -> bool:
        return bool(
            self.CLOUDINARY_CLOUD_NAME
            and self.CLOUDINARY_CLOUD_API_KEY
            and self.CLOUDINARY_CLOUD_SECRET
        )

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
