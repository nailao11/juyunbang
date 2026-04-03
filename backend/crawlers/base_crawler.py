import re
import time
import random
import requests
from loguru import logger
from fake_useragent import UserAgent

ua = UserAgent()


class BaseCrawler:
    """基础采集器，所有平台采集器继承此类"""

    # 剧名匹配缓存，所有实例共享
    _drama_cache = {}

    def __init__(self, platform_name):
        self.platform_name = platform_name
        self.session = requests.Session()
        self.session.trust_env = False  # 忽略系统代理
        self.session.headers.update({
            'User-Agent': ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        # 本轮已保存的 drama_id+platform_id 集合，用于去重
        self._saved_this_round = set()

    def fetch(self, url, params=None, headers=None, retry=3):
        """带重试的HTTP请求"""
        for i in range(retry):
            try:
                time.sleep(random.uniform(1, 3))
                self.session.headers['User-Agent'] = ua.random
                if headers:
                    self.session.headers.update(headers)
                resp = self.session.get(url, params=params, timeout=30)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                logger.warning(
                    f"[{self.platform_name}] 请求失败(第{i+1}次): {url}, 错误: {e}"
                )
                if i < retry - 1:
                    time.sleep(random.uniform(3, 8))
                else:
                    logger.error(f"[{self.platform_name}] 请求最终失败: {url}")
                    return None

    def fetch_json(self, url, params=None, headers=None):
        """请求JSON接口"""
        resp = self.fetch(url, params=params, headers=headers)
        if resp:
            try:
                return resp.json()
            except Exception as e:
                logger.error(f"[{self.platform_name}] JSON解析失败: {e}")
        return None

    def _normalize_title(self, title):
        """标准化标题：去除多余空格、特殊符号等"""
        if not title:
            return ''
        title = re.sub(r'[（(][^)）]*[)）]', '', title)
        title = title.strip()
        return title

    def _match_drama(self, title, drama_type='tv_drama', poster_url=''):
        """
        将采集到的标题匹配到数据库中的drama_id。
        优先精确匹配，其次模糊匹配(LIKE)。
        如果完全匹配不到，自动创建新剧集记录。
        如果匹配到的剧缺少封面，自动补充网络封面URL。
        返回 drama_id（始终不为 None）。
        """
        if not title:
            return None

        normalized = self._normalize_title(title)
        if not normalized:
            return None

        # 检查缓存
        if normalized in BaseCrawler._drama_cache:
            drama_id = BaseCrawler._drama_cache[normalized]
            # 即使命中缓存，如果有封面URL也尝试补充
            if poster_url:
                self._update_poster_if_empty(drama_id, poster_url)
            return drama_id

        from app.utils.db import query_one, insert, execute

        try:
            # 1. 精确匹配
            row = query_one(
                "SELECT id, poster_url FROM dramas WHERE title = %s LIMIT 1",
                (normalized,)
            )
            if row:
                drama_id = row['id']
                BaseCrawler._drama_cache[normalized] = drama_id
                if poster_url and not row.get('poster_url'):
                    self._update_poster_if_empty(drama_id, poster_url)
                return drama_id

            # 2. 模糊匹配 (LIKE)
            row = query_one(
                "SELECT id, poster_url FROM dramas WHERE title LIKE %s LIMIT 1",
                (f'%{normalized}%',)
            )
            if row:
                drama_id = row['id']
                BaseCrawler._drama_cache[normalized] = drama_id
                if poster_url and not row.get('poster_url'):
                    self._update_poster_if_empty(drama_id, poster_url)
                return drama_id

            # 3. 反向模糊匹配
            row = query_one(
                "SELECT id, title, poster_url FROM dramas WHERE %s LIKE CONCAT('%%', title, '%%') "
                "AND CHAR_LENGTH(title) >= 2 ORDER BY CHAR_LENGTH(title) DESC LIMIT 1",
                (normalized,)
            )
            if row:
                drama_id = row['id']
                BaseCrawler._drama_cache[normalized] = drama_id
                if poster_url and not row.get('poster_url'):
                    self._update_poster_if_empty(drama_id, poster_url)
                return drama_id

            # 4. 未匹配到：自动创建新剧集（含封面URL）
            drama_id = insert(
                "INSERT INTO dramas (title, type, status, poster_url) VALUES (%s, %s, 'airing', %s)",
                (normalized, drama_type, poster_url or None)
            )
            if drama_id:
                BaseCrawler._drama_cache[normalized] = drama_id
                logger.info(
                    f"[{self.platform_name}] 自动创建新剧集: '{normalized}' -> id={drama_id}"
                    f"{' (含封面)' if poster_url else ''}"
                )
                return drama_id

        except Exception as e:
            logger.error(f"[{self.platform_name}] 匹配/创建剧名'{normalized}'失败: {e}")

        return None

    def _update_poster_if_empty(self, drama_id, poster_url):
        """如果剧集缺少封面，用网络URL补充"""
        if not poster_url:
            return
        try:
            from app.utils.db import execute
            execute(
                "UPDATE dramas SET poster_url = %s WHERE id = %s AND (poster_url IS NULL OR poster_url = '')",
                (poster_url, drama_id)
            )
        except Exception as e:
            logger.debug(f"[{self.platform_name}] 更新封面失败: {e}")

    @classmethod
    def clear_drama_cache(cls):
        """清空剧名匹配缓存（通常在每轮采集开始时调用）"""
        cls._drama_cache.clear()

    def crawl(self):
        """子类需要实现此方法"""
        raise NotImplementedError

    def save_heat_data(self, drama_id, platform_id, heat_value, heat_rank=None):
        """
        保存实时热度数据到数据库。
        同一轮采集中，同一个drama_id+platform_id只保存一次（去重）。
        """
        dedup_key = (drama_id, platform_id)
        if dedup_key in self._saved_this_round:
            return  # 本轮已采集过，跳过
        self._saved_this_round.add(dedup_key)

        from app.utils.db import insert
        from datetime import datetime

        insert(
            "INSERT INTO heat_realtime (drama_id, platform_id, heat_value, heat_rank, record_time) "
            "VALUES (%s, %s, %s, %s, %s)",
            (drama_id, platform_id, heat_value, heat_rank, datetime.now())
        )

    def save_playcount(self, drama_id, platform_id, total_playcount):
        """保存播放量快照"""
        from app.utils.db import insert
        from datetime import datetime

        insert(
            "INSERT INTO playcount_snapshot (drama_id, platform_id, total_playcount, record_time) "
            "VALUES (%s, %s, %s, %s)",
            (drama_id, platform_id, total_playcount, datetime.now())
        )

    def save_social_data(self, drama_id, **kwargs):
        """保存社交媒体数据到 social_daily 表"""
        from app.utils.db import execute
        from datetime import date

        if not kwargs:
            return

        today = date.today()
        columns = ['drama_id', 'stat_date']
        values = [drama_id, today]
        update_parts = []

        for col, val in kwargs.items():
            columns.append(col)
            values.append(val)
            update_parts.append(f"{col} = VALUES({col})")

        col_str = ', '.join(columns)
        placeholder_str = ', '.join(['%s'] * len(values))
        update_str = ', '.join(update_parts)

        sql = (
            f"INSERT INTO social_daily ({col_str}) VALUES ({placeholder_str}) "
            f"ON DUPLICATE KEY UPDATE {update_str}"
        )
        execute(sql, tuple(values))

    def log_task(self, task_type, status, records_count=0, error_message=None):
        """记录采集任务日志"""
        from app.utils.db import insert
        from datetime import datetime

        insert(
            "INSERT INTO crawl_tasks (task_type, status, start_time, end_time, "
            "records_count, error_message) VALUES (%s, %s, %s, %s, %s, %s)",
            (task_type, status, datetime.now(), datetime.now(), records_count, error_message)
        )
