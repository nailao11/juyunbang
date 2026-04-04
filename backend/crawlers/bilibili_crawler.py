from loguru import logger

from .base_crawler import BaseCrawler


class BilibiliCrawler(BaseCrawler):
    """B站数据采集器 — 只采集在播中的剧集"""

    PLATFORM_ID = 5

    def __init__(self):
        super().__init__('哔哩哔哩')

    def crawl(self):
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
                        logger.error(f"[B站] 保存失败 {item['title']}: {e}")

            self.log_task('bilibili_heat', 'success', saved_count)
            logger.info(f"[B站] 采集完成，共{len(results)}条，在播{saved_count}条")

        except Exception as e:
            logger.error(f"[B站] 采集异常: {e}")
            self.log_task('bilibili_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self):
        """采集B站排行，通过 is_finish 字段识别是否完结"""
        url = 'https://api.bilibili.com/pgc/web/rank/list'
        items = []

        for season_type, category in [('5', 'tv'), ('7', 'variety'), ('1', 'anime')]:
            params = {'day': '3', 'season_type': season_type}
            data = self.fetch_json(url, params=params)

            if not data or data.get('code') != 0:
                logger.warning(f"[B站] {category} API返回错误")
                continue

            try:
                rank_list = data.get('result', {}).get('list', [])
                for i, item in enumerate(rank_list):
                    title = item.get('title', '')
                    heat = item.get('stat', {}).get('view', 0)

                    # 判断是否完结: is_finish=1 表示已完结
                    is_finish_val = item.get('is_finish', 0)
                    # new_ep.index_show 包含更新状态文字，如"全XX话"=完结
                    new_ep = item.get('new_ep', {})
                    index_show = new_ep.get('index_show', '')
                    is_finished = (
                        is_finish_val == 1 or
                        '全' in index_show
                    )

                    cover = (
                        item.get('ss_horizontal_cover', '') or
                        item.get('cover', '') or ''
                    )

                    items.append({
                        'title': title,
                        'heat_value': heat,
                        'poster_url': cover,
                        'rank': i + 1,
                        'category': category,
                        'is_finished': is_finished,
                        'platform': 'bilibili'
                    })

            except Exception as e:
                logger.error(f"[B站] 解析{category}排行失败: {e}")

        return items
