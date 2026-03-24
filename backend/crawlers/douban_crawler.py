from bs4 import BeautifulSoup
from loguru import logger

from .base_crawler import BaseCrawler


class DoubanCrawler(BaseCrawler):
    """豆瓣数据采集器"""

    def __init__(self):
        super().__init__('豆瓣')

    def crawl(self):
        """采集豆瓣评分数据并更新到数据库"""
        logger.info("[豆瓣] 开始采集评分数据...")
        results = []

        try:
            from app.utils.db import query
            # 获取需要更新豆瓣评分的在播剧集
            dramas = query(
                "SELECT id, title, douban_id FROM dramas "
                "WHERE status = 'airing' AND douban_id IS NOT NULL"
            )

            for drama in dramas:
                score_data = self._crawl_score(drama['douban_id'])
                if score_data:
                    score_data['drama_id'] = drama['id']
                    score_data['title'] = drama['title']
                    results.append(score_data)

            # 采集完成后立即更新评分到数据库
            if results:
                self.update_scores(results)

            self.log_task('douban_score', 'success', len(results))
            logger.info(f"[豆瓣] 采集完成，共{len(results)}条数据")

        except Exception as e:
            logger.error(f"[豆瓣] 采集异常: {e}")
            self.log_task('douban_score', 'failed', error_message=str(e))

        return results

    def _crawl_score(self, douban_id):
        """采集指定剧集的豆瓣评分"""
        url = f'https://movie.douban.com/subject/{douban_id}/'
        resp = self.fetch(url)
        if not resp:
            return None

        try:
            soup = BeautifulSoup(resp.text, 'lxml')

            # 评分
            score_el = soup.select_one('[property="v:average"]')
            score = float(score_el.get_text(strip=True)) if score_el else None

            # 评分人数
            votes_el = soup.select_one('[property="v:votes"]')
            votes = int(votes_el.get_text(strip=True)) if votes_el else 0

            if score is not None:
                logger.debug(f"[豆瓣] {douban_id}: 评分={score}, 人数={votes}")

            return {
                'douban_id': douban_id,
                'score': score,
                'votes': votes
            }

        except Exception as e:
            logger.error(f"[豆瓣] 解析{douban_id}评分失败: {e}")
            return None

    def update_scores(self, results):
        """更新数据库中的豆瓣评分"""
        from app.utils.db import execute

        updated = 0
        for item in results:
            if item.get('score'):
                try:
                    execute(
                        "UPDATE dramas SET douban_score = %s, douban_votes = %s WHERE id = %s",
                        (item['score'], item['votes'], item['drama_id'])
                    )
                    updated += 1
                    logger.info(f"[豆瓣] 更新 {item['title']} 评分: {item['score']}")
                except Exception as e:
                    logger.error(f"[豆瓣] 更新评分失败 {item['title']}: {e}")

        logger.info(f"[豆瓣] 共更新{updated}条评分数据")
