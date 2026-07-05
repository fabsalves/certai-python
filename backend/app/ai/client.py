from openai import AsyncOpenAI

from app.core.config import settings

_client: AsyncOpenAI | None = None


def get_openai() -> AsyncOpenAI:
    """Cliente OpenAI compartilhado (singleton preguiçoso)."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client
