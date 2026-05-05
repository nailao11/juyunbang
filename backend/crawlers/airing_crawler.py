"""
热剧榜 — 在播剧热度采集器（半自动）

工作流：
    1. 管理员通过 /admin 录入完整页面链接到 drama_platforms 表
    2. APScheduler 每 15 分钟调用 AiringCrawler.crawl()
    3. 按 short_name 分发到对应平台的提取函数 → 入库

四个平台采集口径：
    腾讯视频   m.v.qq.com/x/m/play?cid=...&vid=...    body innerText 匹配 "热度"
    爱奇艺     www.iqiyi.com/a_xxx.html               base_info JSON.heat / label[red]
    优酷       v.youku.com/v_show/id_xxx.html         body innerText + HTML 兜底
    芒果TV     www.mgtv.com/b/{partId}/{clipId}.html  body innerText 匹配 "亿/万次播放"
"""

import re
import time
import random
from loguru import logger

from .base_crawler import BaseCrawler
from .browser_helper import BrowserHelper


class AiringCrawler(BaseCrawler):
    """读 drama_platforms 表，按平台分发到对应提取函数"""

    PLATFORM_EXTRACTORS = {
        'tencent': '_extract_tencent_heat',
        'iqiyi':   '_extract_iqiyi_heat',
        'youku':   '_extract_youku_heat',
        'mgtv':    '_extract_mgtv_playcount',
    }

    def __init__(self):
        super().__init__('AiringCrawler')
        self._last_debug = {}

    # ---- debug ----
    def _set_debug(self, **kwargs):
        """记录最近一次提取的诊断信息，供 /admin/test_extract 展示"""
        self._last_debug = kwargs

    def get_last_debug(self):
        return dict(self._last_debug)

    @staticmethod
    def _new_debug(platform, url, page_kind):
        return {
            'platform': platform,
            'input_url': url,
            'final_url': url,
            'page_kind': page_kind,
            'source_type': None,
            'match_pattern': None,
            'matched_snippet': None,
            'errors': [],
        }

    # ---- 主流程 ----
    def crawl(self):
        from app.utils.db import query

        logger.info('[AiringCrawler] 开始采集')

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
            logger.warning('[AiringCrawler] drama_platforms 无在播剧，请通过 /admin 录入')
            self.log_task('airing_heat', 'success', 0, '无在播剧记录')
            return 0

        logger.info(f'[AiringCrawler] 待采集 {len(rows)} 条记录')
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
                            self.save_playcount(row['drama_id'], row['platform_id'], int(value))
                        self.save_heat_data(row['drama_id'], row['platform_id'], value)
                        saved += 1
                        logger.info(f"  [✓] {row['title']}@{row['platform']}: {value}")
                    else:
                        failed += 1
                        logger.warning(f"  [✗] {row['title']}@{row['platform']}: 未提取到热度")

                    time.sleep(random.uniform(0.8, 2.0))

                except Exception as e:
                    failed += 1
                    logger.error(f"  [!] {row['title']}@{row['platform']} 异常: {e}")

        self.log_task('airing_heat', 'success', saved,
                      f'成功 {saved}，失败 {failed}' if failed else None)
        logger.info(f'[AiringCrawler] 完成: 保存 {saved} 条，失败 {failed} 条')
        return saved

    # ================================================================
    # 腾讯视频：移动播放页 body innerText
    # ================================================================
    def _extract_tencent_heat(self, browser, url):
        debug = self._new_debug('tencent', url, 'mobile_play')
        text = browser.get_rendered_text(
            url, mobile=True, timeout=20000,
            close_selectors=['.mod_guide_box .btn_close', '.download_tips .btn_close'],
            wait_after_ms=2000,
        )
        if not text:
            debug['errors'].append('rendered text empty')
            self._set_debug(**debug)
            return 0

        patterns = [
            (r'站内热度\s*([0-9]{2,9})',          'site_heat'),
            (r'([0-9]{2,9})\s*热度',              'num_then_heat'),
            (r'热度\s*[:：]?\s*([0-9]{2,9})',     'heat_then_num'),
        ]
        for pat, name in patterns:
            m = re.search(pat, text)
            if m:
                debug.update({
                    'source_type': 'rendered_text',
                    'match_pattern': name,
                    'matched_snippet': m.group(0).strip(),
                })
                self._set_debug(**debug)
                try:
                    return float(m.group(1))
                except ValueError:
                    continue

        debug['errors'].append('no heat pattern matched')
        self._set_debug(**debug)
        return 0

    # ================================================================
    # 爱奇艺：base_info JSON 接口为主，渲染文本 + 嵌入式 JSON 兜底
    # ================================================================
    def _extract_iqiyi_heat(self, browser, url):
        debug = self._new_debug('iqiyi', url, 'pc_album')

        data, meta = browser.capture_first_json_response(
            url,
            # 多关键字：iqiyi 偶尔会调整 base_info 路径，留几个 fallback
            url_keywords=[
                'mesh.if.iqiyi.com/tvg/v2/lw/base_info',  # 已确认主端点
                'mesh.if.iqiyi.com/tvg',                  # 同域兜底
                '/lw/base_info',                          # 路径兜底
                'pcw-api.iqiyi.com/album/album/baseinfo', # 历史 PC API
            ],
            # 收集所有相关请求，便于诊断"页面到底请求了什么"
            collect_keyword=[
                'mesh.if.iqiyi', 'iqiyi.com/api', 'pcw-api', 'cache.video.iqiyi',
                'base_info', 'baseinfo', '/heat', 'hotscore',
            ],
            mobile=False,
            timeout=30000,
            extra_headers={
                'Referer': 'https://www.iqiyi.com/',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            },
            wait_after_ms=8000,
            scroll=True,
        )

        if meta.get('final_url'):
            debug['final_url'] = meta['final_url']
        if meta.get('errors'):
            debug['errors'].extend(meta['errors'])
        if meta.get('candidate_urls'):
            debug['candidate_urls'] = meta['candidate_urls']

        # ========== 1. base_info JSON 命中 ==========
        if data:
            base = (data.get('data') or {}).get('base_data') or {}

            heat = base.get('heat')
            if heat not in (None, '', 0, '0'):
                try:
                    v = float(heat)
                    if v > 0:
                        debug.update({
                            'source_type': 'base_info_heat',
                            'match_pattern': 'data.base_data.heat',
                            'matched_snippet': str(int(v)) if v == int(v) else str(v),
                        })
                        self._set_debug(**debug)
                        return v
                except (TypeError, ValueError):
                    pass

            for item in (base.get('label') or []):
                try:
                    if item.get('style') == 'red':
                        txt = str(item.get('txt', '')).strip()
                        if txt.isdigit():
                            debug.update({
                                'source_type': 'base_info_label',
                                'match_pattern': 'data.base_data.label[red]',
                                'matched_snippet': txt,
                            })
                            self._set_debug(**debug)
                            return float(txt)
                except Exception:
                    continue

            debug['errors'].append('JSON 已捕获但 heat / label[red] 字段为空')
        else:
            debug['errors'].append('base_info JSON 未捕获，进入兜底（看 candidate_urls 排查实际请求）')

        # ========== 2. 渲染文本兜底 ==========
        text = browser.get_rendered_text(
            url, mobile=False, timeout=20000, wait_after_ms=3000, scroll=True,
        )
        if text:
            for pat, name in [
                (r'热度[^\d]{0,5}([0-9]{2,9})', 'heat_then_num_text'),
                (r'([0-9]{2,9})\s*热度',          'num_then_heat_text'),
            ]:
                m = re.search(pat, text)
                if m:
                    try:
                        v = float(m.group(1))
                        if v > 0:
                            debug.update({
                                'source_type': 'rendered_text_fallback',
                                'match_pattern': name,
                                'matched_snippet': m.group(0).strip(),
                            })
                            self._set_debug(**debug)
                            return v
                    except ValueError:
                        pass

        # ========== 3. HTML 嵌入式 JSON 兜底（window.__INITIAL_STATE__ 等） ==========
        html = browser.get_html(url, mobile=False, timeout=20000)
        if html:
            for pat, name in [
                (r'"heat"\s*:\s*"?([0-9]{2,9})"?',     'html_heat_field'),
                (r'"hotScore"\s*:\s*"?([0-9]{2,9})"?', 'html_hotScore'),
                (r'"hotValue"\s*:\s*"?([0-9]{2,9})"?', 'html_hotValue'),
            ]:
                m = re.search(pat, html)
                if m:
                    try:
                        v = float(m.group(1))
                        if v > 0:
                            debug.update({
                                'source_type': 'html_embedded_json',
                                'match_pattern': name,
                                'matched_snippet': m.group(0)[:80],
                            })
                            self._set_debug(**debug)
                            return v
                    except ValueError:
                        pass

        debug['errors'].append('rendered_text 与 html 兜底均未找到热度数字')
        self._set_debug(**debug)
        return 0

    # ================================================================
    # 优酷：PC 播放页 body innerText，HTML 兜底
    # ================================================================
    def _extract_youku_heat(self, browser, url):
        debug = self._new_debug('youku', url, 'pc_play')

        text = browser.get_rendered_text(
            url, mobile=False, timeout=20000,
            close_selectors=['[class*="close"]', '.close-btn'],
            wait_after_ms=1500,
        )
        if text:
            patterns = [
                (r'热度\s*破?\s*([0-9]{2,9})',     'heat_break'),
                (r'热度\s*[:：]?\s*([0-9]{2,9})',  'heat_then_num'),
                (r'([0-9]{2,9})\s*热度',           'num_then_heat'),
            ]
            for pat, name in patterns:
                m = re.search(pat, text)
                if m:
                    debug.update({
                        'source_type': 'rendered_text',
                        'match_pattern': name,
                        'matched_snippet': m.group(0).strip(),
                    })
                    self._set_debug(**debug)
                    try:
                        return float(m.group(1))
                    except ValueError:
                        continue

        # HTML 兜底（仅取 JSON 字段，避免大段无关 HTML）
        html = browser.get_html(url, mobile=False, timeout=20000)
        if html:
            for pat, name in [
                (r'"heat"\s*:\s*"?([0-9]{2,9})"?',     'json_heat'),
                (r'"hotValue"\s*:\s*"?([0-9]{2,9})"?', 'json_hotValue'),
            ]:
                m = re.search(pat, html)
                if m:
                    debug.update({
                        'source_type': 'html_json',
                        'match_pattern': name,
                        'matched_snippet': m.group(0)[:60],
                    })
                    self._set_debug(**debug)
                    try:
                        return float(m.group(1))
                    except ValueError:
                        continue

        debug['errors'].append('no heat pattern matched')
        self._set_debug(**debug)
        return 0

    # ================================================================
    # 芒果TV：body innerText 匹配播放量（无热度概念，用播放量替代 heat_realtime）
    # ================================================================
    def _extract_mgtv_playcount(self, browser, url):
        debug = self._new_debug('mgtv', url, 'page')

        text = browser.get_rendered_text(
            url, mobile=True, timeout=20000, wait_after_ms=1500,
        )
        if not text:
            debug['errors'].append('rendered text empty')
            self._set_debug(**debug)
            return 0

        patterns = [
            (r'(\d+(?:\.\d+)?)\s*亿\s*次?\s*播放', 100000000, 'yi'),
            (r'(\d+(?:\.\d+)?)\s*万\s*次?\s*播放', 10000,     'wan'),
            (r'(\d[\d,]{2,})\s*次\s*播放',         1,         'ci'),
        ]
        for pat, mult, name in patterns:
            m = re.search(pat, text)
            if m:
                debug.update({
                    'source_type': 'rendered_text',
                    'match_pattern': name,
                    'matched_snippet': m.group(0).strip(),
                })
                self._set_debug(**debug)
                try:
                    return float(m.group(1).replace(',', '')) * mult
                except ValueError:
                    continue

        debug['errors'].append('no playcount pattern matched')
        self._set_debug(**debug)
        return 0
