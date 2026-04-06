import json
import redis
from loguru import logger

from ..config import Config

_redis = None


def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=True
        )
    return _redis


def cache_get(key):
    try:
        data = get_redis().get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.error(f"Redis读取失败: {key}, 错误: {e}")
        return None


def cache_set(key, value, expire=300):
    try:
        get_redis().setex(key, expire, json.dumps(value, ensure_ascii=False, default=str))
    except Exception as e:
        logger.error(f"Redis写入失败: {key}, 错误: {e}")


