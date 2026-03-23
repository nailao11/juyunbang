import pymysql
from dbutils.pooled_db import PooledDB
from loguru import logger

from ..config import Config

# 数据库连接池
_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=20,
            mincached=5,
            maxcached=10,
            blocking=True,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
    return _pool


def get_db():
    return get_pool().connection()


def query(sql, params=None):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"查询失败: {sql}, 参数: {params}, 错误: {e}")
        raise
    finally:
        conn.close()


def query_one(sql, params=None):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"查询失败: {sql}, 参数: {params}, 错误: {e}")
        raise
    finally:
        conn.close()


def execute(sql, params=None):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            affected = cursor.execute(sql, params)
            return affected
    except Exception as e:
        logger.error(f"执行失败: {sql}, 参数: {params}, 错误: {e}")
        raise
    finally:
        conn.close()


def insert(sql, params=None):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"插入失败: {sql}, 参数: {params}, 错误: {e}")
        raise
    finally:
        conn.close()


def insert_many(sql, params_list):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            affected = cursor.executemany(sql, params_list)
            return affected
    except Exception as e:
        logger.error(f"批量插入失败: {sql}, 错误: {e}")
        raise
    finally:
        conn.close()
