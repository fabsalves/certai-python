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

    # --- Cinndi / WhatsApp ---
    CINNDI_API_URL: str = "https://api.cinndi.com/v2"
    CINNDI_API_KEY: str = ""
    CINNDI_SENDER_PHONE: str = "5519982863180"
    CINNDI_WEBHOOK_TOKEN: str = ""
    CINNDI_INSECURE_SSL: bool = False
    WHATSAPP_INVITE_TEMPLATE: str = "certai_convite_aula"
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
