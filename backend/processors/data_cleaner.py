from datetime import datetime
from loguru import logger

from app.utils.db import query, execute


class DataCleaner:
    """数据清洗处理器：清除异常值和重复记录"""

    def clean_heat_data(self):
        """清除今日热度异常值（超过3个标准差的记录）"""
        today = datetime.now().strftime('%Y-%m-%d')

        # 计算每个 drama_id+platform_id 组合的均值和标准差
        stats = query(
            "SELECT drama_id, platform_id, AVG(heat_value) as mean_val, "
            "STDDEV(heat_value) as std_val "
            "FROM heat_realtime "
            "WHERE DATE(record_time) = %s "
            "GROUP BY drama_id, platform_id "
            "HAVING STDDEV(heat_value) > 0",
            (today,)
        )

        total_removed = 0
        for s in stats:
            mean_val = float(s['mean_val'])
            std_val = float(s['std_val'])
            upper_bound = mean_val + 3 * std_val
            lower_bound = mean_val - 3 * std_val

            affected = execute(
                "DELETE FROM heat_realtime "
                "WHERE drama_id = %s AND platform_id = %s "
                "AND DATE(record_time) = %s "
                "AND (heat_value > %s OR heat_value < %s)",
                (s['drama_id'], s['platform_id'], today, upper_bound, lower_bound)
            )
            total_removed += affected

        logger.info(f"热度异常值清洗完成: 共删除 {total_removed} 条异常记录")
        return total_removed

    def clean_duplicate_records(self):
        """清除今日5分钟内相同 drama_id+platform_id 的重复记录"""
        today = datetime.now().strftime('%Y-%m-%d')

        # 找出5分钟内重复的记录（保留每组最早的一条）
        duplicates = query(
            "SELECT hr1.id "
            "FROM heat_realtime hr1 "
            "INNER JOIN heat_realtime hr2 "
            "  ON hr1.drama_id = hr2.drama_id "
            "  AND hr1.platform_id = hr2.platform_id "
            "  AND hr1.id > hr2.id "
            "  AND ABS(TIMESTAMPDIFF(SECOND, hr1.record_time, hr2.record_time)) < 300 "
            "WHERE DATE(hr1.record_time) = %s",
            (today,)
        )

        total_removed = 0
        if duplicates:
            dup_ids = [d['id'] for d in duplicates]
            # 分批删除，避免单次操作过大
            batch_size = 500
            for i in range(0, len(dup_ids), batch_size):
                batch = dup_ids[i:i + batch_size]
                placeholders = ','.join(['%s'] * len(batch))
                affected = execute(
                    f"DELETE FROM heat_realtime WHERE id IN ({placeholders})",
                    tuple(batch)
                )
                total_removed += affected

        logger.info(f"重复记录清洗完成: 共删除 {total_removed} 条重复记录")
        return total_removed

    def run(self):
        """执行所有数据清洗任务"""
        logger.info("开始执行数据清洗...")

        outliers_removed = self.clean_heat_data()
        duplicates_removed = self.clean_duplicate_records()

        logger.info(
            f"数据清洗完成: 异常值 {outliers_removed} 条, "
            f"重复记录 {duplicates_removed} 条"
        )
