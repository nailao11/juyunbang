from app.utils.db import query, query_one, execute

class NewsModel:
    @staticmethod
    def get_list(category=None, page=1, page_size=20):
        offset = (page - 1) * page_size
        if category:
            items = query(
                "SELECT * FROM news WHERE is_published = 1 AND category = %s "
                "ORDER BY published_at DESC LIMIT %s OFFSET %s",
                (category, page_size, offset)
            )
            count = query_one(
                "SELECT COUNT(*) as total FROM news WHERE is_published = 1 AND category = %s",
                (category,)
            )
        else:
            items = query(
                "SELECT * FROM news WHERE is_published = 1 ORDER BY published_at DESC LIMIT %s OFFSET %s",
                (page_size, offset)
            )
            count = query_one("SELECT COUNT(*) as total FROM news WHERE is_published = 1")
        return items, count['total'] if count else 0

    @staticmethod
    def get_by_id(news_id):
        return query_one("SELECT * FROM news WHERE id = %s", (news_id,))

    @staticmethod
    def increment_view(news_id):
        execute("UPDATE news SET view_count = view_count + 1 WHERE id = %s", (news_id,))

    @staticmethod
    def get_latest_daily_report():
        return query_one(
            "SELECT * FROM daily_report ORDER BY stat_date DESC LIMIT 1"
        )

class FeedbackModel:
    @staticmethod
    def create(user_id, content, contact=None, feedback_type='suggestion'):
        from app.utils.db import insert
        return insert(
            "INSERT INTO feedback (user_id, content, contact, type) VALUES (%s, %s, %s, %s)",
            (user_id, content, contact, feedback_type)
        )
