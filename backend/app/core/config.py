from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    JWT_ALGORITHM: str = "HS256"
    # Origens liberadas no CORS (lista separada por vírgula no .env)
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Banco ---
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
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
    # VAD: server_vad; desktop 0.8, mobile 0.9 (client informa perfil no /token).
    OPENAI_REALTIME_TURN_DETECTION: Literal["semantic_vad", "server_vad"] = "server_vad"
    OPENAI_REALTIME_VAD_EAGERNESS: Literal["auto", "low", "medium", "high"] = "low"
    OPENAI_REALTIME_VAD_THRESHOLD: float = 0.8
    OPENAI_REALTIME_VAD_THRESHOLD_MOBILE: float = 0.9
    OPENAI_REALTIME_VAD_PREFIX_PADDING_MS: int = 500
    OPENAI_REALTIME_VAD_SILENCE_DURATION_MS: int = 1200
    OPENAI_REALTIME_INTERRUPT_RESPONSE: bool = True
    # Mute físico do mic enquanto Lira fala — escape hatch; default off (server_vad 0.8 + AEC).
    OPENAI_REALTIME_MUTE_WHILE_SPEAKING: bool = False

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

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
