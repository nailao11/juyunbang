"""
热剧榜 — 定时任务调度器（v2，2026-04 重构）

变更:
    - 移除了自动"发现新剧"的概念，热度采集改为读 drama_platforms 表
    - 新增"冷数据归档"任务：原始热度 > 90 天 → 聚合进 heat_daily 后删除
    - 保留所有计算/发布任务
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
    "/opt/rejubang/logs/scheduler_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="INFO",
    encoding="utf-8"
)


def job_crawl_heat():
    """每15分钟：根据 drama_platforms 表采集在播剧的热度"""
    logger.info("=== 开始热度数据采集任务 ===")
    try:
        from crawlers.airing_crawler import AiringCrawler
        total_saved = AiringCrawler().crawl()
        logger.info(f"=== 热度采集完成，本轮共保存 {total_saved} 条 ===")
    except Exception as e:
        logger.error(f"热度采集任务异常: {e}")
        import traceback
        traceback.print_exc()


def job_clean_data():
    """每日00:00：数据清洗（去除异常值和重复记录）"""
    logger.info("=== 开始数据清洗 ===")
    try:
        from processors.data_cleaner import DataCleaner
        DataCleaner().run()
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
        AnomalyDetector().run()
    except Exception as e:
        logger.error(f"异动检测异常: {e}")


def job_daily_publish():
    """每日15:00：发布日度数据"""
    logger.info("=== 开始发布日度数据 ===")
    try:
        from processors.daily_calculator import publish_daily_data
        publish_daily_data()
    except Exception as e:
        logger.error(f"日度数据发布异常: {e}")


def job_crawl_douban():
    """每日03:00：更新豆瓣评分"""
    logger.info("=== 开始豆瓣评分更新 ===")
    try:
        from crawlers.douban_crawler import DoubanCrawler
        DoubanCrawler().crawl()
    except Exception as e:
        logger.error(f"豆瓣评分更新异常: {e}")


def job_archive_old_heat():
    """
    每日04:00：归档冷数据（空间管理）
        - 原始 heat_realtime:   > 90 天的数据，已经被 heat_daily 聚合过，直接删除
        - 原始 playcount_snapshot: > 90 天的记录同样删除
        - heat_daily:           > 365 天的日聚合数据归档（可选），保留 1 年供小程序查询

    结果：
        - 热度原始数据本地最多保留 90 天（~32 MB）
        - 日聚合数据保留 365 天（~1.5 MB）
        - 无需依赖七牛云做冷备
    """
    logger.info("=== 开始冷数据归档/清理 ===")
    try:
        from app.utils.db import execute, query_one

        # 1. 先确认 heat_daily 是否已经覆盖到 90 天前
        lag = query_one("""
            SELECT COUNT(*) AS missing FROM heat_realtime h
            WHERE h.record_time < DATE_SUB(NOW(), INTERVAL 90 DAY)
              AND NOT EXISTS (
                SELECT 1 FROM heat_daily d
                WHERE d.drama_id = h.drama_id AND d.platform_id = h.platform_id
                  AND d.stat_date = DATE(h.record_time)
              )
        """)
        missing = (lag or {}).get('missing', 0)
        if missing:
            logger.warning(f"有 {missing} 条旧热度还未被 heat_daily 聚合，本次不清理，"
                           f"请检查 daily_calculator 是否正常")
            return

        # 2. 清理 90 天前的 heat_realtime
        deleted = execute(
            "DELETE FROM heat_realtime WHERE record_time < DATE_SUB(NOW(), INTERVAL 90 DAY)"
        )
        logger.info(f"清理了 {deleted} 条 90 天前的实时热度")

        # 3. 清理 90 天前的 playcount_snapshot
        deleted = execute(
            "DELETE FROM playcount_snapshot WHERE record_time < DATE_SUB(NOW(), INTERVAL 90 DAY)"
        )
        logger.info(f"清理了 {deleted} 条 90 天前的播放量快照")

        # 4. 清理超过 1 年的 heat_daily（小程序图表只展示 1 年窗口）
        deleted = execute(
            "DELETE FROM heat_daily WHERE stat_date < DATE_SUB(CURDATE(), INTERVAL 365 DAY)"
        )
        if deleted:
            logger.info(f"清理了 {deleted} 条 1 年前的日聚合数据")

    except Exception as e:
        logger.error(f"归档任务异常: {e}")


def main():
    scheduler = BlockingScheduler(timezone='Asia/Shanghai')

    scheduler.add_job(job_crawl_heat,
        IntervalTrigger(minutes=15),
        id='crawl_heat', name='热度数据采集', max_instances=1)

    scheduler.add_job(job_clean_data,
        CronTrigger(hour=0, minute=0),
        id='clean_data', name='数据清洗')

    scheduler.add_job(job_daily_calculate,
        CronTrigger(hour=0, minute=30),
        id='daily_calculate', name='日度统计计算')

    scheduler.add_job(job_index_calculate,
        CronTrigger(hour=1, minute=0),
        id='index_calculate', name='剧力指数计算')

    scheduler.add_job(job_detect_anomalies,
        CronTrigger(hour=1, minute=30),
        id='detect_anomalies', name='热度异动检测')

    scheduler.add_job(job_daily_publish,
        CronTrigger(hour=15, minute=0),
        id='daily_publish', name='日度数据发布')

    scheduler.add_job(job_crawl_douban,
        CronTrigger(hour=3, minute=0),
        id='crawl_douban', name='豆瓣评分更新')

    scheduler.add_job(job_archive_old_heat,
        CronTrigger(hour=4, minute=0),
        id='archive_old_heat', name='冷数据归档/清理')

    logger.info("热剧榜定时任务调度器已启动")
    logger.info(f"已注册 {len(scheduler.get_jobs())} 个定时任务：")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name} ({job.trigger})")

    # 启动时立即执行一次热度采集
    logger.info("=== 首次启动，立即执行热度采集 ===")
    job_crawl_heat()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("调度器已停止")


if __name__ == '__main__':
    main()
