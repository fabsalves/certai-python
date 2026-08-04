import ssl

from redis.asyncio import Redis, from_url

from app.core.config import settings

_redis_kwargs: dict = {"encoding": "utf-8", "decode_responses": True}
if str(settings.REDIS_URL).startswith("rediss://"):
    _redis_kwargs["ssl_cert_reqs"] = ssl.CERT_NONE

redis_client: Redis = from_url(str(settings.REDIS_URL), **_redis_kwargs)


async def get_redis() -> Redis:
    return redis_client
