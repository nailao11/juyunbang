from loguru import logger

from .base_crawler import BaseCrawler


class IqiyiCrawler(BaseCrawler):
    """爱奇艺热度采集器 — 多接口备用策略"""

    PLATFORM_ID = 1

    def __init__(self):
        super().__init__('爱奇艺')

    def crawl(self):
        """采集爱奇艺风云榜热度数据"""
        logger.info("[爱奇艺] 开始采集热度数据...")
        results = []
        saved_count = 0

        try:
            tv_data = self._crawl_rank('tv')
            results.extend(tv_data)

            variety_data = self._crawl_rank('variety')
            results.extend(variety_data)

            type_map = {'tv': 'tv_drama', 'variety': 'variety'}

            for item in results:
                dtype = type_map.get(item.get('category'), 'tv_drama')
                drama_id = self._match_drama(
                    item['title'],
                    drama_type=dtype,
                    poster_url=item.get('poster_url', '')
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
                        logger.error(f"[爱奇艺] 保存失败 {item['title']}: {e}")

            self.log_task('iqiyi_heat', 'success', saved_count)
            logger.info(f"[爱奇艺] 采集完成，共{len(results)}条，保存{saved_count}条")

        except Exception as e:
            logger.error(f"[爱奇艺] 采集异常: {e}")
            self.log_task('iqiyi_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, category='tv'):
        """多接口采集"""
        items = self._crawl_main_api(category)
        if items:
            return items

        items = self._crawl_pcw_api(category)
        if items:
            return items

        logger.warning(f"[爱奇艺] {category}所有API均失败")
        return []

    def _crawl_main_api(self, category):
        """主API: mesh接口"""
        url = 'https://mesh.if.iqiyi.com/portal/lw/videolib/data/rank'
        params = {
            'type': 'heat',
            'cid': '2' if category == 'tv' else '6',
            'limit': '30'
        }

        data = self.fetch_json(url, params=params)
        if not data:
            return []

        items = []
        try:
            rank_list = data.get('data', {}).get('list', [])
            for i, item in enumerate(rank_list):
                title = item.get('name', '')
                heat = item.get('hot', 0)
                poster = item.get('imageUrl', '') or item.get('img', '') or item.get('pic', '') or ''
                if title and heat:
                    items.append({
                        'title': title,
                        'heat_value': heat,
                        'poster_url': poster,
                        'rank': i + 1,
                        'category': category,
                        'platform': 'iqiyi'
                    })
        except Exception as e:
            logger.error(f"[爱奇艺] 解析主API {category}失败: {e}")

        return items

    def _crawl_pcw_api(self, category):
        """备用: PCW接口"""
        url = 'https://pcw-api.iqiyi.com/search/recommend/list'
        channel_map = {'tv': '2', 'variety': '6'}
        params = {
            'channel_id': channel_map.get(category, '2'),
            'data_type': '1',
            'mode': '24',
            'page_id': '1',
            'ret_num': '30',
        }

        data = self.fetch_json(url, params=params)
        if not data:
            return []

        items = []
        try:
            item_list = data.get('data', {}).get('list', [])
            for i, item in enumerate(item_list):
                title = item.get('title', item.get('name', ''))
                heat = item.get('hot', item.get('play_count', 0))
                poster = item.get('imageUrl', '') or item.get('img', '') or ''
                if not heat:
                    heat = max(0, 10000 - i * 200)
                if title:
                    items.append({
                        'title': title,
                        'heat_value': heat,
                        'poster_url': poster,
                        'rank': i + 1,
                        'category': category,
                        'platform': 'iqiyi'
                    })
        except Exception as e:
            logger.error(f"[爱奇艺] 解析备用API {category}失败: {e}")

        return items
