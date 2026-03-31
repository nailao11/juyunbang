import time
import random
from loguru import logger

from .base_crawler import BaseCrawler


class DoubanCrawler(BaseCrawler):
    """
    豆瓣数据采集器 — 采集豆瓣评分

    注意：豆瓣反爬非常严格，本采集器采取以下策略：
    1. 使用轻量级JSON接口而非完整HTML页面
    2. 每次请求间隔较长（5-10秒），降低被封风险
    3. 单次采集数量有限，分多次完成
    4. 如果被封IP，采集器会自动跳过并记录日志
    """

    def __init__(self):
        super().__init__('豆瓣')
        # 豆瓣需要更像真实浏览器的请求头
        self.session.headers.update({
            'Host': 'movie.douban.com',
            'Referer': 'https://movie.douban.com/',
            'Accept': 'application/json, text/plain, */*',
        })

    def crawl(self):
        """采集豆瓣评分数据并更新到数据库"""
        logger.info("[豆瓣] 开始采集评分数据...")
        results = []

        try:
            from app.utils.db import query
            # 获取需要更新豆瓣评分的在播剧集
            dramas = query(
                "SELECT id, title, douban_id FROM dramas "
                "WHERE status = 'airing' AND douban_id IS NOT NULL "
                "ORDER BY RAND() LIMIT 10"  # 每次最多采10部，降低被封风险
            )

            if not dramas:
                logger.info("[豆瓣] 没有需要更新评分的在播剧集")
                self.log_task('douban_score', 'success', 0)
                return results

            for drama in dramas:
                score_data = self._crawl_score(drama['douban_id'])
                if score_data:
                    score_data['drama_id'] = drama['id']
                    score_data['title'] = drama['title']
                    results.append(score_data)

                # 豆瓣反爬严格，每次请求间隔长一些
                time.sleep(random.uniform(5, 10))

            # 更新评分到数据库
            if results:
                self._update_scores(results)

            self.log_task('douban_score', 'success', len(results))
            logger.info(f"[豆瓣] 采集完成，共{len(results)}条数据")

        except Exception as e:
            logger.error(f"[豆瓣] 采集异常: {e}")
            self.log_task('douban_score', 'failed', error_message=str(e))

        return results

    def _crawl_score(self, douban_id):
        """
        采集指定剧集的豆瓣评分。
        优先使用轻量级JSON接口，失败则尝试HTML页面。
        """
        # 方式1：轻量JSON接口（推荐，返回数据小，被封概率低）
        score_data = self._fetch_from_json_api(douban_id)
        if score_data:
            return score_data

        # 方式2：回退到HTML解析（数据更完整但更容易被封）
        logger.debug(f"[豆瓣] JSON接口无数据，尝试HTML方式: {douban_id}")
        return self._fetch_from_html(douban_id)

    def _fetch_from_json_api(self, douban_id):
        """使用豆瓣轻量级JSON接口获取评分"""
        url = f'https://movie.douban.com/j/subject_abstract?subject_id={douban_id}'

        data = self.fetch_json(url)
        if not data:
            return None

        try:
            subject = data.get('subject', {})
            if not subject:
                return None

            score_str = subject.get('rate', '')
            score = float(score_str) if score_str else None

            # 此接口不返回评分人数，设置为0表示未知
            return {
                'douban_id': douban_id,
                'score': score,
                'votes': 0,
            } if score else None

        except Exception as e:
            logger.error(f"[豆瓣] 解析JSON {douban_id} 失败: {e}")
            return None

    def _fetch_from_html(self, douban_id):
        """从豆瓣HTML页面解析评分（备用方式）"""
        from bs4 import BeautifulSoup

        url = f'https://movie.douban.com/subject/{douban_id}/'
        resp = self.fetch(url)
        if not resp:
            return None

        # 检查是否被反爬拦截
        if resp.status_code == 403 or '检测到有异常请求' in resp.text:
            logger.warning(f"[豆瓣] 被反爬拦截，跳过 {douban_id}")
            return None

        try:
            soup = BeautifulSoup(resp.text, 'lxml')

            score_el = soup.select_one('[property="v:average"]')
            score = float(score_el.get_text(strip=True)) if score_el else None

            votes_el = soup.select_one('[property="v:votes"]')
            votes = int(votes_el.get_text(strip=True)) if votes_el else 0

            if score is not None:
                logger.debug(f"[豆瓣] {douban_id}: 评分={score}, 人数={votes}")

            return {
                'douban_id': douban_id,
                'score': score,
                'votes': votes
            } if score else None

        except Exception as e:
            logger.error(f"[豆瓣] 解析HTML {douban_id} 失败: {e}")
            return None

    def _update_scores(self, results):
        """更新数据库中的豆瓣评分"""
        from app.utils.db import execute

        updated = 0
        for item in results:
            if item.get('score'):
                try:
                    if item['votes'] > 0:
                        execute(
                            "UPDATE dramas SET douban_score = %s, douban_votes = %s WHERE id = %s",
                            (item['score'], item['votes'], item['drama_id'])
                        )
                    else:
                        # JSON接口不返回投票数，只更新评分
                        execute(
                            "UPDATE dramas SET douban_score = %s WHERE id = %s",
                            (item['score'], item['drama_id'])
                        )
                    updated += 1
                    logger.info(f"[豆瓣] 更新 {item['title']} 评分: {item['score']}")
                except Exception as e:
                    logger.error(f"[豆瓣] 更新评分失败 {item['title']}: {e}")

        logger.info(f"[豆瓣] 共更新{updated}条评分数据")
