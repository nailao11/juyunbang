from loguru import logger

from .base_crawler import BaseCrawler


class MgtvCrawler(BaseCrawler):
    """芒果TV热度采集器"""

    PLATFORM_ID = 4

    def __init__(self):
        super().__init__('芒果TV')

    def crawl(self):
        """采集芒果TV热播榜，匹配剧名并保存到数据库"""
        logger.info("[芒果TV] 开始采集热度数据...")
        results = []
        saved_count = 0

        try:
            data = self._crawl_rank()
            results.extend(data)

            # 匹配剧名并保存
            for item in results:
                drama_id = self._match_drama(item['title'])
                if drama_id:
                    try:
                        self.save_heat_data(
                            drama_id=drama_id,
                            platform_id=self.PLATFORM_ID,
                            heat_value=item['heat_value'],
                            heat_rank=item.get('rank'),
                        )
                        # 芒果TV的playcnt可作为播放量快照
                        if item.get('heat_value'):
                            self.save_playcount(
                                drama_id=drama_id,
                                platform_id=self.PLATFORM_ID,
                                total_playcount=item['heat_value'],
                            )
                        saved_count += 1
                        logger.debug(
                            f"[芒果TV] 保存成功: {item['title']} "
                            f"热度={item['heat_value']} 排名={item.get('rank')}"
                        )
                    except Exception as e:
                        logger.error(f"[芒果TV] 保存失败 {item['title']}: {e}")

            self.log_task('mgtv_heat', 'success', saved_count)
            logger.info(
                f"[芒果TV] 采集完成，共{len(results)}条数据，"
                f"成功匹配并保存{saved_count}条"
            )

        except Exception as e:
            logger.error(f"[芒果TV] 采集异常: {e}")
            self.log_task('mgtv_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self):
        """采集芒果TV排行"""
        url = 'https://pianku.api.mgtv.com/rider/list/pcweb/v3'
        params = {
            'allowedRC': '1',
            'platform': 'pcweb',
            'channelId': '2',  # 电视剧
            'pn': '1',
            'pc': '30',
            'hudong': '1',
            'orderType': 'c2'  # 按热度排序
        }

        data = self.fetch_json(url, params=params)
        if not data:
            return []

        items = []
        try:
            hit_list = data.get('data', {}).get('hitDocs', [])
            for i, item in enumerate(hit_list):
                title = item.get('title', '')
                heat = item.get('playcnt', 0)

                items.append({
                    'title': title,
                    'heat_value': heat,
                    'rank': i + 1,
                    'platform': 'mgtv'
                })

        except Exception as e:
            logger.error(f"[芒果TV] 解析排行失败: {e}")

        return items
