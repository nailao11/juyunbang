"""
热剧榜 — 在播剧热度采集器（半自动架构 v5）

架构说明（2026-04 重构）:
    本版本抛弃了"自动发现新剧"的复杂链路，改为纯被动采集：
      1. 在播剧清单由管理员通过 Web 后台录入到 drama_platforms 表
      2. 本爬虫只负责：读取清单 → 挨个访问详情页 → 提取热度值 → 入库
      3. 旧版的 _discover_tencent/iqiyi/youku/mgtv_dramas() 全部删除

为什么做这个改造:
    各平台（尤其爱奇艺、优酷）的"新剧发现"API 字段结构不稳定，
    旧版代码已被验证存在致命 bug（爱奇艺/芒果TV 发现数恒为 0）。
    半自动架构让爬虫逻辑简化 60%，单点失败只影响单部剧的单平台。

热度提取方式（保留）:
    腾讯视频: 移动端 m.v.qq.com/x/cover/{cid}.html  → "XXXXX 热度"
    爱奇艺:   PC 端 www.iqiyi.com/{短码}.html       → "热度 XXXXX"
    优酷:     PC 端 v.youku.com/v_show/id_{showid}.html → "XXXXX 热度"
    芒果TV:   移动端 m.mgtv.com/b/{partId}/{clipId}.html → "X.X亿次播放"
"""

import re
import time
import random
from loguru import logger

from .base_crawler import BaseCrawler
from .browser_helper import BrowserHelper


class AiringCrawler(BaseCrawler):
    """在播剧热度采集器（读 drama_platforms 表）"""

    # 平台 short_name → 提取函数 映射（短名来自 platforms 表）
    # 提取函数签名: (browser, url) -> float
    PLATFORM_EXTRACTORS = {
        'tencent': '_extract_tencent_heat',
        'iqiyi':   '_extract_iqiyi_heat',
        'youku':   '_extract_youku_heat',
        'mgtv':    '_extract_mgtv_playcount',
    }

    def __init__(self):
        super().__init__('AiringCrawler')

    def crawl(self):
        """读取 drama_platforms，对每条 (剧 × 平台) 采集热度"""
        from app.utils.db import query

        logger.info("[AiringCrawler] 开始采集")

        rows = query("""
            SELECT dp.drama_id, dp.platform_id, dp.platform_drama_id, dp.platform_url,
                   d.title, p.short_name AS platform
            FROM drama_platforms dp
            JOIN dramas    d ON d.id = dp.drama_id
            JOIN platforms p ON p.id = dp.platform_id
            WHERE d.status = 'airing'
              AND p.is_active = 1
              AND dp.platform_url IS NOT NULL
              AND dp.platform_url <> ''
            ORDER BY dp.platform_id, dp.drama_id
        """)

        if not rows:
            logger.warning("[AiringCrawler] drama_platforms 表无在播剧。"
                           "请通过管理后台 /admin 录入。")
            self.log_task('airing_heat', 'success', 0, '无在播剧记录')
            return 0

        logger.info(f"[AiringCrawler] 待采集 {len(rows)} 条记录")
        saved = 0
        failed = 0

        with BrowserHelper(headless=True) as browser:
            for row in rows:
                try:
                    if self._has_recent_heat(row['drama_id'], row['platform_id'], minutes=10):
                        logger.debug(f"  [跳过] {row['title']}@{row['platform']} 10分钟内已采过")
                        continue

                    extractor_name = self.PLATFORM_EXTRACTORS.get(row['platform'])
                    if not extractor_name:
                        logger.warning(f"  [跳过] 未知平台: {row['platform']}")
                        continue

                    extractor = getattr(self, extractor_name)
                    value = extractor(browser, row['platform_url'])

                    if value and value > 0:
                        if row['platform'] == 'mgtv':
                            # 芒果TV: 播放量写 playcount_snapshot + heat_realtime（替代热度）
                            self.save_playcount(row['drama_id'], row['platform_id'], int(value))
                        self.save_heat_data(row['drama_id'], row['platform_id'], value)
                        saved += 1
                        logger.info(f"  [✓] {row['title']}@{row['platform']}: {value}")
                    else:
                        failed += 1
                        logger.warning(f"  [✗] {row['title']}@{row['platform']}: 未提取到热度")

                    # 礼貌延时，避免触发反爬
                    time.sleep(random.uniform(0.8, 2.0))

                except Exception as e:
                    failed += 1
                    logger.error(f"  [!] {row['title']}@{row['platform']} 异常: {e}")

        self.log_task('airing_heat', 'success', saved,
                      f'成功 {saved}，失败 {failed}' if failed else None)
        logger.info(f"[AiringCrawler] 完成: 保存 {saved} 条，失败 {failed} 条")
        return saved

    # ================================================================
    # 各平台热度提取函数（保持原实现，经实测仍有效）
    # ================================================================

    def _extract_tencent_heat(self, browser, url):
        """腾讯视频移动端 cover 页提取热度值"""
        # 如果传入的是 PC 端 URL，自动转成移动端
        url = url.replace('v.qq.com/x/cover', 'm.v.qq.com/x/cover', 1) \
                 .replace('//v.qq.com', '//m.v.qq.com', 1)

        html = browser.get_html(
            url, mobile=True, timeout=15000,
            close_selectors=['.mod_guide_box .btn_close', '.download_tips .btn_close']
        )
        if not html:
            return 0

        for pattern in [
            r'(\d[\d,]{2,})\s*热度',
            r'热度[：:]\s*(\d[\d,]{2,})',
            r'"heatScore"\s*:\s*"?(\d+)"?',
            r'"hot_val"\s*:\s*"?(\d+)"?',
        ]:
            m = re.search(pattern, html)
            if m:
                try:
                    return float(m.group(1).replace(',', ''))
                except ValueError:
                    continue
        return 0

    def _extract_iqiyi_heat(self, browser, url):
        """爱奇艺 PC 端详情页提取热度（自动关闭广告弹窗）"""
        html = browser.get_html(
            url, mobile=False, timeout=20000,
            close_selectors=[
                '.iqp-dialog .iqp-dialog-close',
                '.close-btn',
                '.qy-mod-close',
                '[class*="dialog-close"]',
                '[class*="ad-close"]',
            ]
        )
        if not html:
            return 0

        for pattern in [
            r'热度[^\d]{0,10}(\d{2,8})',
            r'(\d{2,8})\s*热度',
            r'hot[^\d]{0,10}(\d{2,8})',
            r'"hot"\s*:\s*"?(\d+)"?',
            r'"heatScore"\s*:\s*"?(\d+)"?',
            r'"heat"\s*:\s*"?(\d+)"?',
        ]:
            m = re.search(pattern, html)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    continue
        return 0

    def _extract_youku_heat(self, browser, url):
        """优酷 PC 端详情页提取热度"""
        html = browser.get_html(
            url, mobile=False, timeout=20000,
            close_selectors=['[class*="close"]', '.close-btn']
        )
        if not html:
            return 0

        for pattern in [
            r'(\d[\d,]{2,8})\s*热度',
            r'热度[^\d]{0,10}(\d[\d,]{2,8})',
            r'热度破[^\d]{0,5}(\d[\d,]{2,8})',
            r'"heat"\s*:\s*"?(\d+)"?',
            r'"hotValue"\s*:\s*"?(\d+)"?',
        ]:
            m = re.search(pattern, html)
            if m:
                try:
                    return float(m.group(1).replace(',', ''))
                except ValueError:
                    continue
        return 0

    def _extract_mgtv_playcount(self, browser, url):
        """
        芒果TV 提取播放量（无热度概念，用播放量替代）
        显示格式: "X.X亿次播放" / "XXXX万次播放" / "XXXX次播放"
        """
        # 芒果 TV 移动端展示更完整，PC 端也可
        html = browser.get_html(url, mobile=True, timeout=15000)
        if not html:
            return 0

        for pat, mult in [
            (r'(\d+(?:\.\d+)?)\s*亿\s*次?\s*播放', 100000000),
            (r'(\d+(?:\.\d+)?)\s*万\s*次?\s*播放', 10000),
            (r'(\d[\d,]{2,})\s*次\s*播放', 1),
        ]:
            m = re.search(pat, html)
            if m:
                try:
                    return float(m.group(1).replace(',', '')) * mult
                except ValueError:
                    continue
        return 0
