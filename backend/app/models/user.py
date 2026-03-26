from app.utils.db import query_one, insert, execute
from datetime import datetime

class UserModel:
    @staticmethod
    def get_by_id(user_id):
        return query_one("SELECT * FROM users WHERE id = %s", (user_id,))

    @staticmethod
    def get_by_openid(openid):
        return query_one("SELECT * FROM users WHERE openid = %s", (openid,))

    @staticmethod
    def create(openid, nickname=None, avatar_url=None):
        user_id = insert(
            "INSERT INTO users (openid, nickname, avatar_url, last_login_at) VALUES (%s, %s, %s, %s)",
            (openid, nickname, avatar_url, datetime.now())
        )
        return user_id

    @staticmethod
    def update_login_time(user_id):
        execute("UPDATE users SET last_login_at = %s WHERE id = %s", (datetime.now(), user_id))

    @staticmethod
    def update_profile(user_id, **kwargs):
        if not kwargs:
            return
        allowed = {'nickname', 'avatar_url', 'gender', 'theme_mode', 'notify_enabled'}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_parts = [f"{k} = %s" for k in fields]
        values = list(fields.values()) + [user_id]
        execute(f"UPDATE users SET {', '.join(set_parts)} WHERE id = %s", tuple(values))
