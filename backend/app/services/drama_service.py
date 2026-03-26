"""剧集业务逻辑"""
from app.utils.cache import cache_get, cache_set


class DramaService:
    CACHE_TTL_DETAIL = 300
    CACHE_TTL_LIST = 3600

    @staticmethod
    def get_detail(drama_id):
        """获取剧集完整详情"""
        cache_key = f"drama:detail:{drama_id}"
        cached = cache_get(cache_key)
        if cached:
            return cached

        from app.models.drama import DramaModel
        from app.models.platform import PlatformModel
        from app.models.drama_index import DramaIndexModel

        drama = DramaModel.get_by_id(drama_id)
        if not drama:
            return None

        drama['platforms'] = PlatformModel.get_drama_platforms(drama_id)
        drama['index'] = DramaIndexModel.get_latest_for_drama(drama_id)

        cache_set(cache_key, drama, DramaService.CACHE_TTL_DETAIL)
        return drama

    @staticmethod
    def get_related(drama_id, limit=6):
        """获取关联推荐剧集"""
        cache_key = f"drama:related:{drama_id}"
        cached = cache_get(cache_key)
        if cached:
            return cached

        from app.models.drama import DramaModel
        items = DramaModel.get_related(drama_id, limit)
        cache_set(cache_key, items, DramaService.CACHE_TTL_LIST)
        return items

    @staticmethod
    def get_heat_history(drama_id, days=30):
        """获取热度历史"""
        from app.models.heat import HeatModel
        return HeatModel.get_drama_heat_history(drama_id, days)

    @staticmethod
    def get_play_history(drama_id, days=30):
        """获取播放量历史"""
        from app.models.playcount import PlaycountModel
        return PlaycountModel.get_drama_play_history(drama_id, days)

    @staticmethod
    def get_social_history(drama_id, days=30):
        """获取社交数据历史"""
        from app.models.social import SocialModel
        return SocialModel.get_drama_social_history(drama_id, days)

    @staticmethod
    def get_index_history(drama_id, days=30):
        """获取剧力指数历史"""
        from app.models.drama_index import DramaIndexModel
        return DramaIndexModel.get_drama_index_history(drama_id, days)
