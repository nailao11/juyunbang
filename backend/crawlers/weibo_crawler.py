from loguru import logger

from .base_crawler import BaseCrawler


class WeiboCrawler(BaseCrawler):
    """微博数据采集器 - 社交媒体类，保存到 social_daily"""

    def __init__(self):
        super().__init__('微博')

    def crawl(self):
        """采集微博热搜数据，匹配剧名并保存到 social_daily"""
        logger.info("[微博] 开始采集数据...")
        results = []
        saved_count = 0

        try:
            # 微博热搜榜
            data = self._crawl_entertainment_rank()
            results.extend(data)

            # 统计每个剧的上热搜次数
            drama_hot_count = {}
            for item in results:
                keyword = item.get('keyword', '')
                drama_id = self._match_drama(keyword)
                if drama_id:
                    drama_hot_count[drama_id] = drama_hot_count.get(drama_id, 0) + 1

            # 保存热搜次数到 social_daily
            for drama_id, count in drama_hot_count.items():
                try:
                    self.save_social_data(
                        drama_id=drama_id,
                        weibo_hot_search_count=count,
                    )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"[微博] 保存热搜次数失败 drama_id={drama_id}: {e}")

            # 针对在播剧，采集话题数据
            topic_saved = self._crawl_drama_topics()
            saved_count += topic_saved

            self.log_task('weibo_social', 'success', saved_count)
            logger.info(
                f"[微博] 采集完成，共{len(results)}条热搜数据，"
                f"成功匹配并保存{saved_count}条"
            )

        except Exception as e:
            logger.error(f"[微博] 采集异常: {e}")
            self.log_task('weibo_social', 'failed', error_message=str(e))

        return results

    def _crawl_entertainment_rank(self):
        """采集微博热搜榜"""
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

    def _crawl_drama_topics(self):
        """针对在播剧集采集微博话题的阅读量和讨论量"""
        from app.utils.db import query

        saved_count = 0
        try:
            dramas = query(
                "SELECT id, title FROM dramas WHERE status = 'airing'"
            )
        except Exception as e:
            logger.error(f"[微博] 查询在播剧列表失败: {e}")
            return 0

        for drama in dramas:
            topic_data = self.crawl_topic(drama['title'])
            if topic_data and topic_data.get('read_count'):
                try:
                    self.save_social_data(
                        drama_id=drama['id'],
                        weibo_topic_read_incr=topic_data['read_count'],
                        weibo_topic_discuss_incr=topic_data.get('discuss_count', 0),
                    )
                    saved_count += 1
                    logger.debug(
                        f"[微博] 话题保存成功: {drama['title']} "
                        f"阅读={topic_data.get('read_count')} "
                        f"讨论={topic_data.get('discuss_count')}"
                    )
                except Exception as e:
                    logger.error(f"[微博] 话题保存失败 {drama['title']}: {e}")

        return saved_count

    def crawl_topic(self, topic_name):
        """采集特定话题的阅读量和讨论量"""
        url = 'https://m.weibo.cn/api/container/getIndex'
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
                    read_count = self._parse_chinese_number(desc, '阅读')
                    discuss_count = self._parse_chinese_number(desc, '讨论')
                    return {
                        'topic': topic_name,
                        'read_count': read_count,
                        'discuss_count': discuss_count,
                    }
        except Exception as e:
            logger.error(f"[微博] 解析话题{topic_name}失败: {e}")

        return None

    @staticmethod
    def _parse_chinese_number(text, prefix):
        """解析中文数字表达，如 '阅读 1.2亿' -> 120000000"""
        import re

        pattern = rf'{prefix}\s*([\d.]+)\s*(亿|万)?'
        match = re.search(pattern, text)
        if not match:
            return 0

        num = float(match.group(1))
        unit = match.group(2)
        if unit == '亿':
            num *= 100000000
        elif unit == '万':
            num *= 10000
        return int(num)
