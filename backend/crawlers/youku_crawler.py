import json
from loguru import logger

from .base_crawler import BaseCrawler


class YoukuCrawler(BaseCrawler):
    """优酷热度采集器 — 使用优酷内部JSON接口"""

    PLATFORM_ID = 2

    # 优酷移动端排行接口（返回JSON，无需JS渲染）
    RANK_API = 'https://acs.youku.com/h5/mtop.youku.columbus.gateway.new.execute/1.0/'

    def __init__(self):
        super().__init__('优酷')

    def crawl(self):
        """采集优酷热播榜，匹配剧名并保存到数据库"""
        logger.info("[优酷] 开始采集热度数据...")
        results = []
        saved_count = 0

        try:
            # 电视剧热度榜
            tv_data = self._crawl_rank(category='电视剧')
            results.extend(tv_data)

            # 综艺热度榜
            variety_data = self._crawl_rank(category='综艺')
            results.extend(variety_data)

            type_map = {'电视剧': 'tv_drama', '综艺': 'variety'}

            for item in results:
                dtype = type_map.get(item.get('category'), 'tv_drama')
                drama_id = self._match_drama(item['title'], drama_type=dtype)
                if drama_id:
                    try:
                        self.save_heat_data(
                            drama_id=drama_id,
                            platform_id=self.PLATFORM_ID,
                            heat_value=item['heat_value'],
                            heat_rank=item.get('rank'),
                        )
                        saved_count += 1
                        logger.debug(
                            f"[优酷] 保存成功: {item['title']} "
                            f"热度={item['heat_value']} 排名={item.get('rank')}"
                        )
                    except Exception as e:
                        logger.error(f"[优酷] 保存失败 {item['title']}: {e}")

            self.log_task('youku_heat', 'success', saved_count)
            logger.info(
                f"[优酷] 采集完成，共{len(results)}条数据，"
                f"成功匹配并保存{saved_count}条"
            )

        except Exception as e:
            logger.error(f"[优酷] 采集异常: {e}")
            self.log_task('youku_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, category='电视剧'):
        """
        通过优酷移动端接口采集排行。
        优酷H5页面的数据来自内部网关接口，返回JSON。
        """
        # 方式1：优酷移动版排行页（服务端渲染，可以解析）
        category_map = {
            '电视剧': '97',
            '综艺': '85',
        }
        cid = category_map.get(category, '97')

        url = f'https://www.youku.com/category/show/c_{cid}.html'
        headers = {
            'Referer': 'https://www.youku.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

        # 尝试移动端API
        mobile_url = f'https://acs.youku.com/h5/mtop.youku.columbus.gateway.new.execute/1.0/'
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

        data = self.fetch_json(mobile_url, params=params, headers=headers)
        items = []

        if data:
            items = self._parse_api_response(data, category)

        if not items:
            # 回退方式：尝试优酷的公开排行数据接口
            fallback_url = f'https://list.youku.com/category/show/c_{cid}/s_1_d_1.html'
            logger.warning(f"[优酷] 主接口无数据，尝试备用方式采集{category}")
            items = self._crawl_rank_fallback(fallback_url, category)

        return items

    def _parse_api_response(self, data, category):
        """解析优酷API返回的JSON数据"""
        items = []
        try:
            # 优酷网关返回的数据结构
            result = data.get('data', {})
            if isinstance(result, str):
                result = json.loads(result)

            # 尝试多种可能的数据路径
            show_list = (
                result.get('data', {}).get('nodes', []) or
                result.get('nodes', []) or
                result.get('list', []) or
                []
            )

            for i, show in enumerate(show_list[:30]):
                title = (
                    show.get('title', '') or
                    show.get('show_name', '') or
                    show.get('name', '')
                )
                heat = (
                    show.get('heat', 0) or
                    show.get('hot_value', 0) or
                    show.get('total_vv', 0) or
                    0
                )

                if title:
                    items.append({
                        'title': self._normalize_title(title),
                        'heat_value': float(heat),
                        'rank': i + 1,
                        'category': category,
                        'platform': 'youku'
                    })

        except Exception as e:
            logger.error(f"[优酷] 解析API响应失败: {e}")

        return items

    def _crawl_rank_fallback(self, url, category):
        """备用方式：从列表页提取数据"""
        from bs4 import BeautifulSoup

        resp = self.fetch(url)
        if not resp:
            return []

        items = []
        try:
            soup = BeautifulSoup(resp.text, 'lxml')
            # 优酷列表页的结构
            show_items = soup.select('.pack-film-card, .p-thumb, li[data-id]')

            for i, item in enumerate(show_items[:30]):
                title_el = item.select_one('.title, a[title], .info-title')
                title = ''
                if title_el:
                    title = title_el.get('title', '') or title_el.get_text(strip=True)

                if title:
                    items.append({
                        'title': self._normalize_title(title),
                        'heat_value': max(0, 10000 - i * 300),  # 按排名估算热度
                        'rank': i + 1,
                        'category': category,
                        'platform': 'youku'
                    })

        except Exception as e:
            logger.error(f"[优酷] 备用解析失败: {e}")

        return items
