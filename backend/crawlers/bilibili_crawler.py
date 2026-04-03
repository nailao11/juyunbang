from loguru import logger

from .base_crawler import BaseCrawler


class BilibiliCrawler(BaseCrawler):
    """B站数据采集器 — 使用B站公开排行API，最稳定"""

    PLATFORM_ID = 5

    def __init__(self):
        super().__init__('哔哩哔哩')

    def crawl(self):
        """采集B站排行榜"""
        logger.info("[B站] 开始采集数据...")
        results = []
        saved_count = 0

        try:
            data = self._crawl_rank()
            results.extend(data)

            type_map = {'tv': 'tv_drama', 'variety': 'variety', 'anime': 'anime'}

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
                        if item.get('heat_value'):
                            self.save_playcount(
                                drama_id=drama_id,
                                platform_id=self.PLATFORM_ID,
                                total_playcount=item['heat_value'],
                            )
                        saved_count += 1
                    except Exception as e:
                        logger.error(f"[B站] 保存失败 {item['title']}: {e}")

            self.log_task('bilibili_heat', 'success', saved_count)
            logger.info(f"[B站] 采集完成，共{len(results)}条，保存{saved_count}条")

        except Exception as e:
            logger.error(f"[B站] 采集异常: {e}")
            self.log_task('bilibili_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self):
        """采集B站热门排行"""
        url = 'https://api.bilibili.com/pgc/web/rank/list'
        params = {'day': '3', 'season_type': '1'}

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
                    # B站封面：优先横版封面，其次竖版
                    cover = (
                        item.get('ss_horizontal_cover', '') or
                        item.get('cover', '') or
                        item.get('new_ep', {}).get('cover', '') or
                        ''
                    )

                    items.append({
                        'title': title,
                        'heat_value': heat,
                        'follow_count': follow,
                        'poster_url': cover,
                        'rank': i + 1,
                        'category': category,
                        'platform': 'bilibili'
                    })

            except Exception as e:
                logger.error(f"[B站] 解析{category}排行失败: {e}")

        return items
