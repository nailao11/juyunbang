from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..utils.db import query, query_one
from ..utils.cache import cache_get, cache_set
from ..utils.response import success, error

heat_bp = Blueprint('heat', __name__)


@heat_bp.route('/realtime/rank', methods=['GET'])
def realtime_rank():
    """获取实时热度排行榜（取每个剧+平台的最新一条记录）"""
    platform = request.args.get('platform', '')
    drama_type = request.args.get('type', '')
    limit = min(int(request.args.get('limit', 30)), 100)
    page = max(int(request.args.get('page', 1)), 1)
    offset = (page - 1) * limit

    cache_key = f"heat:realtime:rank:{platform}:{drama_type}:{page}:{limit}"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    # 找到最新采集时间（全局）
    latest = query_one("SELECT MAX(record_time) as latest FROM heat_realtime")
    if not latest or not latest['latest']:
        return success({'list': [], 'total': 0, 'page': page, 'page_size': limit, 'update_time': None})

    latest_time = latest['latest']

    # 取最新一批数据（最近一次采集周期内的数据）
    where_clauses = ["hr.record_time >= DATE_SUB(%s, INTERVAL 30 MINUTE)"]
    params = [latest_time]

    if platform:
        where_clauses.append("p.short_name = %s")
        params.append(platform)

    if drama_type:
        where_clauses.append("d.type = %s")
        params.append(drama_type)

    # 只显示在播剧
    where_clauses.append("d.status = 'airing'")

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT d.id, d.title, d.type, d.genre, d.region, d.status,
               d.poster_url, d.douban_score, d.current_episode, d.total_episodes,
               p.name as platform_name, p.short_name as platform_short,
               p.color as platform_color,
               hr.heat_value, hr.heat_rank, hr.record_time
        FROM heat_realtime hr
        JOIN dramas d ON hr.drama_id = d.id
        JOIN platforms p ON hr.platform_id = p.id
        WHERE {where_sql}
        ORDER BY hr.heat_value DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    items = query(sql, tuple(params))

    for item in items:
        item['heat_change'] = 0
        item['heat_change_pct'] = 0
        item['trend'] = 'new'

    count_sql = f"""
        SELECT COUNT(DISTINCT hr.drama_id) as total
        FROM heat_realtime hr
        JOIN dramas d ON hr.drama_id = d.id
        JOIN platforms p ON hr.platform_id = p.id
        WHERE {where_sql}
    """
    total = query_one(count_sql, tuple(params[:-2]))
    total_count = total['total'] if total else 0

    result = {
        'list': items,
        'total': total_count,
        'page': page,
        'page_size': limit,
        'update_time': items[0]['record_time'] if items else None
    }

    cache_set(cache_key, result, expire=120)
    return success(result)


@heat_bp.route('/realtime/all-rank', methods=['GET'])
def all_platform_rank():
    """全平台聚合热度排行 — 最新在播剧，最多30条"""
    drama_type = request.args.get('type', '')
    limit = min(int(request.args.get('limit', 30)), 30)

    cache_key = f"heat:allrank:{drama_type}:{limit}"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    # 找到最新采集时间
    latest = query_one("SELECT MAX(record_time) as latest FROM heat_realtime")
    if not latest or not latest['latest']:
        return success([])

    latest_time = latest['latest']

    where_clause = "AND d.status = 'airing'"
    params = [latest_time]
    if drama_type:
        where_clause += " AND d.type = %s"
        params.append(drama_type)

    sql = f"""
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               d.status, d.current_episode, d.total_episodes,
               AVG(hr.heat_value) as avg_heat,
               MAX(hr.heat_value) as max_heat,
               COUNT(DISTINCT hr.platform_id) as platform_count,
               GROUP_CONCAT(DISTINCT p.short_name) as platforms
        FROM heat_realtime hr
        JOIN dramas d ON hr.drama_id = d.id
        JOIN platforms p ON hr.platform_id = p.id
        WHERE hr.record_time >= DATE_SUB(%s, INTERVAL 30 MINUTE)
        {where_clause}
        GROUP BY d.id
        ORDER BY avg_heat DESC
        LIMIT %s
    """
    params.append(limit)

    items = query(sql, tuple(params))

    for i, item in enumerate(items):
        item['rank'] = i + 1
        item['avg_heat'] = round(float(item['avg_heat']), 2)
        item['max_heat'] = round(float(item['max_heat']), 2)
        item['platforms'] = item['platforms'].split(',') if item['platforms'] else []

    cache_set(cache_key, items, expire=120)
    return success(items)


@heat_bp.route('/realtime/<int:drama_id>', methods=['GET'])
def drama_realtime_heat(drama_id):
    """获取某剧各平台实时热度（取最新采集的数据）"""
    latest = query_one("SELECT MAX(record_time) as latest FROM heat_realtime WHERE drama_id = %s", (drama_id,))
    if not latest or not latest['latest']:
        return success([])

    sql = """
        SELECT p.name as platform_name, p.short_name as platform_short,
               p.color as platform_color,
               hr.heat_value, hr.heat_rank, hr.record_time
        FROM heat_realtime hr
        JOIN platforms p ON hr.platform_id = p.id
        WHERE hr.drama_id = %s
          AND hr.record_time >= DATE_SUB(%s, INTERVAL 30 MINUTE)
        ORDER BY hr.heat_value DESC
    """
    items = query(sql, (drama_id, latest['latest']))
    return success(items)


@heat_bp.route('/realtime/<int:drama_id>/trend', methods=['GET'])
def drama_heat_trend(drama_id):
    """获取某剧今日热度走势"""
    platform = request.args.get('platform', '')

    where_extra = ""
    params = [drama_id]
    if platform:
        where_extra = "AND p.short_name = %s"
        params.append(platform)

    sql = f"""
        SELECT p.short_name as platform, hr.heat_value,
               DATE_FORMAT(hr.record_time, '%%H:%%i') as time_label,
               hr.record_time
        FROM heat_realtime hr
        JOIN platforms p ON hr.platform_id = p.id
        WHERE hr.drama_id = %s
          AND DATE(hr.record_time) = CURDATE()
          {where_extra}
        ORDER BY hr.record_time ASC
    """
    items = query(sql, tuple(params))

    # 按平台分组
    trend_data = {}
    for item in items:
        plat = item['platform']
        if plat not in trend_data:
            trend_data[plat] = {'labels': [], 'values': []}
        trend_data[plat]['labels'].append(item['time_label'])
        trend_data[plat]['values'].append(float(item['heat_value']))

    return success(trend_data)


@heat_bp.route('/realtime/compare', methods=['GET'])
def compare_heat():
    """多剧实时热度对比（最多4部）"""
    drama_ids = request.args.get('drama_ids', '')
    if not drama_ids:
        return error('请指定要对比的剧集', 400)

    ids = [int(x) for x in drama_ids.split(',')[:4]]
    placeholders = ','.join(['%s'] * len(ids))

    sql = f"""
        SELECT d.id as drama_id, d.title, p.short_name as platform,
               hr.heat_value,
               DATE_FORMAT(hr.record_time, '%%H:%%i') as time_label
        FROM heat_realtime hr
        JOIN dramas d ON hr.drama_id = d.id
        JOIN platforms p ON hr.platform_id = p.id
        WHERE hr.drama_id IN ({placeholders})
          AND DATE(hr.record_time) = CURDATE()
        ORDER BY hr.record_time ASC
    """
    items = query(sql, tuple(ids))

    # 按剧集分组
    compare_data = {}
    for item in items:
        did = item['drama_id']
        if did not in compare_data:
            compare_data[did] = {
                'title': item['title'],
                'trend': {}
            }
        plat = item['platform']
        if plat not in compare_data[did]['trend']:
            compare_data[did]['trend'][plat] = {'labels': [], 'values': []}
        compare_data[did]['trend'][plat]['labels'].append(item['time_label'])
        compare_data[did]['trend'][plat]['values'].append(float(item['heat_value']))

    return success(compare_data)
