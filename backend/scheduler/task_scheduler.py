"""
剧云榜 — 定时任务调度器
管理所有数据采集和计算任务的定时执行
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

# 配置日志
logger.add(
    "/opt/juyunbang/logs/scheduler_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="INFO",
    encoding="utf-8"
)


def job_crawl_heat():
    """每15分钟：采集各平台热度数据"""
    logger.info("=== 开始热度数据采集任务 ===")
    try:
        from crawlers.iqiyi_crawler import IqiyiCrawler
        from crawlers.bilibili_crawler import BilibiliCrawler
        from crawlers.youku_crawler import YoukuCrawler
        from crawlers.tencent_crawler import TencentCrawler
        from crawlers.mgtv_crawler import MgtvCrawler

        crawlers = [
            IqiyiCrawler(),
            BilibiliCrawler(),
            YoukuCrawler(),
            TencentCrawler(),
            MgtvCrawler(),
        ]

        for crawler in crawlers:
            try:
                crawler.crawl()
            except Exception as e:
                logger.error(f"{crawler.platform_name} 采集失败: {e}")

    except Exception as e:
        logger.error(f"热度采集任务异常: {e}")


def job_crawl_social():
    """每60分钟：采集社交媒体数据（微博/抖音/百度）"""
    logger.info("=== 开始社交媒体数据采集任务 ===")
    try:
        from crawlers.weibo_crawler import WeiboCrawler
        from crawlers.douyin_crawler import DouyinCrawler
        from crawlers.baidu_crawler import BaiduCrawler

        for CrawlerClass in [WeiboCrawler, DouyinCrawler, BaiduCrawler]:
            try:
                crawler = CrawlerClass()
                crawler.crawl()
            except Exception as e:
                logger.error(f"社交数据采集失败: {e}")

    except Exception as e:
        logger.error(f"社交采集任务异常: {e}")


def job_clean_data():
    """每日00:00：数据清洗（去除异常值和重复记录）"""
    logger.info("=== 开始数据清洗 ===")
    try:
        from processors.data_cleaner import DataCleaner
        cleaner = DataCleaner()
        cleaner.run()
    except Exception as e:
        logger.error(f"数据清洗异常: {e}")


def job_daily_calculate():
    """每日00:30：计算日度统计数据"""
    logger.info("=== 开始日度统计计算 ===")
    try:
        from processors.daily_calculator import calculate_daily_stats
        calculate_daily_stats()
    except Exception as e:
        logger.error(f"日度统计计算异常: {e}")


def job_index_calculate():
    """每日01:00：计算剧力指数"""
    logger.info("=== 开始剧力指数计算 ===")
    try:
        from processors.index_calculator import calculate_drama_index
        calculate_drama_index()
    except Exception as e:
        logger.error(f"剧力指数计算异常: {e}")


def job_detect_anomalies():
    """每日01:30：检测热度异动"""
    logger.info("=== 开始热度异动检测 ===")
    try:
        from processors.anomaly_detector import AnomalyDetector
        detector = AnomalyDetector()
        detector.run()
    except Exception as e:
        logger.error(f"异动检测异常: {e}")


def job_daily_publish():
    """每日15:00：发布日度数据并生成日报"""
    logger.info("=== 开始发布日度数据 ===")
    try:
        from processors.daily_calculator import publish_daily_data
        publish_daily_data()
    except Exception as e:
        logger.error(f"日度数据发布异常: {e}")

    logger.info("=== 开始生成每日简报 ===")
    try:
        from processors.report_generator import ReportGenerator
        generator = ReportGenerator()
        generator.run()
    except Exception as e:
        logger.error(f"日报生成异常: {e}")


def job_crawl_douban():
    """每日03:00：更新豆瓣评分"""
    logger.info("=== 开始豆瓣评分更新 ===")
    try:
        from crawlers.douban_crawler import DoubanCrawler
        crawler = DoubanCrawler()
        crawler.crawl()
    except Exception as e:
        logger.error(f"豆瓣评分更新异常: {e}")


def job_clean_old_data():
    """每日04:00：清理30天前的实时热度数据"""
    logger.info("=== 开始清理旧数据 ===")
    try:
        from app.utils.db import execute
        affected = execute(
            "DELETE FROM heat_realtime WHERE record_time < DATE_SUB(NOW(), INTERVAL 30 DAY)"
        )
        logger.info(f"清理了 {affected} 条过期实时热度数据")

        affected = execute(
            "DELETE FROM playcount_snapshot WHERE record_time < DATE_SUB(NOW(), INTERVAL 30 DAY)"
        )
        logger.info(f"清理了 {affected} 条过期播放量快照")

    except Exception as e:
        logger.error(f"旧数据清理异常: {e}")


def main():
    scheduler = BlockingScheduler(timezone='Asia/Shanghai')

    # 每15分钟：热度采集
    scheduler.add_job(
        job_crawl_heat,
        IntervalTrigger(minutes=15),
        id='crawl_heat',
        name='热度数据采集',
        max_instances=1
    )

    # 每60分钟：社交媒体采集
    scheduler.add_job(
        job_crawl_social,
        IntervalTrigger(minutes=60),
        id='crawl_social',
        name='社交媒体数据采集',
        max_instances=1
    )

    # 每日00:00：数据清洗
    scheduler.add_job(
        job_clean_data,
        CronTrigger(hour=0, minute=0),
        id='clean_data',
        name='数据清洗'
    )

    # 每日00:30：日度统计计算
    scheduler.add_job(
        job_daily_calculate,
        CronTrigger(hour=0, minute=30),
        id='daily_calculate',
        name='日度统计计算'
    )

    # 每日01:00：剧力指数计算
    scheduler.add_job(
        job_index_calculate,
        CronTrigger(hour=1, minute=0),
        id='index_calculate',
        name='剧力指数计算'
    )

    # 每日01:30：热度异动检测
    scheduler.add_job(
        job_detect_anomalies,
        CronTrigger(hour=1, minute=30),
        id='detect_anomalies',
        name='热度异动检测'
    )

    # 每日15:00：发布日度数据 + 生成日报
    scheduler.add_job(
        job_daily_publish,
        CronTrigger(hour=15, minute=0),
        id='daily_publish',
        name='日度数据发布与日报生成'
    )

    # 每日03:00：豆瓣评分更新
    scheduler.add_job(
        job_crawl_douban,
        CronTrigger(hour=3, minute=0),
        id='crawl_douban',
        name='豆瓣评分更新'
    )

    # 每日04:00：清理旧数据
    scheduler.add_job(
        job_clean_old_data,
        CronTrigger(hour=4, minute=0),
        id='clean_old_data',
        name='清理旧数据'
    )

    logger.info("剧云榜定时任务调度器已启动")
    logger.info(f"已注册 {len(scheduler.get_jobs())} 个定时任务：")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name} ({job.trigger})")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("调度器已停止")


if __name__ == '__main__':
    main()
