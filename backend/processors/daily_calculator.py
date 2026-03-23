from datetime import datetime, timedelta
from loguru import logger

from app.utils.db import query, execute, insert


def calculate_daily_stats(stat_date=None):
    """计算日度统计数据"""
    if stat_date is None:
        stat_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    logger.info(f"开始计算 {stat_date} 日度统计数据...")

    # 1. 计算日度热度统计
    _calc_daily_heat(stat_date)

    # 2. 计算日播放量
    _calc_daily_playcount(stat_date)

    logger.info(f"{stat_date} 日度统计计算完成")


def _calc_daily_heat(stat_date):
    """从实时热度数据计算日度热度统计"""
    sql = """
        INSERT INTO heat_daily (drama_id, platform_id, stat_date, heat_avg, heat_max, heat_min, heat_latest, rank_avg, rank_best)
        SELECT
            drama_id, platform_id, DATE(record_time) as stat_date,
            AVG(heat_value) as heat_avg,
            MAX(heat_value) as heat_max,
            MIN(heat_value) as heat_min,
            (SELECT heat_value FROM heat_realtime hr2
             WHERE hr2.drama_id = hr.drama_id AND hr2.platform_id = hr.platform_id
             AND DATE(hr2.record_time) = %s
             ORDER BY hr2.record_time DESC LIMIT 1) as heat_latest,
            ROUND(AVG(heat_rank)) as rank_avg,
            MIN(heat_rank) as rank_best
        FROM heat_realtime hr
        WHERE DATE(record_time) = %s
        GROUP BY drama_id, platform_id
        ON DUPLICATE KEY UPDATE
            heat_avg = VALUES(heat_avg),
            heat_max = VALUES(heat_max),
            heat_min = VALUES(heat_min),
            heat_latest = VALUES(heat_latest),
            rank_avg = VALUES(rank_avg),
            rank_best = VALUES(rank_best)
    """
    execute(sql, (stat_date, stat_date))
    logger.info(f"热度日度统计完成: {stat_date}")


def _calc_daily_playcount(stat_date):
    """从播放量快照计算日播放量"""
    sql = """
        INSERT INTO playcount_daily (drama_id, platform_id, stat_date, daily_increment, total_accumulated, episode_latest, avg_per_episode)
        SELECT
            ps_today.drama_id,
            ps_today.platform_id,
            %s as stat_date,
            (ps_today.max_play - COALESCE(ps_yesterday.max_play, 0)) as daily_increment,
            ps_today.max_play as total_accumulated,
            d.current_episode as episode_latest,
            CASE WHEN d.current_episode > 0
                 THEN ROUND(ps_today.max_play / d.current_episode)
                 ELSE 0 END as avg_per_episode
        FROM (
            SELECT drama_id, platform_id, MAX(total_playcount) as max_play
            FROM playcount_snapshot
            WHERE DATE(record_time) = %s
            GROUP BY drama_id, platform_id
        ) ps_today
        LEFT JOIN (
            SELECT drama_id, platform_id, MAX(total_playcount) as max_play
            FROM playcount_snapshot
            WHERE DATE(record_time) = DATE_SUB(%s, INTERVAL 1 DAY)
            GROUP BY drama_id, platform_id
        ) ps_yesterday ON ps_today.drama_id = ps_yesterday.drama_id
            AND ps_today.platform_id = ps_yesterday.platform_id
        JOIN dramas d ON ps_today.drama_id = d.id
        ON DUPLICATE KEY UPDATE
            daily_increment = VALUES(daily_increment),
            total_accumulated = VALUES(total_accumulated),
            episode_latest = VALUES(episode_latest),
            avg_per_episode = VALUES(avg_per_episode)
    """
    execute(sql, (stat_date, stat_date, stat_date))
    logger.info(f"播放量日度统计完成: {stat_date}")


def publish_daily_data(stat_date=None):
    """发布日度数据（设置published_at时间）"""
    if stat_date is None:
        stat_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    now = datetime.now()

    execute(
        "UPDATE heat_daily SET published_at = %s WHERE stat_date = %s AND published_at IS NULL",
        (now, stat_date)
    )
    execute(
        "UPDATE playcount_daily SET published_at = %s WHERE stat_date = %s AND published_at IS NULL",
        (now, stat_date)
    )
    execute(
        "UPDATE drama_index_daily SET published_at = %s WHERE stat_date = %s AND published_at IS NULL",
        (now, stat_date)
    )

    logger.info(f"{stat_date} 数据已发布")
