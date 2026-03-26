from datetime import datetime
from loguru import logger

from app.utils.db import query


class AnomalyDetector:
    """异常检测器：检测热度异常飙升的剧集"""

    def detect_heat_anomalies(self):
        """检测今日热度较7日均值飙升200%以上的剧集"""
        today = datetime.now().strftime('%Y-%m-%d')

        sql = """
            SELECT
                d.id as drama_id,
                d.title,
                today_heat.current_heat,
                hist.avg_heat,
                ROUND((today_heat.current_heat - hist.avg_heat) / hist.avg_heat * 100, 2) as change_pct
            FROM dramas d
            INNER JOIN (
                SELECT drama_id, AVG(heat_value) as current_heat
                FROM heat_realtime
                WHERE DATE(record_time) = %s
                GROUP BY drama_id
            ) today_heat ON d.id = today_heat.drama_id
            INNER JOIN (
                SELECT drama_id, AVG(heat_avg) as avg_heat
                FROM heat_daily
                WHERE stat_date >= DATE_SUB(%s, INTERVAL 7 DAY)
                  AND stat_date < %s
                GROUP BY drama_id
                HAVING AVG(heat_avg) > 0
            ) hist ON d.id = hist.drama_id
            WHERE (today_heat.current_heat - hist.avg_heat) / hist.avg_heat >= 2.0
            ORDER BY change_pct DESC
        """
        rows = query(sql, (today, today, today))

        anomalies = []
        for row in rows:
            anomalies.append({
                'drama_id': row['drama_id'],
                'title': row['title'],
                'current_heat': float(row['current_heat']),
                'avg_heat': float(row['avg_heat']),
                'change_pct': float(row['change_pct']),
            })

        return anomalies

    def run(self):
        """执行异常检测"""
        logger.info("开始执行热度异常检测...")

        anomalies = self.detect_heat_anomalies()

        if anomalies:
            logger.warning(f"检测到 {len(anomalies)} 部剧集热度异常飙升:")
            for a in anomalies:
                logger.warning(
                    f"  {a['title']}(ID:{a['drama_id']}): "
                    f"当前热度 {a['current_heat']:.0f}, "
                    f"7日均值 {a['avg_heat']:.0f}, "
                    f"涨幅 {a['change_pct']:.1f}%"
                )
        else:
            logger.info("未检测到热度异常飙升的剧集")

        return anomalies
