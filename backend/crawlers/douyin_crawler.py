import time
import random
from loguru import logger

from .base_crawler import BaseCrawler


class DouyinCrawler(BaseCrawler):
    """
    抖音数据采集器

    注意：抖音的Web API有签名保护（需要动态生成 X-Bogus / a_bogus 参数），
    直接请求大概率会被拒绝。本采集器采用以下策略：
    1. 尝试请求API，如果成功则正常解析
    2. 如果被拒绝（返回空数据或错误），记录日志并优雅跳过
    3. 抖音数据作为补充数据源，不影响核心排行功能

    后续可通过以下方式增强：
    - 使用开源的抖音签名库生成 X-Bogus 参数
    - 使用第三方数据接口
    """

    def __init__(self):
        super().__init__('抖音')

    def crawl(self):
        """采集抖音热搜榜相关数据"""
        logger.info("[抖音] 开始采集数据...")
        results = []
        saved_count = 0

        try:
            # 1. 采集抖音热搜（用于匹配剧名热度）
            data = self._crawl_hot()
            results.extend(data)

            # 2. 针对在播剧采集抖音话题播放量
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
        """
        采集抖音热搜。
        抖音热搜API有签名保护，可能返回空数据。
        """
        url = 'https://www.douyin.com/aweme/v1/web/hot/search/list/'
        headers = {
            'Referer': 'https://www.douyin.com/',
            'Accept': 'application/json',
        }

        data = self.fetch_json(url, headers=headers)

        # 检查是否被签名保护拦截
        if not data or data.get('status_code') != 0:
            logger.warning(
                "[抖音] 热搜API被拦截（需要签名参数），跳过热搜采集。"
                "这不影响核心功能，抖音数据为补充数据源。"
            )
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

            logger.info(f"[抖音] 成功获取{len(items)}条热搜数据")

        except Exception as e:
            logger.error(f"[抖音] 解析热搜失败: {e}")

        return items

    def _crawl_drama_topics(self):
        """
        针对在播剧集采集抖音话题的播放量。
        通过抖音搜索建议接口间接获取话题热度。
        """
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

            # 每个剧之间间隔一下
            time.sleep(random.uniform(2, 5))

        return saved_count

    def _crawl_topic_detail(self, topic_name):
        """
        采集特定话题的播放量。
        使用抖音搜索建议接口（相对稳定，不需要签名）。
        """
        # 尝试搜索建议接口
        suggest_url = 'https://www.douyin.com/aweme/v1/web/search/suggest/'
        params = {
            'keyword': topic_name,
            'source': 'video_search_page',
        }
        headers = {
            'Referer': f'https://www.douyin.com/search/{topic_name}',
        }

        data = self.fetch_json(suggest_url, params=params, headers=headers)
        if not data or data.get('status_code') != 0:
            return None

        try:
            # 从搜索建议中提取话题信息
            sug_list = data.get('data', []) or []
            for sug in sug_list:
                # 查找与剧名匹配的话题
                content = sug.get('content', '') or sug.get('word', '')
                if topic_name in content:
                    extra = sug.get('extra_info', {}) or {}
                    view_count = extra.get('vv', 0) or extra.get('view_count', 0)
                    if view_count:
                        return {
                            'topic': topic_name,
                            'view_count': int(view_count),
                        }
        except Exception as e:
            logger.error(f"[抖音] 解析话题{topic_name}失败: {e}")

        return None
