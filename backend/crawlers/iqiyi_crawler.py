from bs4 import BeautifulSoup
from loguru import logger

from .base_crawler import BaseCrawler


class IqiyiCrawler(BaseCrawler):
    """爱奇艺热度采集器"""

    PLATFORM_ID = 1  # 爱奇艺在platforms表中的ID

    def __init__(self):
        super().__init__('爱奇艺')

    def crawl(self):
        """采集爱奇艺风云榜热度数据"""
        logger.info("[爱奇艺] 开始采集热度数据...")
        results = []

        try:
            # 电视剧热度榜
            tv_data = self._crawl_rank('tv')
            results.extend(tv_data)

            # 综艺热度榜
            variety_data = self._crawl_rank('variety')
            results.extend(variety_data)

            self.log_task('iqiyi_heat', 'success', len(results))
            logger.info(f"[爱奇艺] 采集完成，共{len(results)}条数据")

        except Exception as e:
            logger.error(f"[爱奇艺] 采集异常: {e}")
            self.log_task('iqiyi_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, category='tv'):
        """采集指定分类的排行"""
        # 爱奇艺热播榜API接口
        url = 'https://mesh.if.iqiyi.com/portal/lw/videolib/data/rank'
        params = {
            'type': 'heat',
            'cid': '2' if category == 'tv' else '6',  # 2=电视剧, 6=综艺
            'limit': '30'
        }

        data = self.fetch_json(url, params=params)
        if not data:
            return []

        items = []
        try:
            rank_list = data.get('data', {}).get('list', [])
            for i, item in enumerate(rank_list):
                title = item.get('name', '')
                heat = item.get('hot', 0)
                rank = i + 1

                items.append({
                    'title': title,
                    'heat_value': heat,
                    'rank': rank,
                    'category': category,
                    'platform': 'iqiyi'
                })

                logger.debug(f"[爱奇艺] #{rank} {title}: {heat}")

        except Exception as e:
            logger.error(f"[爱奇艺] 解析{category}排行失败: {e}")

        return items


if __name__ == '__main__':
    crawler = IqiyiCrawler()
    results = crawler.crawl()
    for r in results:
        print(f"#{r['rank']} {r['title']}: {r['heat_value']}")
