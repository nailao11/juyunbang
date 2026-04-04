import json
import re
from loguru import logger

from .base_crawler import BaseCrawler


class YoukuCrawler(BaseCrawler):
    """
    优酷热度采集器
    策略：
      1. 优酷移动端网关API
      2. 优酷频道列表页HTML解析（最稳定备用）
    注意：优酷反爬较严格，失败属正常现象
    """

    PLATFORM_ID = 2

    def __init__(self):
        super().__init__('优酷')

    def crawl(self):
        logger.info("[优酷] 开始采集热度数据...")
        results = []
        saved_count = 0

        try:
            tv_data = self._crawl_rank(category='电视剧', cid='97')
            results.extend(tv_data)

            variety_data = self._crawl_rank(category='综艺', cid='85')
            results.extend(variety_data)

            type_map = {'电视剧': 'tv_drama', '综艺': 'variety'}

            for item in results:
                dtype = type_map.get(item.get('category'), 'tv_drama')
                drama_id = self._match_drama(
                    item['title'],
                    drama_type=dtype,
                    poster_url=item.get('poster_url', ''),
                    is_finished=item.get('is_finished', False),
                )
                if drama_id:
                    try:
                        self.save_heat_data(
                            drama_id=drama_id,
                            platform_id=self.PLATFORM_ID,
                            heat_value=item['heat_value'],
                            heat_rank=item.get('rank'),
                        )
                        saved_count += 1
                    except Exception as e:
                        logger.error(f"[优酷] 保存失败 {item['title']}: {e}")

            self.log_task('youku_heat', 'success', saved_count)
            logger.info(f"[优酷] 采集完成，共{len(results)}条，保存{saved_count}条")

        except Exception as e:
            logger.error(f"[优酷] 采集异常: {e}")
            self.log_task('youku_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, category='电视剧', cid='97'):
        """多接口策略"""
        # 方式1: 优酷移动端API
        items = self._fetch_from_api(cid, category)
        if items:
            return items

        # 方式2: 优酷搜索热门接口
        logger.warning(f"[优酷] 主接口无数据，尝试热门接口 {category}")
        items = self._fetch_from_hot(category)
        if items:
            return items

        # 方式3: HTML列表页
        logger.warning(f"[优酷] 热门接口无数据，尝试HTML采集 {category}")
        items = self._fetch_from_html(cid, category)
        return items

    def _fetch_from_api(self, cid, category):
        """优酷移动端网关API"""
        url = 'https://acs.youku.com/h5/mtop.youku.columbus.gateway.new.execute/1.0/'
        headers = {'Referer': 'https://www.youku.com/'}
        params = {
            'jsv': '2.7.2',
            'appKey': '24679788',
            'api': 'mtop.youku.columbus.gateway.new.execute',
            'v': '1.0',
            'data': json.dumps({
                'ms_codes': '2019030100',
                'params': json.dumps({'st': '1', 'pn': '1', 'ps': '30', 'cid': cid})
            })
        }

        data = self.fetch_json(url, params=params, headers=headers)
        if not data:
            return []

        items = []
        try:
            result = data.get('data', {})
            if isinstance(result, str):
                result = json.loads(result)

            show_list = (
                result.get('data', {}).get('nodes', []) or
                result.get('nodes', []) or
                result.get('list', []) or []
            )

            for i, show in enumerate(show_list[:30]):
                title = show.get('title', '') or show.get('show_name', '') or show.get('name', '')
                heat = show.get('heat', 0) or show.get('hot_value', 0) or show.get('total_vv', 0)
                poster = show.get('img', '') or show.get('cover', '') or show.get('thumb_url', '') or ''
                episode_info = show.get('episode_total', '') or show.get('last_episode', '')
                is_finished = show.get('completed', False) or '完结' in str(episode_info)

                if title:
                    items.append({
                        'title': self._normalize_title(title),
                        'heat_value': float(heat) if heat else max(1000, 9500 - i * 300),
                        'poster_url': poster,
                        'rank': i + 1,
                        'category': category,
                        'is_finished': is_finished,
                        'platform': 'youku'
                    })
        except Exception as e:
            logger.error(f"[优酷] API解析失败: {e}")

        return items

    def _fetch_from_hot(self, category):
        """优酷热门/搜索接口"""
        type_map = {'电视剧': '1', '综艺': '6'}
        type_id = type_map.get(category, '1')

        # 优酷搜索推荐接口
        url = 'https://search.youku.com/api/search'
        params = {
            'keyword': '热播' + category,
            'pg': '1',
            'pageSize': '30',
            'catType': type_id,
        }
        headers = {
            'Referer': 'https://search.youku.com/',
        }

        data = self.fetch_json(url, params=params, headers=headers)
        if not data:
            return []

        items = []
        try:
            results_list = data.get('pageComponentList', []) or data.get('data', []) or []
            for i, show in enumerate(results_list[:30]):
                title = show.get('title', '') or show.get('name', '')
                # 去HTML标签
                title = re.sub(r'<[^>]+>', '', title) if title else ''
                poster = show.get('img', '') or show.get('thumbUrl', '') or ''
                heat = show.get('heat', 0) or show.get('stripeBottom', 0) or 0

                if title:
                    items.append({
                        'title': self._normalize_title(title),
                        'heat_value': float(heat) if heat else max(1000, 9500 - i * 300),
                        'poster_url': poster,
                        'rank': i + 1,
                        'category': category,
                        'is_finished': False,
                        'platform': 'youku'
                    })
        except Exception as e:
            logger.error(f"[优酷] 热门接口解析失败: {e}")

        return items

    def _fetch_from_html(self, cid, category):
        """从优酷列表页HTML提取"""
        url = f'https://list.youku.com/category/show/c_{cid}/s_1_d_1.html'
        resp = self.fetch(url)
        if not resp:
            return []

        items = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 优酷列表页中的剧集卡片
            show_items = soup.select('.pack-film-card, .p-thumb, li[data-id], .yk-pack-film')

            for i, el in enumerate(show_items[:30]):
                title_el = el.select_one('.title, a[title], .info-title, .pack-title')
                title = ''
                if title_el:
                    title = title_el.get('title', '') or title_el.get_text(strip=True)

                img_el = el.select_one('img')
                poster = ''
                if img_el:
                    poster = img_el.get('src', '') or img_el.get('data-src', '') or ''

                if title:
                    items.append({
                        'title': self._normalize_title(title),
                        'heat_value': max(1000, 9500 - i * 300),
                        'poster_url': poster,
                        'rank': i + 1,
                        'category': category,
                        'is_finished': False,
                        'platform': 'youku'
                    })
        except ImportError:
            logger.warning("[优酷] bs4未安装，无法解析HTML")
        except Exception as e:
            logger.error(f"[优酷] HTML解析失败: {e}")

        return items
