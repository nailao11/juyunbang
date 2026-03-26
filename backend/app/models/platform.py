from app.utils.db import query, query_one

class PlatformModel:
    @staticmethod
    def get_all_active():
        return query("SELECT * FROM platforms WHERE is_active = 1 ORDER BY sort_order")

    @staticmethod
    def get_by_id(platform_id):
        return query_one("SELECT * FROM platforms WHERE id = %s", (platform_id,))

    @staticmethod
    def get_drama_platforms(drama_id):
        return query(
            "SELECT dp.*, p.name, p.short_name, p.logo_url, p.color "
            "FROM drama_platforms dp JOIN platforms p ON dp.platform_id = p.id "
            "WHERE dp.drama_id = %s",
            (drama_id,)
        )
