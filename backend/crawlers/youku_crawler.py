from loguru import logger

from .base_crawler import BaseCrawler


class YoukuCrawler(BaseCrawler):
    """优酷热度采集器"""

    PLATFORM_ID = 2

    def __init__(self):
        super().__init__('优酷')

    def crawl(self):
        """采集优酷热播榜，匹配剧名并保存到数据库"""
        logger.info("[优酷] 开始采集热度数据...")
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
                        saved_count += 1
                        logger.debug(
                            f"[优酷] 保存成功: {item['title']} "
                            f"热度={item['heat_value']} 排名={item.get('rank')}"
                        )
                    except Exception as e:
                        logger.error(f"[优酷] 保存失败 {item['title']}: {e}")

            self.log_task('youku_heat', 'success', saved_count)
            logger.info(
                f"[优酷] 采集完成，共{len(results)}条数据，"
                f"成功匹配并保存{saved_count}条"
            )

        except Exception as e:
            logger.error(f"[优酷] 采集异常: {e}")
            self.log_task('youku_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self):
        """采集优酷排行"""
        from bs4 import BeautifulSoup

        url = 'https://www.youku.com/rank'
        resp = self.fetch(url)
        if not resp:
            return []

        items = []
        try:
            soup = BeautifulSoup(resp.text, 'lxml')
            rank_items = soup.select('.rank-list .rank-item, .rk-list li')

            for i, item in enumerate(rank_items[:30]):
                title_el = item.select_one('.title, .name, a')
                heat_el = item.select_one('.heat, .hot, .num')

                title = title_el.get_text(strip=True) if title_el else ''
                heat = heat_el.get_text(strip=True) if heat_el else '0'

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
                        'platform': 'youku'
                    })

        except Exception as e:
            logger.error(f"[优酷] 解析排行失败: {e}")

        return items
