from flask import Blueprint, request

from ..utils.db import query, query_one
from ..utils.cache import cache_get, cache_set
from ..utils.response import success, error

daily_bp = Blueprint('daily', __name__)


@daily_bp.route('/heat-rank', methods=['GET'])
def daily_heat_rank():
    """日热度排行榜"""
    date = request.args.get('date', '')
    drama_type = request.args.get('type', '')
    platform = request.args.get('platform', '')
    limit = min(int(request.args.get('limit', 30)), 100)
    page = max(int(request.args.get('page', 1)), 1)
    offset = (page - 1) * limit

    cache_key = f"daily:heat:{date}:{drama_type}:{platform}:{page}:{limit}"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    # 如果没传日期，取最新已发布的日期
    if not date:
        latest = query_one(
            "SELECT MAX(stat_date) as latest FROM heat_daily WHERE published_at IS NOT NULL"
        )
        date = str(latest['latest']) if latest and latest['latest'] else None
        if not date:
            return success({'list': [], 'total': 0, 'date': None})

    where_clauses = ["hd.stat_date = %s"]
    params = [date]

    if drama_type:
        where_clauses.append("d.type = %s")
        params.append(drama_type)

    if platform:
        where_clauses.append("p.short_name = %s")
        params.append(platform)

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               d.status, d.current_episode,
               p.name as platform_name, p.short_name as platform_short,
               hd.heat_avg, hd.heat_max, hd.rank_avg, hd.rank_best,
               hd.stat_date
        FROM heat_daily hd
        JOIN dramas d ON hd.drama_id = d.id
        JOIN platforms p ON hd.platform_id = p.id
        WHERE {where_sql}
        ORDER BY hd.heat_avg DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    items = query(sql, tuple(params))

    count_sql = f"""
        SELECT COUNT(*) as total FROM heat_daily hd
        JOIN dramas d ON hd.drama_id = d.id
        JOIN platforms p ON hd.platform_id = p.id
        WHERE {where_sql}
    """
    total = query_one(count_sql, tuple(params[:-2]))

    result = {
        'list': items,
        'total': total['total'] if total else 0,
        'page': page,
        'page_size': limit,
        'date': date
    }

    cache_set(cache_key, result, expire=600)
    return success(result)


@daily_bp.route('/play-rank', methods=['GET'])
def daily_play_rank():
    """日播放量排行榜"""
    date = request.args.get('date', '')
    drama_type = request.args.get('type', '')
    limit = min(int(request.args.get('limit', 30)), 100)
    page = max(int(request.args.get('page', 1)), 1)
    offset = (page - 1) * limit

    if not date:
        latest = query_one(
            "SELECT MAX(stat_date) as latest FROM playcount_daily WHERE published_at IS NOT NULL"
        )
        date = str(latest['latest']) if latest and latest['latest'] else None
        if not date:
            return success({'list': [], 'total': 0, 'date': None})

    cache_key = f"daily:play:{date}:{drama_type}:{page}:{limit}"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    where_clauses = ["pd.stat_date = %s"]
    params = [date]

    if drama_type:
        where_clauses.append("d.type = %s")
        params.append(drama_type)

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               d.status, d.current_episode,
               SUM(pd.daily_increment) as total_daily_play,
               MAX(pd.total_accumulated) as accumulated_play,
               MAX(pd.avg_per_episode) as avg_per_episode,
               pd.stat_date
        FROM playcount_daily pd
        JOIN dramas d ON pd.drama_id = d.id
        WHERE {where_sql}
        GROUP BY d.id
        ORDER BY total_daily_play DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    items = query(sql, tuple(params))

    # 获取前一天数据计算涨跌
    for item in items:
        prev = query_one(
            "SELECT SUM(daily_increment) as prev_play FROM playcount_daily "
            "WHERE drama_id = %s AND stat_date = DATE_SUB(%s, INTERVAL 1 DAY)",
            (item['id'], date)
        )
        if prev and prev['prev_play'] and item['total_daily_play']:
            change = int(item['total_daily_play']) - int(prev['prev_play'])
            pct = round(change / int(prev['prev_play']) * 100, 1) if prev['prev_play'] > 0 else 0
            item['play_change'] = change
            item['play_change_pct'] = pct
        else:
            item['play_change'] = 0
            item['play_change_pct'] = 0

    result = {
        'list': items,
        'total': len(items),
        'page': page,
        'page_size': limit,
        'date': date
    }

    cache_set(cache_key, result, expire=600)
    return success(result)


@daily_bp.route('/index-rank', methods=['GET'])
def daily_index_rank():
    """日剧力指数排行榜"""
    date = request.args.get('date', '')
    drama_type = request.args.get('type', '')
    limit = min(int(request.args.get('limit', 30)), 100)

    if not date:
        latest = query_one(
            "SELECT MAX(stat_date) as latest FROM drama_index_daily WHERE published_at IS NOT NULL"
        )
        date = str(latest['latest']) if latest and latest['latest'] else None
        if not date:
            return success({'list': [], 'date': None})

    cache_key = f"daily:index:{date}:{drama_type}:{limit}"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    where_clauses = ["di.stat_date = %s"]
    params = [date]

    if drama_type:
        where_clauses.append("d.type = %s")
        params.append(drama_type)

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               d.status,
               di.index_total, di.index_heat, di.index_social,
               di.index_playcount, di.index_reputation,
               di.rank_total, di.rank_change, di.stat_date
        FROM drama_index_daily di
        JOIN dramas d ON di.drama_id = d.id
        WHERE {where_sql}
        ORDER BY di.index_total DESC
        LIMIT %s
    """
    params.append(limit)
    items = query(sql, tuple(params))

    cache_set(cache_key, items, expire=600)
    return success({'list': items, 'date': date})


@daily_bp.route('/social-rank', methods=['GET'])
def daily_social_rank():
    """日讨论度排行榜"""
    date = request.args.get('date', '')
    limit = min(int(request.args.get('limit', 30)), 100)

    if not date:
        latest = query_one(
            "SELECT MAX(stat_date) as latest FROM social_daily"
        )
        date = str(latest['latest']) if latest and latest['latest'] else None
        if not date:
            return success({'list': [], 'date': None})

    sql = """
        SELECT d.id, d.title, d.poster_url, d.douban_score,
               sd.weibo_topic_read_incr, sd.weibo_topic_discuss_incr,
               sd.weibo_hot_search_count,
               sd.douyin_topic_views_incr, sd.baidu_index, sd.wechat_index,
               sd.stat_date
        FROM social_daily sd
        JOIN dramas d ON sd.drama_id = d.id
        WHERE sd.stat_date = %s
        ORDER BY (COALESCE(sd.weibo_topic_read_incr, 0) +
                  COALESCE(sd.douyin_topic_views_incr, 0) * 10 +
                  COALESCE(sd.baidu_index, 0) * 10000) DESC
        LIMIT %s
    """
    items = query(sql, (date, limit))

    return success({'list': items, 'date': date})


@daily_bp.route('/available-dates', methods=['GET'])
def available_dates():
    """获取可查询的日期列表"""
    dates = query(
        "SELECT DISTINCT stat_date FROM heat_daily "
        "WHERE published_at IS NOT NULL ORDER BY stat_date DESC LIMIT 90"
    )
    return success([str(d['stat_date']) for d in dates])
