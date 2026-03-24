from loguru import logger

from .base_crawler import BaseCrawler


class DouyinCrawler(BaseCrawler):
    """抖音数据采集器 - 社交媒体类，保存到 social_daily"""

    def __init__(self):
        super().__init__('抖音')

    def crawl(self):
        """采集抖音热搜榜，匹配剧名并保存到 social_daily"""
        logger.info("[抖音] 开始采集数据...")
        results = []
        saved_count = 0

        try:
            data = self._crawl_hot()
            results.extend(data)

            # 针对在播剧采集抖音话题播放量
            topic_saved = self._crawl_drama_topics()
            saved_count += topic_saved

            self.log_task('douyin_social', 'success', saved_count)
            logger.info(
                f"[抖音] 采集完成，共{len(results)}条热搜数据，"
                f"成功保存{saved_count}条话题数据"
            )

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

    def _crawl_drama_topics(self):
        """针对在播剧集采集抖音话题的播放量"""
        from app.utils.db import query

        saved_count = 0
        try:
            dramas = query(
                "SELECT id, title FROM dramas WHERE status = 'airing'"
            )
        except Exception as e:
            logger.error(f"[抖音] 查询在播剧列表失败: {e}")
            return 0

        for drama in dramas:
            topic_data = self._crawl_topic_detail(drama['title'])
            if topic_data and topic_data.get('view_count'):
                try:
                    self.save_social_data(
                        drama_id=drama['id'],
                        douyin_topic_views_incr=topic_data['view_count'],
                    )
                    saved_count += 1
                    logger.debug(
                        f"[抖音] 话题保存成功: {drama['title']} "
                        f"播放量={topic_data['view_count']}"
                    )
                except Exception as e:
                    logger.error(f"[抖音] 话题保存失败 {drama['title']}: {e}")

        return saved_count

    def _crawl_topic_detail(self, topic_name):
        """采集特定话题的播放量"""
        url = 'https://www.douyin.com/aweme/v1/web/challenge/detail/'
        params = {
            'keyword': topic_name,
        }
        headers = {
            'Referer': 'https://www.douyin.com/',
        }

        data = self.fetch_json(url, params=params, headers=headers)
        if not data:
            return None

        try:
            ch_info = data.get('ch_info', {}) or data.get('data', {})
            view_count = ch_info.get('view_count', 0) or ch_info.get('vv', 0)
            return {
                'topic': topic_name,
                'view_count': view_count,
            }
        except Exception as e:
            logger.error(f"[抖音] 解析话题{topic_name}失败: {e}")
            return None
