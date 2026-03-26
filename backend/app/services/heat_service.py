"""热度数据业务逻辑"""
from app.utils.cache import cache_get, cache_set


class HeatService:
    CACHE_TTL_REALTIME = 120  # 实时数据缓存2分钟
    CACHE_TTL_DAILY = 600     # 日度数据缓存10分钟

    @staticmethod
    def get_realtime_rank(platform_id=None, page=1, page_size=20):
        """获取实时热度排行"""
        cache_key = f"heat:realtime:rank:{platform_id}:{page}:{page_size}"
        cached = cache_get(cache_key)
        if cached:
            return cached

        from app.models.heat import HeatModel
        items = HeatModel.get_realtime_rank(platform_id, page, page_size)
        result = {'items': items, 'page': page, 'page_size': page_size}
        cache_set(cache_key, result, HeatService.CACHE_TTL_REALTIME)
        return result

    @staticmethod
    def get_drama_trend(drama_id, hours=24):
        """获取单剧热度走势"""
        cache_key = f"heat:trend:{drama_id}:{hours}"
        cached = cache_get(cache_key)
        if cached:
            return cached

        from app.models.heat import HeatModel
        data = HeatModel.get_drama_realtime(drama_id, hours)
        # 按平台分组
        platforms = {}
        for row in data:
            pname = row.get('platform_name', '')
            if pname not in platforms:
                platforms[pname] = []
            platforms[pname].append(row)

        cache_set(cache_key, platforms, HeatService.CACHE_TTL_REALTIME)
        return platforms

    @staticmethod
    def get_daily_rank(stat_date=None, platform_id=None, page=1, page_size=20):
        """获取日度热度排行"""
        cache_key = f"heat:daily:rank:{stat_date}:{platform_id}:{page}:{page_size}"
        cached = cache_get(cache_key)
        if cached:
            return cached

        from app.models.heat import HeatModel
        items, total, actual_date = HeatModel.get_daily_rank(stat_date, platform_id, page, page_size)
        result = {'items': items, 'total': total, 'stat_date': str(actual_date) if actual_date else None}
        cache_set(cache_key, result, HeatService.CACHE_TTL_DAILY)
        return result
