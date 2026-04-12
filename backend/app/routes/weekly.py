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


@weekly_bp.route('/heat-rank', methods=['GET'])
def weekly_heat_rank():
    """周热度排行榜：按 heat_daily 聚合一周平均热度。"""
    week_start = request.args.get('week_start', '')
    drama_type = request.args.get('type', '')
    limit = min(int(request.args.get('limit', 30)), 100)

    if not week_start:
        latest = query_one(
            "SELECT DATE_SUB(MAX(stat_date), INTERVAL WEEKDAY(MAX(stat_date)) DAY) as ws "
            "FROM heat_daily WHERE published_at IS NOT NULL"
        )
        week_start = str(latest['ws']) if latest and latest['ws'] else None
        if not week_start:
            return success({'list': [], 'week_start': None})

    cache_key = f"weekly:heat:{week_start}:{drama_type}:{limit}"
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
               AVG(hd.heat_avg) as heat_avg,
               MAX(hd.heat_max) as heat_max,
               MIN(hd.rank_best) as rank_best
        FROM heat_daily hd
        JOIN dramas d ON hd.drama_id = d.id
        WHERE hd.stat_date >= %s
          AND hd.stat_date < DATE_ADD(%s, INTERVAL 7 DAY)
          {where_extra}
        GROUP BY d.id
        HAVING heat_avg > 0
        ORDER BY heat_avg DESC
        LIMIT %s
    """
    params.append(limit)
    items = query(sql, tuple(params))

    for i, item in enumerate(items):
        item['rank'] = i + 1
        if item.get('heat_avg') is not None:
            item['heat_avg'] = round(float(item['heat_avg']), 2)
        if item.get('heat_max') is not None:
            item['heat_max'] = round(float(item['heat_max']), 2)

    result = {'list': items, 'week_start': week_start}
    cache_set(cache_key, result, expire=3600)
    return success(result)


@weekly_bp.route('/social-rank', methods=['GET'])
def weekly_social_rank():
    """周讨论度排行榜：聚合一周微博/抖音/百度等数据。"""
    week_start = request.args.get('week_start', '')
    drama_type = request.args.get('type', '')
    limit = min(int(request.args.get('limit', 30)), 100)

    if not week_start:
        latest = query_one(
            "SELECT DATE_SUB(MAX(stat_date), INTERVAL WEEKDAY(MAX(stat_date)) DAY) as ws "
            "FROM social_daily"
        )
        week_start = str(latest['ws']) if latest and latest['ws'] else None
        if not week_start:
            return success({'list': [], 'week_start': None})

    where_extra = ""
    params = [week_start, week_start]
    if drama_type:
        where_extra = "AND d.type = %s"
        params.append(drama_type)

    sql = f"""
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               SUM(COALESCE(sd.weibo_topic_read_incr, 0)) as weibo_topic_read_incr,
               SUM(COALESCE(sd.weibo_topic_discuss_incr, 0)) as weibo_topic_discuss_incr,
               SUM(COALESCE(sd.douyin_topic_views_incr, 0)) as douyin_topic_views_incr,
               AVG(COALESCE(sd.baidu_index, 0)) as baidu_index,
               SUM(COALESCE(sd.weibo_hot_search_count, 0)) as weibo_hot_search_count,
               (SUM(COALESCE(sd.weibo_topic_read_incr, 0)) +
                SUM(COALESCE(sd.douyin_topic_views_incr, 0)) * 10 +
                AVG(COALESCE(sd.baidu_index, 0)) * 10000) as social_score
        FROM social_daily sd
        JOIN dramas d ON sd.drama_id = d.id
        WHERE sd.stat_date >= %s
          AND sd.stat_date < DATE_ADD(%s, INTERVAL 7 DAY)
          {where_extra}
        GROUP BY d.id
        HAVING social_score > 0
        ORDER BY social_score DESC
        LIMIT %s
    """
    params.append(limit)
    items = query(sql, tuple(params))

    for i, item in enumerate(items):
        item['rank'] = i + 1
        if item.get('social_score') is not None:
            item['social_score'] = int(float(item['social_score']))
        if item.get('baidu_index') is not None:
            item['baidu_index'] = int(float(item['baidu_index']))

    return success({'list': items, 'week_start': week_start})


@weekly_bp.route('/monthly/play-rank', methods=['GET'])
def monthly_play_rank():
    """月播放量排行榜"""
    month = request.args.get('month', '')
    drama_type = request.args.get('type', '')
    limit = min(int(request.args.get('limit', 30)), 100)

    if not month:
        latest = query_one(
            "SELECT DATE_FORMAT(MAX(stat_date), '%%Y-%%m') as m FROM playcount_daily"
        )
        month = latest['m'] if latest and latest['m'] else None
        if not month:
            return success({'list': [], 'month': None})

    where_extra = ""
    params = [month]
    if drama_type:
        where_extra = "AND d.type = %s"
        params.append(drama_type)

    sql = f"""
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               d.status,
               SUM(pd.daily_increment) as monthly_play,
               MAX(pd.total_accumulated) as accumulated_play
        FROM playcount_daily pd
        JOIN dramas d ON pd.drama_id = d.id
        WHERE DATE_FORMAT(pd.stat_date, '%%Y-%%m') = %s
        {where_extra}
        GROUP BY d.id
        HAVING monthly_play > 0
        ORDER BY monthly_play DESC
        LIMIT %s
    """
    params.append(limit)
    items = query(sql, tuple(params))

    for i, item in enumerate(items):
        item['rank'] = i + 1

    return success({'list': items, 'month': month})


@weekly_bp.route('/monthly/heat-rank', methods=['GET'])
def monthly_heat_rank():
    """月热度排行榜：heat_daily 按月聚合。"""
    month = request.args.get('month', '')
    drama_type = request.args.get('type', '')
    limit = min(int(request.args.get('limit', 30)), 100)

    if not month:
        latest = query_one(
            "SELECT DATE_FORMAT(MAX(stat_date), '%%Y-%%m') as m FROM heat_daily "
            "WHERE published_at IS NOT NULL"
        )
        month = latest['m'] if latest and latest['m'] else None
        if not month:
            return success({'list': [], 'month': None})

    where_extra = ""
    params = [month]
    if drama_type:
        where_extra = "AND d.type = %s"
        params.append(drama_type)

    sql = f"""
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               d.status, d.current_episode,
               AVG(hd.heat_avg) as heat_avg,
               MAX(hd.heat_max) as heat_max
        FROM heat_daily hd
        JOIN dramas d ON hd.drama_id = d.id
        WHERE DATE_FORMAT(hd.stat_date, '%%Y-%%m') = %s
        {where_extra}
        GROUP BY d.id
        HAVING heat_avg > 0
        ORDER BY heat_avg DESC
        LIMIT %s
    """
    params.append(limit)
    items = query(sql, tuple(params))

    for i, item in enumerate(items):
        item['rank'] = i + 1
        if item.get('heat_avg') is not None:
            item['heat_avg'] = round(float(item['heat_avg']), 2)
        if item.get('heat_max') is not None:
            item['heat_max'] = round(float(item['heat_max']), 2)

    return success({'list': items, 'month': month})


@weekly_bp.route('/monthly/index-rank', methods=['GET'])
def monthly_index_rank():
    """月剧力指数排行榜。"""
    month = request.args.get('month', '')
    drama_type = request.args.get('type', '')
    limit = min(int(request.args.get('limit', 30)), 100)

    if not month:
        latest = query_one(
            "SELECT DATE_FORMAT(MAX(stat_date), '%%Y-%%m') as m FROM drama_index_daily "
            "WHERE published_at IS NOT NULL"
        )
        month = latest['m'] if latest and latest['m'] else None
        if not month:
            return success({'list': [], 'month': None})

    where_extra = ""
    params = [month]
    if drama_type:
        where_extra = "AND d.type = %s"
        params.append(drama_type)

    sql = f"""
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               AVG(di.index_total) as avg_index,
               AVG(di.index_heat) as avg_heat,
               AVG(di.index_social) as avg_social,
               AVG(di.index_playcount) as avg_play,
               AVG(di.index_reputation) as avg_reputation
        FROM drama_index_daily di
        JOIN dramas d ON di.drama_id = d.id
        WHERE DATE_FORMAT(di.stat_date, '%%Y-%%m') = %s
        {where_extra}
        GROUP BY d.id
        HAVING avg_index > 0
        ORDER BY avg_index DESC
        LIMIT %s
    """
    params.append(limit)
    items = query(sql, tuple(params))

    for i, item in enumerate(items):
        item['rank'] = i + 1
        for key in ['avg_index', 'avg_heat', 'avg_social', 'avg_play', 'avg_reputation']:
            if item.get(key) is not None:
                item[key] = round(float(item[key]), 2)

    return success({'list': items, 'month': month})


@weekly_bp.route('/monthly/social-rank', methods=['GET'])
def monthly_social_rank():
    """月讨论度排行榜。"""
    month = request.args.get('month', '')
    drama_type = request.args.get('type', '')
    limit = min(int(request.args.get('limit', 30)), 100)

    if not month:
        latest = query_one(
            "SELECT DATE_FORMAT(MAX(stat_date), '%%Y-%%m') as m FROM social_daily"
        )
        month = latest['m'] if latest and latest['m'] else None
        if not month:
            return success({'list': [], 'month': None})

    where_extra = ""
    params = [month]
    if drama_type:
        where_extra = "AND d.type = %s"
        params.append(drama_type)

    sql = f"""
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               SUM(COALESCE(sd.weibo_topic_read_incr, 0)) as weibo_topic_read_incr,
               SUM(COALESCE(sd.douyin_topic_views_incr, 0)) as douyin_topic_views_incr,
               AVG(COALESCE(sd.baidu_index, 0)) as baidu_index,
               SUM(COALESCE(sd.weibo_hot_search_count, 0)) as weibo_hot_search_count,
               (SUM(COALESCE(sd.weibo_topic_read_incr, 0)) +
                SUM(COALESCE(sd.douyin_topic_views_incr, 0)) * 10 +
                AVG(COALESCE(sd.baidu_index, 0)) * 10000) as social_score
        FROM social_daily sd
        JOIN dramas d ON sd.drama_id = d.id
        WHERE DATE_FORMAT(sd.stat_date, '%%Y-%%m') = %s
        {where_extra}
        GROUP BY d.id
        HAVING social_score > 0
        ORDER BY social_score DESC
        LIMIT %s
    """
    params.append(limit)
    items = query(sql, tuple(params))

    for i, item in enumerate(items):
        item['rank'] = i + 1
        if item.get('social_score') is not None:
            item['social_score'] = int(float(item['social_score']))
        if item.get('baidu_index') is not None:
            item['baidu_index'] = int(float(item['baidu_index']))

    return success({'list': items, 'month': month})
