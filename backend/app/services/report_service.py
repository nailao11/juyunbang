"""报告业务逻辑"""
from app.utils.cache import cache_get, cache_set


class ReportService:
    @staticmethod
    def get_daily_brief():
        """获取最新日报"""
        cache_key = "report:daily:latest"
        cached = cache_get(cache_key)
        if cached:
            return cached

        from app.models.news import NewsModel
        report = NewsModel.get_latest_daily_report()
        if report:
            cache_set(cache_key, report, 600)
        return report

    @staticmethod
    def get_tracking_monthly_report(user_id, year_month):
        """获取用户月度追剧报告"""
        from app.models.tracking import TrackingModel
        from app.utils.db import query

        new_dramas = query(
            "SELECT ut.*, d.title, d.poster_url FROM user_tracking ut "
            "JOIN dramas d ON ut.drama_id = d.id "
            "WHERE ut.user_id = %s AND DATE_FORMAT(ut.started_at, '%%Y-%%m') = %s",
            (user_id, year_month)
        )
        finished = query(
            "SELECT ut.*, d.title, d.poster_url FROM user_tracking ut "
            "JOIN dramas d ON ut.drama_id = d.id "
            "WHERE ut.user_id = %s AND ut.status = 'watched' "
            "AND DATE_FORMAT(ut.finished_at, '%%Y-%%m') = %s",
            (user_id, year_month)
        )
        dropped = query(
            "SELECT ut.*, d.title, d.poster_url FROM user_tracking ut "
            "JOIN dramas d ON ut.drama_id = d.id "
            "WHERE ut.user_id = %s AND ut.status = 'dropped' "
            "AND DATE_FORMAT(ut.updated_at, '%%Y-%%m') = %s",
            (user_id, year_month)
        )
        return {
            'year_month': year_month,
            'new_dramas': new_dramas or [],
            'finished': finished or [],
            'dropped': dropped or [],
        }
