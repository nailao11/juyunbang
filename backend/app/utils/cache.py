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


def cache_delete(key):
    try:
        get_redis().delete(key)
    except Exception as e:
        logger.error(f"Redis删除失败: {key}, 错误: {e}")


def cache_delete_pattern(pattern):
    try:
        r = get_redis()
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception as e:
        logger.error(f"Redis批量删除失败: {pattern}, 错误: {e}")
