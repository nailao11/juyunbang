from app.utils.db import query, query_one, execute

class DramaModel:
    @staticmethod
    def get_by_id(drama_id):
        return query_one("SELECT * FROM dramas WHERE id = %s", (drama_id,))

    @staticmethod
    def get_by_status(status, limit=50):
        return query("SELECT * FROM dramas WHERE status = %s ORDER BY air_date DESC LIMIT %s", (status, limit))

    @staticmethod
    def search_by_title(keyword, page=1, page_size=20):
        offset = (page - 1) * page_size
        items = query(
            "SELECT * FROM dramas WHERE title LIKE %s ORDER BY douban_score DESC LIMIT %s OFFSET %s",
            (f'%{keyword}%', page_size, offset)
        )
        count = query_one("SELECT COUNT(*) as total FROM dramas WHERE title LIKE %s", (f'%{keyword}%',))
        return items, count['total'] if count else 0

    @staticmethod
    def get_by_genre(genre, page=1, page_size=20):
        offset = (page - 1) * page_size
        items = query(
            "SELECT * FROM dramas WHERE genre LIKE %s ORDER BY air_date DESC LIMIT %s OFFSET %s",
            (f'%{genre}%', page_size, offset)
        )
        count = query_one("SELECT COUNT(*) as total FROM dramas WHERE genre LIKE %s", (f'%{genre}%',))
        return items, count['total'] if count else 0

    @staticmethod
    def get_upcoming():
        return query(
            "SELECT * FROM dramas WHERE status = 'upcoming' AND air_date >= CURDATE() ORDER BY air_date ASC LIMIT 20"
        )

    @staticmethod
    def get_high_rated(min_score=8.0, min_votes=1000):
        return query(
            "SELECT * FROM dramas WHERE douban_score >= %s AND douban_votes >= %s ORDER BY douban_score DESC LIMIT 30",
            (min_score, min_votes)
        )

    @staticmethod
    def get_all_genres():
        return query("SELECT DISTINCT genre FROM dramas WHERE genre IS NOT NULL AND genre != ''")

    @staticmethod
    def get_related(drama_id, limit=6):
        drama = query_one("SELECT type, genre, region FROM dramas WHERE id = %s", (drama_id,))
        if not drama:
            return []
        return query(
            "SELECT id, title, poster_url, douban_score, status FROM dramas "
            "WHERE id != %s AND (type = %s OR genre LIKE %s) AND status = 'airing' "
            "ORDER BY douban_score DESC LIMIT %s",
            (drama_id, drama['type'], f"%{drama.get('genre', '').split(',')[0] if drama.get('genre') else ''}%", limit)
        )
