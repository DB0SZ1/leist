from redis.asyncio import Redis, from_url
from app.config import settings

_redis: Redis = None

async def init_redis():
    global _redis
    if settings.ENV == "development":
        # In development, Redis is optional. If connection fails, we log and proceed without it.
        try:
            _redis = from_url(settings.REDIS_URL, decode_responses=True)
            await _redis.ping()
            return _redis
        except Exception as e:
            print(f"Redis not available in development: {e}. Caching will be disabled.")
            _redis = None
            return None
    
    _redis = from_url(settings.REDIS_URL, decode_responses=True)
    return _redis

async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        await init_redis()
    return _redis

async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
