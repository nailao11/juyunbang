from app.utils.db import query, query_one, insert, execute
from datetime import datetime

class NoteModel:
    @staticmethod
    def get_user_notes(user_id, page=1, page_size=20):
        offset = (page - 1) * page_size
        items = query(
            "SELECT n.*, d.title as drama_title, d.poster_url "
            "FROM user_notes n LEFT JOIN dramas d ON n.drama_id = d.id "
            "WHERE n.user_id = %s ORDER BY n.updated_at DESC LIMIT %s OFFSET %s",
            (user_id, page_size, offset)
        )
        count = query_one("SELECT COUNT(*) as total FROM user_notes WHERE user_id = %s", (user_id,))
        return items, count['total'] if count else 0

    @staticmethod
    def get_drama_notes(user_id, drama_id):
        return query(
            "SELECT * FROM user_notes WHERE user_id = %s AND drama_id = %s ORDER BY created_at DESC",
            (user_id, drama_id)
        )

    @staticmethod
    def create(user_id, drama_id, content, episode_number=None, is_private=1):
        return insert(
            "INSERT INTO user_notes (user_id, drama_id, episode_number, content, is_private) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, drama_id, episode_number, content, is_private)
        )

    @staticmethod
    def update(note_id, user_id, content):
        execute(
            "UPDATE user_notes SET content = %s, updated_at = %s WHERE id = %s AND user_id = %s",
            (content, datetime.now(), note_id, user_id)
        )

    @staticmethod
    def delete(note_id, user_id):
        execute("DELETE FROM user_notes WHERE id = %s AND user_id = %s", (note_id, user_id))
