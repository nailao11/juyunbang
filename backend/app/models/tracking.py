from app.utils.db import query, query_one, insert, execute
from datetime import datetime, date

class TrackingModel:
    @staticmethod
    def get_user_list(user_id, status=None):
        if status:
            return query(
                "SELECT ut.*, d.title, d.poster_url, d.total_episodes, d.status as drama_status, d.douban_score "
                "FROM user_tracking ut JOIN dramas d ON ut.drama_id = d.id "
                "WHERE ut.user_id = %s AND ut.status = %s ORDER BY ut.updated_at DESC",
                (user_id, status)
            )
        return query(
            "SELECT ut.*, d.title, d.poster_url, d.total_episodes, d.status as drama_status, d.douban_score "
            "FROM user_tracking ut JOIN dramas d ON ut.drama_id = d.id "
            "WHERE ut.user_id = %s ORDER BY ut.updated_at DESC",
            (user_id,)
        )

    @staticmethod
    def get_status(user_id, drama_id):
        return query_one(
            "SELECT * FROM user_tracking WHERE user_id = %s AND drama_id = %s",
            (user_id, drama_id)
        )

    @staticmethod
    def add_or_update(user_id, drama_id, status='watching', current_episode=0):
        existing = TrackingModel.get_status(user_id, drama_id)
        if existing:
            execute(
                "UPDATE user_tracking SET status = %s, current_episode = %s, updated_at = %s WHERE id = %s",
                (status, current_episode, datetime.now(), existing['id'])
            )
            return existing['id']
        return insert(
            "INSERT INTO user_tracking (user_id, drama_id, status, current_episode, started_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, drama_id, status, current_episode, date.today())
        )

    @staticmethod
    def remove(user_id, drama_id):
        execute("DELETE FROM user_tracking WHERE user_id = %s AND drama_id = %s", (user_id, drama_id))

    @staticmethod
    def get_stats(user_id):
        return query_one(
            "SELECT "
            "COUNT(*) as total, "
            "SUM(CASE WHEN status='watching' THEN 1 ELSE 0 END) as watching, "
            "SUM(CASE WHEN status='want_to_watch' THEN 1 ELSE 0 END) as want_to_watch, "
            "SUM(CASE WHEN status='watched' THEN 1 ELSE 0 END) as watched, "
            "SUM(CASE WHEN status='dropped' THEN 1 ELSE 0 END) as dropped "
            "FROM user_tracking WHERE user_id = %s",
            (user_id,)
        )
