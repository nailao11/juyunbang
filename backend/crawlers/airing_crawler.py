"""
在播新剧热度采集器（主方案）
采集策略：
  1. 从各平台轻量API获取新剧列表（title, detail_url, air_date）
  2. 筛选近30天内上线的新剧
  3. 对每部剧使用 Playwright 打开详情页，渲染JS后提取真实热度值
  4. 去重：同剧同平台10分钟内已采集则跳过

平台热度位置（用户实测）：
  腾讯视频: PC/移动端均可，读取 "XXXXX热度"
  爱奇艺:   仅PC端，读取剧集详情页热度图标旁数字（可能有会员广告遮挡）
  优酷:     仅PC端，读取 "XXXXX热度"
  芒果TV:   无热度值，仅移动端显示 "X.X亿次播放"，记录播放量（供后续计算增长量）
"""

import re
import time
import random
from datetime import datetime, date, timedelta
from loguru import logger

from .base_crawler import BaseCrawler
from .browser_helper import BrowserHelper


# 采集窗口：近30天内上线的剧
NEW_DRAMA_WINDOW_DAYS = 30

# 单轮每平台最多处理的剧数（避免单轮过长）
MAX_DRAMAS_PER_PLATFORM = 20


class AiringCrawler(BaseCrawler):
    """
    在播新剧热度采集主爬虫 —— 一次调用采集全部4个平台。
    """

    # 平台ID映射
    PLATFORM_IDS = {
        'iqiyi': 1,
        'youku': 2,
        'tencent': 3,
        'mgtv': 4,
    }

    def __init__(self):
        super().__init__('AiringCrawler')
        self.today = date.today()
        self.cutoff = self.today - timedelta(days=NEW_DRAMA_WINDOW_DAYS)

    def crawl(self):
        """采集所有平台的新剧热度"""
        logger.info(f"[AiringCrawler] 开始，窗口={NEW_DRAMA_WINDOW_DAYS}天")
        total_saved = 0

        with BrowserHelper(headless=True) as browser:
            for platform_key, handler in [
                ('tencent', self._crawl_tencent),
                ('iqiyi',   self._crawl_iqiyi),
                ('youku',   self._crawl_youku),
                ('mgtv',    self._crawl_mgtv),
            ]:
                try:
                    count = handler(browser)
                    total_saved += count
                    logger.info(f"[AiringCrawler] {platform_key}: 保存{count}条")
                except Exception as e:
                    logger.error(f"[AiringCrawler] {platform_key}异常: {e}")

        self.log_task('airing_heat', 'success', total_saved)
        logger.info(f"[AiringCrawler] 全部完成，共{total_saved}条")
        return total_saved

    # ================================================================
    # 腾讯视频
    # ================================================================
    def _crawl_tencent(self, browser):
        """腾讯视频: 使用移动端 cover 页面提取热度值"""
        platform_id = self.PLATFORM_IDS['tencent']
        dramas = self._discover_tencent_dramas()
        if not dramas:
            logger.warning("[腾讯] 未发现新剧")
            return 0

        saved = 0
        for i, d in enumerate(dramas[:MAX_DRAMAS_PER_PLATFORM]):
            drama_id = self._match_drama(
                d['title'], drama_type='tv_drama',
                poster_url=d.get('poster', ''),
                air_date=d.get('air_date'),
            )
            if not drama_id:
                continue

            if self._has_recent_heat(drama_id, platform_id, minutes=10):
                continue

            url = f"https://m.v.qq.com/x/cover/{d['cid']}.html"
            heat = self._extract_tencent_heat(browser, url)
            self._save_platform_url(drama_id, platform_id, d['cid'], url)

            if heat > 0:
                self.save_heat_data(drama_id, platform_id, heat, heat_rank=i + 1)
                saved += 1
                logger.debug(f"[腾讯] {d['title']}: {heat}热度")

            time.sleep(random.uniform(0.5, 1.5))

        return saved

    def _discover_tencent_dramas(self):
        """获取腾讯视频新剧列表（含cid和首播日期）"""
        dramas = []
        # 通过 bu/pagesheet/list 获取新上线的剧
        resp = self.fetch(
            'https://v.qq.com/x/bu/pagesheet/list',
            params={'_all': '1', 'append': '1', 'channel': 'tv',
                    'listpage': '2', 'offset': '0', 'pagesize': '60', 'sort': '75'},
            headers={'Referer': 'https://v.qq.com/channel/tv'}
        )
        if not resp:
            return dramas

        text = resp.text
        # 每个 list_item 包含一部剧
        item_blocks = re.split(r'<div[^>]*class="[^"]*list_item[^"]*"', text)

        for block in item_blocks[1:]:
            # 标题
            m_title = re.search(r'title="([^"]{2,50})"', block)
            if not m_title:
                continue
            title = m_title.group(1).strip()

            # 封面链接 -> 提取cid (mzc00200xxx 或类似)
            m_link = re.search(r'href="https://v\.qq\.com/x/cover/([a-z0-9]+)\.html"', block)
            if not m_link:
                continue
            cid = m_link.group(1)

            # 封面图
            m_img = re.search(r'src="(https?://[^"]*(?:vcover|puui|puic)[^"]*)"', block)
            poster = m_img.group(1) if m_img else ''

            # 更新信息 -> 粗略推断air_date
            m_update = re.search(r'(\d{4}-\d{2}-\d{2})', block)
            air_date = m_update.group(1) if m_update else None

            # 已完结的跳过
            if re.search(r'全\d+集|已完结', block):
                continue

            dramas.append({
                'title': title,
                'cid': cid,
                'poster': poster,
                'air_date': air_date,
            })

        # 无法从列表页精确获取air_date → 全部视为候选，交给详情页筛选
        return dramas

    def _extract_tencent_heat(self, browser, url):
        """打开腾讯视频移动端cover页提取热度值"""
        html = browser.get_html(
            url, mobile=True, wait_for=None, timeout=15000,
            close_selectors=['.mod_guide_box .btn_close', '.download_tips .btn_close']
        )
        if not html:
            return 0

        # 提取 "23421热度" 类模式
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

    # ================================================================
    # 爱奇艺（PC端，需处理会员广告）
    # ================================================================
    def _crawl_iqiyi(self, browser):
        """爱奇艺: PC端详情页提取热度值"""
        platform_id = self.PLATFORM_IDS['iqiyi']
        dramas = self._discover_iqiyi_dramas()
        if not dramas:
            logger.warning("[爱奇艺] 未发现新剧")
            return 0

        saved = 0
        for i, d in enumerate(dramas[:MAX_DRAMAS_PER_PLATFORM]):
            drama_id = self._match_drama(
                d['title'], drama_type='tv_drama',
                poster_url=d.get('poster', ''),
                air_date=d.get('air_date'),
            )
            if not drama_id:
                continue
            if self._has_recent_heat(drama_id, platform_id, minutes=10):
                continue

            url = d['url']
            heat = self._extract_iqiyi_heat(browser, url)
            self._save_platform_url(drama_id, platform_id, d.get('album_id', ''), url)

            if heat > 0:
                self.save_heat_data(drama_id, platform_id, heat, heat_rank=i + 1)
                saved += 1
                logger.debug(f"[爱奇艺] {d['title']}: {heat}热度")

            time.sleep(random.uniform(0.5, 1.5))

        return saved

    def _discover_iqiyi_dramas(self):
        """从爱奇艺PCW API获取新剧列表"""
        dramas = []
        data = self.fetch_json(
            'https://pcw-api.iqiyi.com/search/recommend/list',
            params={'channel_id': '2', 'data_type': '1', 'mode': '24',
                    'page_id': '1', 'ret_num': '60'}
        )
        if not data:
            return dramas

        item_list = data.get('data', {}).get('list', []) or []
        for item in item_list:
            if not isinstance(item, dict):
                continue
            title = (item.get('title', '') or item.get('name', '')).strip()
            if not title:
                continue

            page_url = item.get('pageUrl', '') or item.get('albumLink', '')
            if not page_url:
                continue
            if not page_url.startswith('http'):
                page_url = 'https:' + page_url if page_url.startswith('//') else 'https://www.iqiyi.com' + page_url

            album_id = item.get('albumId', '') or item.get('qipuId', '')
            poster = item.get('imageUrl', '') or item.get('img', '')

            # 首播日期
            air_date = item.get('startDate', '') or item.get('firstIssueTime', '')
            if isinstance(air_date, (int, float)) and air_date > 1000000000:
                air_date = datetime.fromtimestamp(air_date / 1000 if air_date > 9999999999 else air_date).strftime('%Y-%m-%d')

            # 完结剧跳过
            desc = str(item.get('description', '') + ' ' + item.get('focus', ''))
            if '完结' in desc or '全集' in desc:
                continue

            dramas.append({
                'title': title,
                'url': page_url,
                'album_id': str(album_id),
                'poster': poster,
                'air_date': air_date,
            })

        return dramas

    def _extract_iqiyi_heat(self, browser, url):
        """爱奇艺PC页面提取热度值，自动关闭会员广告"""
        html = browser.get_html(
            url, mobile=False,
            wait_for=None,
            timeout=20000,
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

        # 爱奇艺热度值模式: "热度 7868" 或图标+数字
        for pattern in [
            r'热度[^\d]{0,10}(\d{2,8})',
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

    # ================================================================
    # 优酷（PC端）
    # ================================================================
    def _crawl_youku(self, browser):
        """优酷: PC端详情页提取热度值"""
        platform_id = self.PLATFORM_IDS['youku']
        dramas = self._discover_youku_dramas(browser)
        if not dramas:
            logger.warning("[优酷] 未发现新剧")
            return 0

        saved = 0
        for i, d in enumerate(dramas[:MAX_DRAMAS_PER_PLATFORM]):
            drama_id = self._match_drama(
                d['title'], drama_type='tv_drama',
                poster_url=d.get('poster', ''),
                air_date=d.get('air_date'),
            )
            if not drama_id:
                continue
            if self._has_recent_heat(drama_id, platform_id, minutes=10):
                continue

            url = d['url']
            heat = self._extract_youku_heat(browser, url)
            self._save_platform_url(drama_id, platform_id, d.get('show_id', ''), url)

            if heat > 0:
                self.save_heat_data(drama_id, platform_id, heat, heat_rank=i + 1)
                saved += 1
                logger.debug(f"[优酷] {d['title']}: {heat}热度")

            time.sleep(random.uniform(0.5, 1.5))

        return saved

    def _discover_youku_dramas(self, browser):
        """从优酷分类页抓取新剧列表（SPA需用浏览器）"""
        # 优酷电视剧分类: c_97
        url = 'https://www.youku.com/category/show/c_97_s_1_d_1.html'
        html = browser.get_html(url, mobile=False, timeout=20000)
        if not html:
            return []

        dramas = []
        # 从HTML中提取剧集链接和标题
        # 优酷show URL格式: v.youku.com/v_show/id_XXXX.html
        pattern = re.compile(
            r'href="(https://v\.youku\.com/v_show/id_[^"]+\.html)"[^>]*title="([^"]{2,50})"',
            re.DOTALL
        )
        seen_urls = set()
        for m in pattern.finditer(html):
            url_v = m.group(1)
            title = m.group(2).strip()
            if url_v in seen_urls or not title:
                continue
            seen_urls.add(url_v)

            # 提取show_id
            m_id = re.search(r'id_([^.]+)\.html', url_v)
            show_id = m_id.group(1) if m_id else ''

            dramas.append({
                'title': title,
                'url': url_v,
                'show_id': show_id,
                'poster': '',
                'air_date': None,
            })
            if len(dramas) >= 60:
                break

        return dramas

    def _extract_youku_heat(self, browser, url):
        """优酷PC详情页提取热度值"""
        html = browser.get_html(
            url, mobile=False, timeout=20000,
            close_selectors=['[class*="close"]', '.close-btn']
        )
        if not html:
            return 0

        for pattern in [
            r'(\d{3,8})\s*热度',
            r'热度[^\d]{0,10}(\d{3,8})',
            r'热度破[^\d]{0,5}(\d{3,8})',
            r'"heat"\s*:\s*"?(\d+)"?',
            r'"hotValue"\s*:\s*"?(\d+)"?',
        ]:
            m = re.search(pattern, html)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    continue
        return 0

    # ================================================================
    # 芒果TV（移动端，仅记录播放量）
    # ================================================================
    def _crawl_mgtv(self, browser):
        """
        芒果TV: 平台无热度值，仅移动端显示播放量。
        记录playcount_snapshot，后续由processors计算日增长量。
        """
        platform_id = self.PLATFORM_IDS['mgtv']
        dramas = self._discover_mgtv_dramas()
        if not dramas:
            logger.warning("[芒果TV] 未发现新剧")
            return 0

        saved = 0
        for i, d in enumerate(dramas[:MAX_DRAMAS_PER_PLATFORM]):
            drama_id = self._match_drama(
                d['title'], drama_type='tv_drama',
                poster_url=d.get('poster', ''),
                air_date=d.get('air_date'),
            )
            if not drama_id:
                continue
            if self._has_recent_heat(drama_id, platform_id, minutes=10):
                continue

            # 芒果TV移动端URL构造
            url = f"https://m.mgtv.com/b/{d['part_id']}/{d['vid']}.html"
            playcount = self._extract_mgtv_playcount(browser, url)
            self._save_platform_url(drama_id, platform_id, d.get('vid', ''), url)

            if playcount > 0:
                # 记录播放量快照
                self.save_playcount(drama_id, platform_id, int(playcount))
                # 同时将播放量写入heat_realtime（作为芒果TV的"热度"替代）
                self.save_heat_data(drama_id, platform_id, playcount, heat_rank=i + 1)
                saved += 1
                logger.debug(f"[芒果TV] {d['title']}: {playcount}播放")

            time.sleep(random.uniform(0.5, 1.5))

        return saved

    def _discover_mgtv_dramas(self):
        """芒果TV pianku API获取新剧列表"""
        dramas = []
        data = self.fetch_json(
            'https://pianku.api.mgtv.com/rider/list/pcweb/v3',
            params={'allowedRC': '1', 'platform': 'pcweb', 'channelId': '2',
                    'pn': '1', 'pc': '60', 'hudong': '1', 'orderType': 'c2'}
        )
        if not data:
            return dramas

        hit_list = data.get('data', {})
        if isinstance(hit_list, dict):
            hit_list = hit_list.get('hitDocs', []) or []

        for item in hit_list:
            if not isinstance(item, dict):
                continue
            title = (item.get('title', '') or item.get('name', '')).strip()
            if not title:
                continue

            # 完结剧跳过
            update_info = str(item.get('updateInfo', ''))
            if ('全' in update_info and '集' in update_info) or '完结' in update_info:
                continue

            # 芒果TV URL: m.mgtv.com/b/{part_id}/{vid}.html
            # playPartId + vid 组合
            part_id = item.get('playPartId', '') or item.get('partId', '')
            vid = item.get('playVid', '') or item.get('vid', '') or item.get('videoId', '')

            if not part_id or not vid:
                continue

            img = item.get('img', '') or item.get('clipImg', '')
            if img and not img.startswith('http'):
                img = f'https://1img.hitv.com/preview/{img}'

            release_date = item.get('releaseDate', '') or item.get('releaseYear', '')

            dramas.append({
                'title': title,
                'part_id': str(part_id),
                'vid': str(vid),
                'poster': img,
                'air_date': release_date,
            })

        return dramas

    def _extract_mgtv_playcount(self, browser, url):
        """
        芒果TV移动端提取播放量。
        显示格式: "8.3亿次播放" / "1234万次播放" / "8976次播放"
        """
        html = browser.get_html(url, mobile=True, timeout=15000)
        if not html:
            return 0

        # 匹配 "X.X亿次播放" / "XXXX万次播放" / "XXXX次播放"
        patterns = [
            (r'(\d+(?:\.\d+)?)\s*亿次播放', 100000000),
            (r'(\d+(?:\.\d+)?)\s*亿\s*次', 100000000),
            (r'(\d+(?:\.\d+)?)\s*万次播放', 10000),
            (r'(\d+(?:\.\d+)?)\s*万\s*次', 10000),
            (r'(\d[\d,]{2,})\s*次播放', 1),
        ]
        for pat, mult in patterns:
            m = re.search(pat, html)
            if m:
                try:
                    return float(m.group(1).replace(',', '')) * mult
                except ValueError:
                    continue
        return 0
