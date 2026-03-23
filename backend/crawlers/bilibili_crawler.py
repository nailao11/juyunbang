from loguru import logger

from .base_crawler import BaseCrawler


class BilibiliCrawler(BaseCrawler):
    """B站数据采集器"""

    PLATFORM_ID = 5

    def __init__(self):
        super().__init__('哔哩哔哩')

    def crawl(self):
        """采集B站排行榜"""
        logger.info("[B站] 开始采集数据...")
        results = []

        try:
            # B站有公开API
            data = self._crawl_rank()
            results.extend(data)

            self.log_task('bilibili_heat', 'success', len(results))
            logger.info(f"[B站] 采集完成，共{len(results)}条数据")

        except Exception as e:
            logger.error(f"[B站] 采集异常: {e}")
            self.log_task('bilibili_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self):
        """采集B站热门排行"""
        # B站公开API
        url = 'https://api.bilibili.com/pgc/web/rank/list'
        params = {
            'day': '3',
            'season_type': '1'  # 1=番剧, 4=国产动画, 5=电视剧, 7=综艺
        }

        items = []

        for season_type, category in [('5', 'tv'), ('7', 'variety'), ('1', 'anime')]:
            params['season_type'] = season_type
            data = self.fetch_json(url, params=params)

            if not data or data.get('code') != 0:
                continue

            try:
                rank_list = data.get('result', {}).get('list', [])
                for i, item in enumerate(rank_list):
                    title = item.get('title', '')
                    heat = item.get('stat', {}).get('view', 0)
                    follow = item.get('stat', {}).get('follow', 0)
                    score = item.get('rating', '')

                    items.append({
                        'title': title,
                        'heat_value': heat,
                        'follow_count': follow,
                        'score': score,
                        'rank': i + 1,
                        'category': category,
                        'platform': 'bilibili'
                    })

            except Exception as e:
                logger.error(f"[B站] 解析{category}排行失败: {e}")

        return items
