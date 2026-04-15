from flask import Blueprint, request

from ..utils.db import query, query_one
from ..utils.cache import cache_get, cache_set
from ..utils.request_helpers import get_int_arg
from ..utils.response import success, error

daily_bp = Blueprint('daily', __name__)


@daily_bp.route('/heat-rank', methods=['GET'])
def daily_heat_rank():
    """日热度排行榜"""
    date = request.args.get('date', '')
    drama_type = request.args.get('type', '')
    platform = request.args.get('platform', '')
    limit = get_int_arg('limit', 30, min_val=1, max_val=100)
    page = get_int_arg('page', 1, min_val=1)
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
    limit = get_int_arg('limit', 30, min_val=1, max_val=100)
    page = get_int_arg('page', 1, min_val=1)
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
    query_params = params + [limit, offset]
    items = query(sql, tuple(query_params))

    # 总数（用于前端分页）
    count_sql = f"""
        SELECT COUNT(DISTINCT pd.drama_id) as total
        FROM playcount_daily pd
        JOIN dramas d ON pd.drama_id = d.id
        WHERE {where_sql}
    """
    total_row = query_one(count_sql, tuple(params))
    total_count = total_row['total'] if total_row else 0

    # 一次性取出本页所有剧集前一天的播放数据，避免 N+1 查询
    drama_ids = [item['id'] for item in items]
    prev_map = {}
    if drama_ids:
        placeholders = ','.join(['%s'] * len(drama_ids))
        prev_rows = query(
            f"SELECT drama_id, SUM(daily_increment) as prev_play "
            f"FROM playcount_daily "
            f"WHERE stat_date = DATE_SUB(%s, INTERVAL 1 DAY) "
            f"  AND drama_id IN ({placeholders}) "
            f"GROUP BY drama_id",
            tuple([date] + drama_ids)
        )
        prev_map = {r['drama_id']: r['prev_play'] for r in prev_rows}

    for item in items:
        prev_play = prev_map.get(item['id'])
        if prev_play and item['total_daily_play']:
            change = int(item['total_daily_play']) - int(prev_play)
            pct = round(change / int(prev_play) * 100, 1) if int(prev_play) > 0 else 0
            item['play_change'] = change
            item['play_change_pct'] = pct
        else:
            item['play_change'] = 0
            item['play_change_pct'] = 0

    result = {
        'list': items,
        'total': total_count,
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
    limit = get_int_arg('limit', 30, min_val=1, max_val=100)

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
    drama_type = request.args.get('type', '')
    limit = get_int_arg('limit', 30, min_val=1, max_val=100)

    if not date:
        latest = query_one(
            "SELECT MAX(stat_date) as latest FROM social_daily"
        )
        date = str(latest['latest']) if latest and latest['latest'] else None
        if not date:
            return success({'list': [], 'date': None})

    where_extra = ""
    params = [date]
    if drama_type:
        where_extra = "AND d.type = %s"
        params.append(drama_type)

    sql = f"""
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               sd.weibo_topic_read_incr, sd.weibo_topic_discuss_incr,
               sd.weibo_hot_search_count,
               sd.douyin_topic_views_incr, sd.baidu_index, sd.wechat_index,
               sd.stat_date,
               (COALESCE(sd.weibo_topic_read_incr, 0) +
                COALESCE(sd.douyin_topic_views_incr, 0) * 10 +
                COALESCE(sd.baidu_index, 0) * 10000) as social_score
        FROM social_daily sd
        JOIN dramas d ON sd.drama_id = d.id
        WHERE sd.stat_date = %s
        {where_extra}
        ORDER BY social_score DESC
        LIMIT %s
    """
    params.append(limit)
    items = query(sql, tuple(params))

    for item in items:
        if item.get('social_score') is not None:
            item['social_score'] = int(item['social_score'])

    return success({'list': items, 'date': date})


@daily_bp.route('/available-dates', methods=['GET'])
def available_dates():
    """获取可查询的日期列表"""
    dates = query(
        "SELECT DISTINCT stat_date FROM heat_daily "
        "WHERE published_at IS NOT NULL ORDER BY stat_date DESC LIMIT 90"
    )
    return success([str(d['stat_date']) for d in dates])
