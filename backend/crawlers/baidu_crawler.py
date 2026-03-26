from loguru import logger

from .base_crawler import BaseCrawler


class BaiduCrawler(BaseCrawler):
    """百度数据采集器 - 社交媒体类，保存到 social_daily"""

    def __init__(self):
        super().__init__('百度')

    def crawl(self):
        """采集百度搜索指数数据，匹配剧名并保存到 social_daily"""
        logger.info("[百度] 开始采集数据...")
        results = []
        saved_count = 0

        try:
            # 百度实时热搜榜
            data = self._crawl_hot_search()
            results.extend(data)

            # 匹配剧名并汇总百度指数
            drama_index = {}
            for item in results:
                keyword = item.get('keyword', '')
                drama_id = self._match_drama(keyword)
                if drama_id:
                    # 取最高热搜值作为百度指数
                    heat = item.get('heat_value', 0)
                    if drama_id not in drama_index or heat > drama_index[drama_id]:
                        drama_index[drama_id] = heat

            # 保存百度指数到 social_daily
            for drama_id, value in drama_index.items():
                try:
                    self.save_social_data(
                        drama_id=drama_id,
                        baidu_index=value,
                    )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"[百度] 保存百度指数失败 drama_id={drama_id}: {e}")

            # 针对在播剧，补充采集百度指数
            supplement_saved = self._crawl_drama_baidu_index()
            saved_count += supplement_saved

            self.log_task('baidu_social', 'success', saved_count)
            logger.info(
                f"[百度] 采集完成，共{len(results)}条热搜数据，"
                f"成功匹配并保存{saved_count}条"
            )

        except Exception as e:
            logger.error(f"[百度] 采集异常: {e}")
            self.log_task('baidu_social', 'failed', error_message=str(e))

        return results

    def _crawl_hot_search(self):
        """采集百度实时热搜榜"""
        url = 'https://top.baidu.com/api/board?platform=wise&tab=realtime'
        data = self.fetch_json(url)

        items = []
        if not data or data.get('success') is not True:
            return items

        try:
            cards = data.get('data', {}).get('cards', [])
            for card in cards:
                content_list = card.get('content', [])
                for i, item in enumerate(content_list[:50]):
                    word = item.get('word', '')
                    hot_score = item.get('hotScore', 0)

                    items.append({
                        'keyword': word,
                        'heat_value': int(hot_score),
                        'rank': i + 1,
                        'platform': 'baidu',
                    })

        except Exception as e:
            logger.error(f"[百度] 解析热搜失败: {e}")

        return items

    def _crawl_drama_baidu_index(self):
        """针对在播剧集，通过百度热搜补充采集百度指数"""
        from app.utils.db import query

        saved_count = 0
        try:
            dramas = query(
                "SELECT id, title FROM dramas WHERE status = 'airing'"
            )
        except Exception as e:
            logger.error(f"[百度] 查询在播剧列表失败: {e}")
            return 0

        # 获取热搜数据用于匹配
        hot_data = self._crawl_hot_search()
        hot_map = {}
        for item in hot_data:
            keyword = item.get('keyword', '')
            heat = item.get('heat_value', 0)
            hot_map[keyword] = max(hot_map.get(keyword, 0), heat)

        for drama in dramas:
            title = drama['title']
            # 在热搜关键词中查找包含剧名的条目
            baidu_index = 0
            for keyword, heat in hot_map.items():
                if title in keyword or keyword in title:
                    baidu_index = max(baidu_index, heat)

            if baidu_index > 0:
                try:
                    self.save_social_data(
                        drama_id=drama['id'],
                        baidu_index=baidu_index,
                    )
                    saved_count += 1
                    logger.debug(
                        f"[百度] 百度指数保存成功: {title} "
                        f"指数={baidu_index}"
                    )
                except Exception as e:
                    logger.error(f"[百度] 百度指数保存失败 {title}: {e}")

        return saved_count
