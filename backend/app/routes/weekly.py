from flask import Blueprint, request

from ..utils.db import query, query_one
from ..utils.cache import cache_get, cache_set
from ..utils.response import success

weekly_bp = Blueprint('weekly', __name__)


@weekly_bp.route('/play-rank', methods=['GET'])
def weekly_play_rank():
    """周播放量排行榜"""
    week_start = request.args.get('week_start', '')
    drama_type = request.args.get('type', '')
    limit = min(int(request.args.get('limit', 30)), 100)

    if not week_start:
        latest = query_one(
            "SELECT DATE_SUB(MAX(stat_date), INTERVAL WEEKDAY(MAX(stat_date)) DAY) as ws "
            "FROM playcount_daily WHERE published_at IS NOT NULL"
        )
        week_start = str(latest['ws']) if latest and latest['ws'] else None
        if not week_start:
            return success({'list': [], 'week_start': None})

    cache_key = f"weekly:play:{week_start}:{drama_type}:{limit}"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    where_extra = ""
    params = [week_start, week_start]
    if drama_type:
        where_extra = "AND d.type = %s"
        params.append(drama_type)

    sql = f"""
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               d.status, d.current_episode,
               SUM(pd.daily_increment) as weekly_play,
               MAX(pd.total_accumulated) as accumulated_play,
               COUNT(pd.stat_date) as data_days
        FROM playcount_daily pd
        JOIN dramas d ON pd.drama_id = d.id
        WHERE pd.stat_date >= %s
          AND pd.stat_date < DATE_ADD(%s, INTERVAL 7 DAY)
          {where_extra}
        GROUP BY d.id
        HAVING weekly_play > 0
        ORDER BY weekly_play DESC
        LIMIT %s
    """
    params.append(limit)
    items = query(sql, tuple(params))

    for i, item in enumerate(items):
        item['rank'] = i + 1

    result = {'list': items, 'week_start': week_start}
    cache_set(cache_key, result, expire=3600)
    return success(result)


@weekly_bp.route('/index-rank', methods=['GET'])
def weekly_index_rank():
    """周剧力指数排行榜"""
    week_start = request.args.get('week_start', '')
    limit = min(int(request.args.get('limit', 30)), 100)

    if not week_start:
        latest = query_one(
            "SELECT DATE_SUB(MAX(stat_date), INTERVAL WEEKDAY(MAX(stat_date)) DAY) as ws "
            "FROM drama_index_daily WHERE published_at IS NOT NULL"
        )
        week_start = str(latest['ws']) if latest and latest['ws'] else None
        if not week_start:
            return success({'list': [], 'week_start': None})

    sql = """
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               AVG(di.index_total) as avg_index,
               AVG(di.index_heat) as avg_heat,
               AVG(di.index_social) as avg_social,
               AVG(di.index_playcount) as avg_play,
               AVG(di.index_reputation) as avg_reputation
        FROM drama_index_daily di
        JOIN dramas d ON di.drama_id = d.id
        WHERE di.stat_date >= %s
          AND di.stat_date < DATE_ADD(%s, INTERVAL 7 DAY)
        GROUP BY d.id
        ORDER BY avg_index DESC
        LIMIT %s
    """
    items = query(sql, (week_start, week_start, limit))

    for i, item in enumerate(items):
        item['rank'] = i + 1
        for key in ['avg_index', 'avg_heat', 'avg_social', 'avg_play', 'avg_reputation']:
            if item[key]:
                item[key] = round(float(item[key]), 2)

    return success({'list': items, 'week_start': week_start})


@weekly_bp.route('/monthly/play-rank', methods=['GET'])
def monthly_play_rank():
    """月播放量排行榜"""
    month = request.args.get('month', '')
    limit = min(int(request.args.get('limit', 30)), 100)

    if not month:
        latest = query_one(
            "SELECT DATE_FORMAT(MAX(stat_date), '%%Y-%%m') as m FROM playcount_daily"
        )
        month = latest['m'] if latest and latest['m'] else None
        if not month:
            return success({'list': [], 'month': None})

    sql = """
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               d.status,
               SUM(pd.daily_increment) as monthly_play,
               MAX(pd.total_accumulated) as accumulated_play
        FROM playcount_daily pd
        JOIN dramas d ON pd.drama_id = d.id
        WHERE DATE_FORMAT(pd.stat_date, '%%Y-%%m') = %s
        GROUP BY d.id
        HAVING monthly_play > 0
        ORDER BY monthly_play DESC
        LIMIT %s
    """
    items = query(sql, (month, limit))

    for i, item in enumerate(items):
        item['rank'] = i + 1

    return success({'list': items, 'month': month})
