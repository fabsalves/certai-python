from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from pydantic import Field, PostgresDsn, RedisDsn, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def redis_url_for_db(redis_url: str, db: int) -> str:
    """Build Redis URL for a logical DB; Heroku rediss:// needs ssl_cert_reqs for Celery."""
    parsed = urlparse(redis_url)
    query = parse_qs(parsed.query)
    if parsed.scheme == "rediss" and "ssl_cert_reqs" not in query:
        query["ssl_cert_reqs"] = ["CERT_NONE"]
    return urlunparse(
        parsed._replace(path=f"/{db}", query=urlencode({k: v[0] for k, v in query.items()}))
    )


class Settings(BaseSettings):
    """Configuração central. Tudo vem de variáveis de ambiente (.env)."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    ENV: Literal["dev", "staging", "prod"] = "dev"
    PROJECT_NAME: str = "CertAI"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # --- Segurança ---
    SECRET_KEY: str = Field(min_length=32)
    ENCRYPTION_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    JWT_ALGORITHM: str = "HS256"
    # Origens liberadas no CORS (lista separada por vírgula no .env)
    CORS_ORIGINS: str = "http://localhost:5173"
    # Host headers aceitos em prod (TrustedHostMiddleware)
    ALLOWED_HOSTS: str = (
        "*.certai.app,certai.app,*.certai.com.br,certai.com.br,*.herokuapp.com"
    )

    # --- Banco ---
    # Heroku Postgres injeta DATABASE_URL; POSTGRES_* continuam válidos em dev.
    DATABASE_URL: str | None = None
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "certai"

    # --- Redis ---
    REDIS_URL: RedisDsn = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # --- IA (OpenAI — mesmo provedor do Realtime com alunos) ---
    OPENAI_API_KEY: str = ""
    ENGINE_MODEL: str = "gpt-4o"
    HUMANIZER_MODEL: str = "gpt-4o-mini"
    EVALUATOR_MODEL: str = "gpt-4o"
    GROQ_API_KEY: str = ""
    GROQ_TRANSCRIBE_MODEL: str = "whisper-large-v3"

    # --- Voz / handoff (link público /voz/:token) ---
    FRONTEND_BASE_URL: str = "http://localhost:5173"
    VOICE_HANDOFF_EXPIRE_HOURS: int = 48

    # --- OpenAI Realtime (voz ao vivo) ---
    OPENAI_REALTIME_MODEL: str = "gpt-realtime-2"
    OPENAI_REALTIME_VOICE: str = "coral"
    OPENAI_REALTIME_REASONING_EFFORT: str = "low"
    OPENAI_REALTIME_TRANSCRIPTION_MODEL: str = "gpt-4o-mini-transcribe"
    OPENAI_REALTIME_TRANSCRIPTION_LANGUAGE: str = "pt"
    # VAD: server_vad; tunable via ENV (prefix_padding, silence_duration, threshold).
    OPENAI_REALTIME_TURN_DETECTION: Literal["semantic_vad", "server_vad"] = "server_vad"
    OPENAI_REALTIME_VAD_EAGERNESS: Literal["auto", "low", "medium", "high"] = "low"
    OPENAI_REALTIME_VAD_THRESHOLD: float = 0.9
    OPENAI_REALTIME_VAD_PREFIX_PADDING_MS: int = 500
    OPENAI_REALTIME_VAD_SILENCE_DURATION_MS: int = 1200
    OPENAI_REALTIME_INTERRUPT_RESPONSE: bool = True

    # --- Storage (local em dev; S3 em staging/prod) ---
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    STORAGE_LOCAL_ROOT: str = "./media"
    AWS_BUCKET: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # --- Cinndi / WhatsApp ---
    CINNDI_API_URL: str = "https://api.cinndi.com/v2"
    CINNDI_API_KEY: str = ""
    CINNDI_SENDER_PHONE: str = "5519982863180"
    CINNDI_WEBHOOK_TOKEN: str = ""
    CINNDI_INSECURE_SSL: bool = False
    WHATSAPP_INVITE_TEMPLATE: str = "certai_convite_aula"
    WHATSAPP_INVITE_VOICE_TEMPLATE: str = "certai_convite_aula_voz_v2"
    WHATSAPP_INVITE_USE_VOICE_TEMPLATE: bool = False
    WHATSAPP_TEMPLATE_LANG: str = "pt_BR"
    ASSISTANT_NAME: str = "Lira"
    INBOUND_DEBOUNCE_SECONDS: int = 5
    PUBLIC_API_BASE_URL: str = "http://localhost:8000"

    # --- Custos de IA ---
    # Só exibição: todo cálculo e persistência são em USD.
    USD_BRL_RATE: float = 5.50

    @model_validator(mode="after")
    def derive_celery_redis_urls(self) -> "Settings":
        redis_url = str(self.REDIS_URL)
        if "localhost" in redis_url:
            return self
        # RedisCloud (Heroku addon) só expõe DB 0 — broker e backend compartilham a instância.
        db_index = 0 if "redislabs.com" in redis_url else 1
        backend_db = 0 if "redislabs.com" in redis_url else 2
        if self.CELERY_BROKER_URL == "redis://localhost:6379/1":
            self.CELERY_BROKER_URL = redis_url_for_db(redis_url, db_index)
        if self.CELERY_RESULT_BACKEND == "redis://localhost:6379/2":
            self.CELERY_RESULT_BACKEND = redis_url_for_db(redis_url, backend_db)
        return self

    @computed_field
    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                return url.replace("postgres://", "postgresql+asyncpg://", 1)
            if url.startswith("postgresql://"):
                return url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        if not self.POSTGRES_USER or not self.POSTGRES_PASSWORD:
            raise ValueError("Set DATABASE_URL or POSTGRES_USER/POSTGRES_PASSWORD")
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @computed_field
    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
