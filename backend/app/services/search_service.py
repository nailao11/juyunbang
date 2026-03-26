"""搜索与发现业务逻辑"""
from app.utils.cache import cache_get, cache_set


class SearchService:
    @staticmethod
    def search(keyword, page=1, page_size=20):
        """全文搜索剧集"""
        from app.models.drama import DramaModel
        items, total = DramaModel.search_by_title(keyword, page, page_size)
        return {'items': items, 'total': total, 'page': page}

    @staticmethod
    def get_hot_keywords():
        """获取热门搜索词"""
        cache_key = "search:hot_keywords"
        cached = cache_get(cache_key)
        if cached:
            return cached

        from app.utils.db import query
        rows = query(
            "SELECT title FROM dramas WHERE status = 'airing' "
            "ORDER BY douban_score DESC LIMIT 10"
        )
        keywords = [r['title'] for r in rows] if rows else []
        cache_set(cache_key, keywords, 3600)
        return keywords

    @staticmethod
    def get_suggest(keyword, limit=8):
        """搜索建议"""
        from app.utils.db import query
        return query(
            "SELECT id, title, poster_url FROM dramas WHERE title LIKE %s LIMIT %s",
            (f'%{keyword}%', limit)
        )

    @staticmethod
    def discover_by_genre(genre, page=1, page_size=20):
        """按题材发现"""
        from app.models.drama import DramaModel
        items, total = DramaModel.get_by_genre(genre, page, page_size)
        return {'items': items, 'total': total}

    @staticmethod
    def get_all_genres():
        """获取所有题材"""
        cache_key = "discover:genres"
        cached = cache_get(cache_key)
        if cached:
            return cached

        from app.models.drama import DramaModel
        rows = DramaModel.get_all_genres()
        genres = list({g.strip() for r in rows if r.get('genre') for g in r['genre'].split(',')})
        cache_set(cache_key, genres, 86400)
        return genres

    @staticmethod
    def get_upcoming():
        """获取待播剧集"""
        from app.models.drama import DramaModel
        return DramaModel.get_upcoming()

    @staticmethod
    def get_high_rated():
        """获取高分剧集"""
        from app.models.drama import DramaModel
        return DramaModel.get_high_rated()
