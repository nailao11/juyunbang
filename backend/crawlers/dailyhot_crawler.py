"""
DailyHot 统一热度采集器
通过 DailyHot API（开源项目 github.com/imsyy/DailyHotApi）一次性获取所有平台热度数据。

优势:
  - 一个数据源覆盖所有平台，无需逐个平台破解反爬
  - 返回真实站内热度值（从平台SSR/API中提取）
  - 开源可自建，也可用公共实例

支持平台:
  /iqiyi   -> 爱奇艺 (PLATFORM_ID=1)
  /youku   -> 优酷   (PLATFORM_ID=2)
  /tencent -> 腾讯   (PLATFORM_ID=3)
  /mgtv    -> 芒果TV (PLATFORM_ID=4)
"""

import os
from loguru import logger

from .base_crawler import BaseCrawler


# DailyHot API 地址，优先使用环境变量（方便自建部署）
DAILYHOT_BASE = os.environ.get('DAILYHOT_API', 'https://api-hot.imsyy.top')

# 平台映射: DailyHot路由 -> (platform_id, 平台名, drama_type)
PLATFORM_MAP = {
    'iqiyi':   (1, '爱奇艺',   'tv_drama'),
    'youku':   (2, '优酷',     'tv_drama'),
    'tencent': (3, '腾讯视频', 'tv_drama'),
    'mgtv':    (4, '芒果TV',   'tv_drama'),
}


class DailyHotCrawler(BaseCrawler):
    """
    统一热度采集器 — 通过 DailyHot API 获取所有平台数据。
    一次 crawl() 调用完成全部4个平台的采集。
    """

    PLATFORM_ID = 0  # 不使用固定ID，每个平台单独指定

    def __init__(self):
        super().__init__('DailyHot')
        self.base_url = DAILYHOT_BASE.rstrip('/')

    def crawl(self):
        """采集所有平台的热度数据"""
        logger.info(f"[DailyHot] 开始采集，API={self.base_url}")
        total_saved = 0

        for route, (platform_id, platform_name, default_type) in PLATFORM_MAP.items():
            try:
                saved = self._crawl_platform(route, platform_id, platform_name, default_type)
                total_saved += saved
            except Exception as e:
                logger.error(f"[DailyHot] {platform_name}采集异常: {e}")

        self.log_task('dailyhot_heat', 'success', total_saved)
        logger.info(f"[DailyHot] 全部完成，共保存{total_saved}条热度数据")
        return total_saved

    def _crawl_platform(self, route, platform_id, platform_name, default_type):
        """采集单个平台"""
        url = f'{self.base_url}/{route}'
        data = self.fetch_json(url)

        if not data:
            logger.warning(f"[DailyHot] {platform_name}: 无响应")
            return 0

        # DailyHot API 标准响应格式:
        # { "code": 200, "data": [ { "id", "title", "hot", "url", "cover", ... } ] }
        items = data.get('data', [])
        if not items:
            # 兼容其他可能的格式
            items = data.get('list', [])
        if not items:
            for k, v in data.items():
                if isinstance(v, list) and len(v) >= 5:
                    items = v
                    break

        if not items:
            logger.warning(f"[DailyHot] {platform_name}: 响应无数据列表, keys={list(data.keys())}")
            return 0

        logger.info(f"[DailyHot] {platform_name}: 获取{len(items)}条数据")

        saved_count = 0
        for i, item in enumerate(items[:30]):
            if not isinstance(item, dict):
                continue

            # 提取标题
            title = (item.get('title', '') or item.get('name', '') or '').strip()
            if not title:
                continue

            # 提取热度值
            heat = self._extract_heat(item)

            # 提取封面
            poster = (item.get('cover', '') or item.get('pic', '') or
                      item.get('img', '') or item.get('mobileCover', '') or '')

            # 判断完结
            desc = str(item.get('desc', '') or item.get('description', '') or '')
            is_finished = '完结' in desc or '全集' in desc

            # 匹配/创建剧集
            drama_id = self._match_drama(
                title,
                drama_type=default_type,
                poster_url=poster,
                is_finished=is_finished,
            )

            if drama_id and heat > 0:
                try:
                    self.save_heat_data(
                        drama_id=drama_id,
                        platform_id=platform_id,
                        heat_value=heat,
                        heat_rank=i + 1,
                    )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"[DailyHot] {platform_name} 保存失败 {title}: {e}")

        has_heat = saved_count
        logger.info(f"[DailyHot] {platform_name}: {len(items)}条, {has_heat}条有热度已保存")
        return saved_count

    def _extract_heat(self, item):
        """从item中提取热度值，兼容多种字段名和格式"""
        for key in ['hot', 'heat', 'heatScore', 'score', 'hotScore',
                     'hot_value', 'popularity', 'index']:
            val = item.get(key)
            if val is None:
                continue
            try:
                # 处理 "1.2万" "3.5亿" 等中文数字格式
                s = str(val).strip().replace(',', '')
                multiplier = 1
                if s.endswith('万'):
                    s = s[:-1]
                    multiplier = 10000
                elif s.endswith('亿'):
                    s = s[:-1]
                    multiplier = 100000000
                h = float(s) * multiplier
                if h > 0:
                    return h
            except (ValueError, TypeError):
                continue
        return 0
