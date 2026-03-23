from loguru import logger

from .base_crawler import BaseCrawler


class WeiboCrawler(BaseCrawler):
    """微博数据采集器"""

    def __init__(self):
        super().__init__('微博')

    def crawl(self):
        """采集微博相关数据"""
        logger.info("[微博] 开始采集数据...")
        results = []

        try:
            # 微博影视榜
            data = self._crawl_entertainment_rank()
            results.extend(data)

            self.log_task('weibo_social', 'success', len(results))
            logger.info(f"[微博] 采集完成，共{len(results)}条数据")

        except Exception as e:
            logger.error(f"[微博] 采集异常: {e}")
            self.log_task('weibo_social', 'failed', error_message=str(e))

        return results

    def _crawl_entertainment_rank(self):
        """采集微博影视榜"""
        url = 'https://weibo.com/ajax/side/hotSearch'
        data = self.fetch_json(url)

        items = []
        if not data or data.get('ok') != 1:
            return items

        try:
            hot_list = data.get('data', {}).get('realtime', [])
            for i, item in enumerate(hot_list[:50]):
                word = item.get('word', '')
                raw_hot = item.get('raw_hot', 0)

                items.append({
                    'keyword': word,
                    'heat_value': raw_hot,
                    'rank': i + 1,
                    'platform': 'weibo'
                })

        except Exception as e:
            logger.error(f"[微博] 解析热搜失败: {e}")

        return items

    def crawl_topic(self, topic_name):
        """采集特定话题的数据"""
        from bs4 import BeautifulSoup

        url = f'https://m.weibo.cn/api/container/getIndex'
        params = {
            'containerid': f'100103type=1&q=#{topic_name}#'
        }

        data = self.fetch_json(url, params=params)
        if not data:
            return None

        try:
            cards = data.get('data', {}).get('cards', [])
            for card in cards:
                if card.get('card_type') == 4:
                    desc = card.get('desc', '')
                    # 解析阅读量和讨论量
                    return {
                        'topic': topic_name,
                        'description': desc,
                        'raw_data': card
                    }
        except Exception as e:
            logger.error(f"[微博] 解析话题{topic_name}失败: {e}")

        return None
