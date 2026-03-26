from app.utils.db import query, query_one

class SocialModel:
    @staticmethod
    def get_daily_rank(stat_date=None, sort_by='weibo', page=1, page_size=20):
        offset = (page - 1) * page_size
        if not stat_date:
            row = query_one("SELECT MAX(stat_date) as latest FROM social_daily")
            stat_date = row['latest'] if row and row['latest'] else None
        if not stat_date:
            return [], 0, None

        sort_map = {
            'weibo': 'IFNULL(sd.weibo_topic_read_incr, 0) + IFNULL(sd.weibo_hot_search_count, 0) * 1000000',
            'douyin': 'IFNULL(sd.douyin_topic_views_incr, 0)',
            'baidu': 'IFNULL(sd.baidu_index, 0)',
        }
        order_expr = sort_map.get(sort_by, sort_map['weibo'])

        items = query(
            f"SELECT sd.*, d.title, d.poster_url, d.douban_score "
            f"FROM social_daily sd JOIN dramas d ON sd.drama_id = d.id "
            f"WHERE sd.stat_date = %s ORDER BY ({order_expr}) DESC LIMIT %s OFFSET %s",
            (stat_date, page_size, offset)
        )
        count = query_one("SELECT COUNT(*) as total FROM social_daily WHERE stat_date = %s", (stat_date,))
        return items, count['total'] if count else 0, stat_date

    @staticmethod
    def get_drama_social_history(drama_id, days=30):
        return query(
            "SELECT * FROM social_daily WHERE drama_id = %s "
            "AND stat_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
            "ORDER BY stat_date ASC",
            (drama_id, days)
        )
