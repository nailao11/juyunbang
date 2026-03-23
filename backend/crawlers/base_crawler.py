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
        self.session.headers.update({
            'User-Agent': ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })

    def fetch(self, url, params=None, headers=None, retry=3):
        """带重试的HTTP请求"""
        for i in range(retry):
            try:
                # 随机延迟，避免被反爬
                time.sleep(random.uniform(1, 3))

                # 每次请求换一个UA
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

    def crawl(self):
        """子类需要实现此方法"""
        raise NotImplementedError

    def save_heat_data(self, drama_id, platform_id, heat_value, heat_rank=None):
        """保存实时热度数据到数据库"""
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

    def log_task(self, task_type, status, records_count=0, error_message=None):
        """记录采集任务日志"""
        from app.utils.db import insert
        from datetime import datetime

        insert(
            "INSERT INTO crawl_tasks (task_type, status, start_time, end_time, "
            "records_count, error_message) VALUES (%s, %s, %s, %s, %s, %s)",
            (task_type, status, datetime.now(), datetime.now(), records_count, error_message)
        )
