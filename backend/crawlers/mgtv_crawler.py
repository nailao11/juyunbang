from loguru import logger

from .base_crawler import BaseCrawler


class MgtvCrawler(BaseCrawler):
    """芒果TV热度采集器"""

    PLATFORM_ID = 4

    def __init__(self):
        super().__init__('芒果TV')

    def crawl(self):
        """采集芒果TV热播榜"""
        logger.info("[芒果TV] 开始采集热度数据...")
        results = []
        saved_count = 0

        try:
            # 电视剧
            tv_data = self._crawl_rank(channel_id='2', category='tv_drama')
            results.extend(tv_data)

            # 综艺
            variety_data = self._crawl_rank(channel_id='3', category='variety')
            results.extend(variety_data)

            for item in results:
                drama_id = self._match_drama(
                    item['title'],
                    drama_type=item.get('category', 'tv_drama'),
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
                        logger.error(f"[芒果TV] 保存失败 {item['title']}: {e}")

            self.log_task('mgtv_heat', 'success', saved_count)
            logger.info(f"[芒果TV] 采集完成，共{len(results)}条，保存{saved_count}条")

        except Exception as e:
            logger.error(f"[芒果TV] 采集异常: {e}")
            self.log_task('mgtv_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, channel_id='2', category='tv_drama'):
        """采集芒果TV排行"""
        url = 'https://pianku.api.mgtv.com/rider/list/pcweb/v3'
        params = {
            'allowedRC': '1',
            'platform': 'pcweb',
            'channelId': channel_id,
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
                # 芒果TV封面: img字段，通常是相对路径，需加域名前缀
                img = item.get('img', '') or item.get('clipImg', '') or ''
                if img and not img.startswith('http'):
                    img = 'https://puui.qpic.cn/vcover_hz_pic/' + img if '/' in img else ''

                items.append({
                    'title': title,
                    'heat_value': heat,
                    'poster_url': img,
                    'rank': i + 1,
                    'category': category,
                    'platform': 'mgtv'
                })

        except Exception as e:
            logger.error(f"[芒果TV] 解析排行失败: {e}")

        return items
