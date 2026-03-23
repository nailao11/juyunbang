from loguru import logger

from .base_crawler import BaseCrawler


class TencentCrawler(BaseCrawler):
    """腾讯视频热度采集器"""

    PLATFORM_ID = 3

    def __init__(self):
        super().__init__('腾讯视频')

    def crawl(self):
        """采集腾讯视频热搜榜"""
        logger.info("[腾讯视频] 开始采集热度数据...")
        results = []

        try:
            tv_data = self._crawl_rank('tv')
            results.extend(tv_data)

            variety_data = self._crawl_rank('variety')
            results.extend(variety_data)

            self.log_task('tencent_heat', 'success', len(results))
            logger.info(f"[腾讯视频] 采集完成，共{len(results)}条数据")

        except Exception as e:
            logger.error(f"[腾讯视频] 采集异常: {e}")
            self.log_task('tencent_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, category='tv'):
        """采集腾讯视频排行"""
        url = 'https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/getPage'

        # 腾讯视频的H5接口
        params = {
            'video_appid': '3000010',
            'vplatform': '2',
        }

        # 使用页面采集方式
        page_url = 'https://v.qq.com/x/rank/'
        resp = self.fetch(page_url)
        if not resp:
            return []

        items = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'lxml')

            rank_items = soup.select('.rank_list_item, .rank-list-item')
            for i, item in enumerate(rank_items[:30]):
                title_el = item.select_one('.rank_name, .name, a')
                heat_el = item.select_one('.rank_hot, .hot, .heat')

                title = title_el.get_text(strip=True) if title_el else ''
                heat = heat_el.get_text(strip=True) if heat_el else '0'

                # 清理热度值
                heat = heat.replace(',', '').replace('万', '0000')
                try:
                    heat_value = float(heat)
                except ValueError:
                    heat_value = 0

                if title:
                    items.append({
                        'title': title,
                        'heat_value': heat_value,
                        'rank': i + 1,
                        'category': category,
                        'platform': 'tencent'
                    })

        except Exception as e:
            logger.error(f"[腾讯视频] 解析排行失败: {e}")

        return items
