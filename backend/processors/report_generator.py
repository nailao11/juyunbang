from datetime import datetime, timedelta
from loguru import logger

from app.utils.db import query, query_one, execute


class ReportGenerator:
    """每日报告生成器：汇总当日数据生成日报"""

    def generate_daily_report(self, stat_date=None):
        """生成每日简报并保存到 daily_report 表"""
        if stat_date is None:
            stat_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        # 1. 热度最高的剧集
        top_heat = query_one(
            "SELECT hd.drama_id, d.title, hd.heat_avg "
            "FROM heat_daily hd "
            "JOIN dramas d ON hd.drama_id = d.id "
            "WHERE hd.stat_date = %s "
            "ORDER BY hd.heat_avg DESC LIMIT 1",
            (stat_date,)
        )

        # 2. 播放量最高的剧集
        top_play = query_one(
            "SELECT pd.drama_id, d.title, SUM(pd.daily_increment) as total_play "
            "FROM playcount_daily pd "
            "JOIN dramas d ON pd.drama_id = d.id "
            "WHERE pd.stat_date = %s "
            "GROUP BY pd.drama_id, d.title "
            "ORDER BY total_play DESC LIMIT 1",
            (stat_date,)
        )

        # 3. 涨幅最大的剧集（基于剧力指数排名变化）
        biggest_riser = query_one(
            "SELECT did.drama_id, d.title, did.rank_change, did.index_total "
            "FROM drama_index_daily did "
            "JOIN dramas d ON did.drama_id = d.id "
            "WHERE did.stat_date = %s AND did.rank_change > 0 "
            "ORDER BY did.rank_change DESC LIMIT 1",
            (stat_date,)
        )

        # 4. 当日追踪剧集总数
        count_row = query_one(
            "SELECT COUNT(DISTINCT drama_id) as total "
            "FROM heat_daily WHERE stat_date = %s",
            (stat_date,)
        )
        total_dramas = count_row['total'] if count_row else 0

        # 构建报告摘要
        top_heat_title = top_heat['title'] if top_heat else '无'
        top_heat_value = round(float(top_heat['heat_avg']), 2) if top_heat else 0

        top_play_title = top_play['title'] if top_play else '无'
        top_play_value = int(top_play['total_play']) if top_play else 0

        riser_title = biggest_riser['title'] if biggest_riser else '无'
        riser_change = int(biggest_riser['rank_change']) if biggest_riser and biggest_riser['rank_change'] is not None else 0

        summary = (
            f"热度冠军: {top_heat_title}({top_heat_value}); "
            f"播放冠军: {top_play_title}({top_play_value}); "
            f"最大黑马: {riser_title}(排名上升{riser_change}位); "
            f"追踪剧集: {total_dramas}部"
        )

        # 写入 daily_report 表
        sql = """
            INSERT INTO daily_report (
                stat_date, top_heat_drama_id, top_heat_title, top_heat_value,
                top_play_drama_id, top_play_title, top_play_value,
                biggest_riser_drama_id, biggest_riser_title, biggest_riser_change,
                total_dramas, summary, generated_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                top_heat_drama_id = VALUES(top_heat_drama_id),
                top_heat_title = VALUES(top_heat_title),
                top_heat_value = VALUES(top_heat_value),
                top_play_drama_id = VALUES(top_play_drama_id),
                top_play_title = VALUES(top_play_title),
                top_play_value = VALUES(top_play_value),
                biggest_riser_drama_id = VALUES(biggest_riser_drama_id),
                biggest_riser_title = VALUES(biggest_riser_title),
                biggest_riser_change = VALUES(biggest_riser_change),
                total_dramas = VALUES(total_dramas),
                summary = VALUES(summary),
                generated_at = VALUES(generated_at)
        """
        execute(sql, (
            stat_date,
            top_heat['drama_id'] if top_heat else None,
            top_heat_title, top_heat_value,
            top_play['drama_id'] if top_play else None,
            top_play_title, top_play_value,
            biggest_riser['drama_id'] if biggest_riser else None,
            riser_title, riser_change,
            total_dramas, summary, datetime.now()
        ))

        logger.info(f"{stat_date} 日报生成完成: {summary}")
        return summary

    def run(self, stat_date=None):
        """执行日报生成"""
        logger.info("开始生成每日报告...")

        summary = self.generate_daily_report(stat_date)

        logger.info("每日报告生成完成")
        return summary
