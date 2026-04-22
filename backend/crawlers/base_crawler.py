"""
基础采集器：提供 HTTP fetch、数据库写入、热度去重等通用能力

注意（2026-04 重构）:
    原来的 _match_drama() / _discover_* 等"自动发现新剧"逻辑已移除。
    剧集清单现在由管理员通过 /admin 录入到 drama_platforms 表，
    爬虫只做读表 → 抓热度 → 写库 三件事。
"""
import time
import random
import requests
from loguru import logger
from fake_useragent import UserAgent

ua = UserAgent()


class BaseCrawler:
    """基础采集器，所有平台采集器继承此类"""

    def __init__(self, platform_name):
        self.platform_name = platform_name
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            'User-Agent': ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        self._saved_this_round = set()

    # --- HTTP ---
    def fetch(self, url, params=None, headers=None, retry=3):
        """带重试的 HTTP 请求"""
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
                logger.warning(f"[{self.platform_name}] 请求失败(第{i+1}次): {url}, 错误: {e}")
                if i < retry - 1:
                    time.sleep(random.uniform(3, 8))
                else:
                    logger.error(f"[{self.platform_name}] 请求最终失败: {url}")
                    return None

    def fetch_json(self, url, params=None, headers=None):
        """请求 JSON 接口"""
        resp = self.fetch(url, params=params, headers=headers)
        if resp:
            try:
                return resp.json()
            except Exception as e:
                logger.error(f"[{self.platform_name}] JSON 解析失败: {e}")
        return None

    # --- 去重 ---
    def _has_recent_heat(self, drama_id, platform_id, minutes=10):
        """检查是否在近 N 分钟内已保存过该剧的热度（防止短时间重复采集）"""
        try:
            from app.utils.db import query_one
            row = query_one(
                "SELECT id FROM heat_realtime "
                "WHERE drama_id=%s AND platform_id=%s "
                "AND record_time > DATE_SUB(NOW(), INTERVAL %s MINUTE) LIMIT 1",
                (drama_id, platform_id, minutes)
            )
            return row is not None
        except Exception:
            return False

    # --- 写库 ---
    def save_heat_data(self, drama_id, platform_id, heat_value, heat_rank=None):
        """保存热度数据（本轮内重复调用会被去重）"""
        dedup_key = (drama_id, platform_id)
        if dedup_key in self._saved_this_round:
            return
        self._saved_this_round.add(dedup_key)

        from app.utils.db import insert
        from datetime import datetime

        insert(
            "INSERT INTO heat_realtime (drama_id, platform_id, heat_value, heat_rank, record_time) "
            "VALUES (%s, %s, %s, %s, %s)",
            (drama_id, platform_id, heat_value, heat_rank, datetime.now())
        )

    def save_playcount(self, drama_id, platform_id, total_playcount):
        """保存播放量快照（芒果 TV 用）"""
        from app.utils.db import insert
        from datetime import datetime

        insert(
            "INSERT INTO playcount_snapshot (drama_id, platform_id, total_playcount, record_time) "
            "VALUES (%s, %s, %s, %s)",
            (drama_id, platform_id, total_playcount, datetime.now())
        )

    def log_task(self, task_type, status, records_count=0, error_message=None):
        """记录采集任务日志"""
        from app.utils.db import insert
        from datetime import datetime

        insert(
            "INSERT INTO crawl_tasks (task_type, status, start_time, end_time, "
            "records_count, error_message) VALUES (%s, %s, %s, %s, %s, %s)",
            (task_type, status, datetime.now(), datetime.now(), records_count, error_message)
        )

    def crawl(self):
        raise NotImplementedError
