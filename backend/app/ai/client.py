from anthropic import AsyncAnthropic

from app.core.config import settings

_client: AsyncAnthropic | None = None


def get_anthropic() -> AsyncAnthropic:
    """Cliente Anthropic compartilhado (singleton preguiçoso)."""
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client
