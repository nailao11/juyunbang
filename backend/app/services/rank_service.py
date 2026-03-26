"""排行榜业务逻辑"""
from app.utils.cache import cache_get, cache_set


class RankService:
    CACHE_TTL = 600

    @staticmethod
    def get_play_rank(stat_date=None, page=1, page_size=20):
        """日播放量排行"""
        cache_key = f"rank:play:daily:{stat_date}:{page}:{page_size}"
        cached = cache_get(cache_key)
        if cached:
            return cached

        from app.models.playcount import PlaycountModel
        items, total, actual_date = PlaycountModel.get_daily_rank(stat_date, page, page_size)
        result = {'items': items, 'total': total, 'stat_date': str(actual_date) if actual_date else None}
        cache_set(cache_key, result, RankService.CACHE_TTL)
        return result

    @staticmethod
    def get_index_rank(stat_date=None, page=1, page_size=20):
        """剧力指数排行"""
        cache_key = f"rank:index:daily:{stat_date}:{page}:{page_size}"
        cached = cache_get(cache_key)
        if cached:
            return cached

        from app.models.drama_index import DramaIndexModel
        items, total, actual_date = DramaIndexModel.get_daily_rank(stat_date, page, page_size)
        result = {'items': items, 'total': total, 'stat_date': str(actual_date) if actual_date else None}
        cache_set(cache_key, result, RankService.CACHE_TTL)
        return result

    @staticmethod
    def get_social_rank(stat_date=None, sort_by='weibo', page=1, page_size=20):
        """社交数据排行"""
        cache_key = f"rank:social:{stat_date}:{sort_by}:{page}:{page_size}"
        cached = cache_get(cache_key)
        if cached:
            return cached

        from app.models.social import SocialModel
        items, total, actual_date = SocialModel.get_daily_rank(stat_date, sort_by, page, page_size)
        result = {'items': items, 'total': total, 'stat_date': str(actual_date) if actual_date else None}
        cache_set(cache_key, result, RankService.CACHE_TTL)
        return result

    @staticmethod
    def get_weekly_play_rank(page=1, page_size=20):
        """周播放量排行"""
        from app.models.playcount import PlaycountModel
        items, total, week_start = PlaycountModel.get_weekly_rank(page, page_size)
        return {'items': items, 'total': total, 'week_start': str(week_start) if week_start else None}

    @staticmethod
    def get_weekly_index_rank(page=1, page_size=20):
        """周剧力指数排行"""
        from app.models.drama_index import DramaIndexModel
        items, total, week_start = DramaIndexModel.get_weekly_rank(page, page_size)
        return {'items': items, 'total': total, 'week_start': str(week_start) if week_start else None}
