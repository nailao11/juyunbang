from app.utils.db import query, query_one

class HeatModel:
    @staticmethod
    def get_realtime_rank(platform_id=None, page=1, page_size=20):
        offset = (page - 1) * page_size
        where = "WHERE hr.platform_id = %s" if platform_id else ""
        params = [platform_id] if platform_id else []

        sql = (
            "SELECT hr.*, d.title, d.poster_url, d.status, d.douban_score, "
            "p.name as platform_name, p.short_name as platform_short, p.color as platform_color "
            "FROM heat_realtime hr "
            "JOIN dramas d ON hr.drama_id = d.id "
            "JOIN platforms p ON hr.platform_id = p.id "
            f"{where} "
            "ORDER BY hr.record_time DESC, hr.heat_value DESC "
            "LIMIT %s OFFSET %s"
        )
        params.extend([page_size, offset])
        return query(sql, tuple(params))

    @staticmethod
    def get_drama_realtime(drama_id, hours=24):
        return query(
            "SELECT hr.*, p.name as platform_name, p.short_name, p.color "
            "FROM heat_realtime hr JOIN platforms p ON hr.platform_id = p.id "
            "WHERE hr.drama_id = %s AND hr.record_time >= DATE_SUB(NOW(), INTERVAL %s HOUR) "
            "ORDER BY hr.record_time ASC",
            (drama_id, hours)
        )

    @staticmethod
    def get_daily_rank(stat_date=None, platform_id=None, page=1, page_size=20):
        offset = (page - 1) * page_size
        if not stat_date:
            row = query_one("SELECT MAX(stat_date) as latest FROM heat_daily WHERE published_at IS NOT NULL")
            stat_date = row['latest'] if row and row['latest'] else None
        if not stat_date:
            return [], 0, None

        conditions = ["hd.stat_date = %s"]
        params = [stat_date]
        if platform_id:
            conditions.append("hd.platform_id = %s")
            params.append(platform_id)

        where = " AND ".join(conditions)
        items = query(
            f"SELECT hd.*, d.title, d.poster_url, d.douban_score, "
            f"p.name as platform_name, p.short_name, p.color "
            f"FROM heat_daily hd "
            f"JOIN dramas d ON hd.drama_id = d.id "
            f"JOIN platforms p ON hd.platform_id = p.id "
            f"WHERE {where} "
            f"ORDER BY hd.heat_avg DESC LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset])
        )
        count = query_one(
            f"SELECT COUNT(*) as total FROM heat_daily hd WHERE {where}",
            tuple(params)
        )
        return items, count['total'] if count else 0, stat_date

    @staticmethod
    def get_drama_heat_history(drama_id, days=30):
        return query(
            "SELECT hd.*, p.name as platform_name, p.short_name, p.color "
            "FROM heat_daily hd JOIN platforms p ON hd.platform_id = p.id "
            "WHERE hd.drama_id = %s AND hd.stat_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
            "ORDER BY hd.stat_date ASC, p.sort_order ASC",
            (drama_id, days)
        )

    @staticmethod
    def get_available_dates(limit=90):
        return query(
            "SELECT DISTINCT stat_date FROM heat_daily WHERE published_at IS NOT NULL "
            "ORDER BY stat_date DESC LIMIT %s",
            (limit,)
        )
