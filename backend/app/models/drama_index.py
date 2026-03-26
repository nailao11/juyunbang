from app.utils.db import query, query_one

class DramaIndexModel:
    @staticmethod
    def get_daily_rank(stat_date=None, page=1, page_size=20):
        offset = (page - 1) * page_size
        if not stat_date:
            row = query_one("SELECT MAX(stat_date) as latest FROM drama_index_daily WHERE published_at IS NOT NULL")
            stat_date = row['latest'] if row and row['latest'] else None
        if not stat_date:
            return [], 0, None

        items = query(
            "SELECT did.*, d.title, d.poster_url, d.douban_score "
            "FROM drama_index_daily did JOIN dramas d ON did.drama_id = d.id "
            "WHERE did.stat_date = %s ORDER BY did.rank_total ASC LIMIT %s OFFSET %s",
            (stat_date, page_size, offset)
        )
        count = query_one(
            "SELECT COUNT(*) as total FROM drama_index_daily WHERE stat_date = %s",
            (stat_date,)
        )
        return items, count['total'] if count else 0, stat_date

    @staticmethod
    def get_weekly_rank(page=1, page_size=20):
        offset = (page - 1) * page_size
        row = query_one(
            "SELECT DATE_SUB(MAX(stat_date), INTERVAL WEEKDAY(MAX(stat_date)) DAY) as week_start "
            "FROM drama_index_daily WHERE published_at IS NOT NULL"
        )
        if not row or not row['week_start']:
            return [], 0, None
        week_start = row['week_start']

        items = query(
            "SELECT did.drama_id, d.title, d.poster_url, d.douban_score, "
            "AVG(did.index_total) as avg_index "
            "FROM drama_index_daily did JOIN dramas d ON did.drama_id = d.id "
            "WHERE did.stat_date >= %s AND did.stat_date < DATE_ADD(%s, INTERVAL 7 DAY) "
            "GROUP BY did.drama_id, d.title, d.poster_url, d.douban_score "
            "ORDER BY avg_index DESC LIMIT %s OFFSET %s",
            (week_start, week_start, page_size, offset)
        )
        return items, len(items), week_start

    @staticmethod
    def get_drama_index_history(drama_id, days=30):
        return query(
            "SELECT * FROM drama_index_daily WHERE drama_id = %s "
            "AND stat_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
            "ORDER BY stat_date ASC",
            (drama_id, days)
        )

    @staticmethod
    def get_latest_for_drama(drama_id):
        return query_one(
            "SELECT * FROM drama_index_daily WHERE drama_id = %s ORDER BY stat_date DESC LIMIT 1",
            (drama_id,)
        )
