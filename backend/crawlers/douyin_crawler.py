from loguru import logger

from .base_crawler import BaseCrawler


class DouyinCrawler(BaseCrawler):
    """抖音数据采集器"""

    def __init__(self):
        super().__init__('抖音')

    def crawl(self):
        """采集抖音热搜榜"""
        logger.info("[抖音] 开始采集数据...")
        results = []

        try:
            data = self._crawl_hot()
            results.extend(data)

            self.log_task('douyin_social', 'success', len(results))
            logger.info(f"[抖音] 采集完成，共{len(results)}条数据")

        except Exception as e:
            logger.error(f"[抖音] 采集异常: {e}")
            self.log_task('douyin_social', 'failed', error_message=str(e))

        return results

    def _crawl_hot(self):
        """采集抖音热搜"""
        url = 'https://www.douyin.com/aweme/v1/web/hot/search/list/'
        headers = {
            'Referer': 'https://www.douyin.com/',
        }

        data = self.fetch_json(url, headers=headers)
        if not data:
            return []

        items = []
        try:
            word_list = data.get('data', {}).get('word_list', [])
            for i, item in enumerate(word_list[:30]):
                word = item.get('word', '')
                hot_value = item.get('hot_value', 0)

                items.append({
                    'keyword': word,
                    'heat_value': hot_value,
                    'rank': i + 1,
                    'platform': 'douyin'
                })

        except Exception as e:
            logger.error(f"[抖音] 解析热搜失败: {e}")

        return items
