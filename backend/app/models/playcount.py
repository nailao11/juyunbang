from app.utils.db import query, query_one

class PlaycountModel:
    @staticmethod
    def get_daily_rank(stat_date=None, page=1, page_size=20):
        offset = (page - 1) * page_size
        if not stat_date:
            row = query_one("SELECT MAX(stat_date) as latest FROM playcount_daily WHERE published_at IS NOT NULL")
            stat_date = row['latest'] if row and row['latest'] else None
        if not stat_date:
            return [], 0, None

        items = query(
            "SELECT pd.drama_id, d.title, d.poster_url, d.douban_score, "
            "SUM(pd.daily_increment) as total_increment, MAX(pd.total_accumulated) as total_play "
            "FROM playcount_daily pd JOIN dramas d ON pd.drama_id = d.id "
            "WHERE pd.stat_date = %s "
            "GROUP BY pd.drama_id, d.title, d.poster_url, d.douban_score "
            "ORDER BY total_increment DESC LIMIT %s OFFSET %s",
            (stat_date, page_size, offset)
        )
        count = query_one(
            "SELECT COUNT(DISTINCT drama_id) as total FROM playcount_daily WHERE stat_date = %s",
            (stat_date,)
        )
        return items, count['total'] if count else 0, stat_date

    @staticmethod
    def get_weekly_rank(page=1, page_size=20):
        offset = (page - 1) * page_size
        row = query_one(
            "SELECT DATE_SUB(MAX(stat_date), INTERVAL WEEKDAY(MAX(stat_date)) DAY) as week_start "
            "FROM playcount_daily WHERE published_at IS NOT NULL"
        )
        if not row or not row['week_start']:
            return [], 0, None
        week_start = row['week_start']

        items = query(
            "SELECT pd.drama_id, d.title, d.poster_url, d.douban_score, "
            "SUM(pd.daily_increment) as week_total, MAX(pd.total_accumulated) as total_play, "
            "COUNT(DISTINCT pd.stat_date) as days "
            "FROM playcount_daily pd JOIN dramas d ON pd.drama_id = d.id "
            "WHERE pd.stat_date >= %s AND pd.stat_date < DATE_ADD(%s, INTERVAL 7 DAY) "
            "GROUP BY pd.drama_id, d.title, d.poster_url, d.douban_score "
            "ORDER BY week_total DESC LIMIT %s OFFSET %s",
            (week_start, week_start, page_size, offset)
        )
        return items, len(items), week_start

    @staticmethod
    def get_drama_play_history(drama_id, days=30):
        return query(
            "SELECT stat_date, SUM(daily_increment) as daily_total, MAX(total_accumulated) as accumulated "
            "FROM playcount_daily WHERE drama_id = %s "
            "AND stat_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
            "GROUP BY stat_date ORDER BY stat_date ASC",
            (drama_id, days)
        )
