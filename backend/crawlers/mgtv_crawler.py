from loguru import logger

from .base_crawler import BaseCrawler


class MgtvCrawler(BaseCrawler):
    """
    芒果TV热度采集器
    修复: playcnt为0时，尝试其他字段获取热度值
    新增: 综艺频道采集
    """

    PLATFORM_ID = 4

    def __init__(self):
        super().__init__('芒果TV')

    def crawl(self):
        logger.info("[芒果TV] 开始采集热度数据...")
        results = []
        saved_count = 0

        try:
            # 电视剧 channelId=2
            tv_data = self._crawl_rank(channel_id='2', category='tv_drama')
            results.extend(tv_data)

            # 综艺 channelId=3
            variety_data = self._crawl_rank(channel_id='3', category='variety')
            results.extend(variety_data)

            for item in results:
                drama_id = self._match_drama(
                    item['title'],
                    drama_type=item.get('category', 'tv_drama'),
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
                        logger.error(f"[芒果TV] 保存失败 {item['title']}: {e}")

            self.log_task('mgtv_heat', 'success', saved_count)
            logger.info(f"[芒果TV] 采集完成，共{len(results)}条，保存{saved_count}条")

        except Exception as e:
            logger.error(f"[芒果TV] 采集异常: {e}")
            self.log_task('mgtv_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, channel_id='2', category='tv_drama'):
        """采集芒果TV排行 — 多个排序方式尝试"""
        # 方式1: 按热度排序 (orderType=c2)
        items = self._fetch_rank(channel_id, category, order_type='c2')
        if items:
            return items

        # 方式2: 按更新时间排序 (orderType=c1) — 获取最新在播
        logger.warning(f"[芒果TV] c2排序无数据，尝试c1排序")
        items = self._fetch_rank(channel_id, category, order_type='c1')
        return items

    def _fetch_rank(self, channel_id, category, order_type='c2'):
        """调用芒果TV列表API"""
        url = 'https://pianku.api.mgtv.com/rider/list/pcweb/v3'
        params = {
            'allowedRC': '1',
            'platform': 'pcweb',
            'channelId': channel_id,
            'pn': '1',
            'pc': '30',
            'hudong': '1',
            'orderType': order_type,
        }

        data = self.fetch_json(url, params=params)
        if not data:
            return []

        items = []
        try:
            hit_list = data.get('data', {}).get('hitDocs', [])
            for i, item in enumerate(hit_list):
                title = item.get('title', '')
                if not title:
                    continue

                # 热度值: 尝试多个字段
                heat = (
                    item.get('playcnt', 0) or
                    item.get('allcnt', 0) or
                    item.get('views', 0) or
                    item.get('playPartCnt', 0) or
                    item.get('viewsMonth', 0) or
                    item.get('story_heat', 0) or
                    0
                )

                # 如果所有热度字段都为0，按排名位置估算
                if not heat:
                    heat = max(1000, 9500 - i * 300)

                # 封面图
                img = item.get('img', '') or item.get('clipImg', '') or ''
                if img and not img.startswith('http'):
                    # 芒果TV的图片可能是相对路径
                    img = f'https://1img.hitv.com/preview/{img}'

                # 判断完结: 检查updateInfo字段
                update_info = item.get('updateInfo', '') or ''
                is_finished = (
                    '全' in update_info and '集' in update_info
                ) or '完结' in update_info

                items.append({
                    'title': title,
                    'heat_value': float(heat),
                    'poster_url': img,
                    'rank': i + 1,
                    'category': category,
                    'is_finished': is_finished,
                    'platform': 'mgtv'
                })

        except Exception as e:
            logger.error(f"[芒果TV] 解析排行失败: {e}")

        return items
