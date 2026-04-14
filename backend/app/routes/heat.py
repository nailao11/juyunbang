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
    """两剧综合对比：按 tab（heat/play/social/score）返回指标列表 + 综合评分。

    请求参数：
      drama_ids: 逗号分隔的剧集ID，最多取前 2 部
      tab:       heat | play | social | score，默认 heat

    返回结构：
      {
        drama_a: {id, title, poster_url},
        drama_b: {id, title, poster_url},
        metrics: [{label, type, raw_a, raw_b, unit}],
        score_a: int,
        score_b: int,
        summary: str,
        tab: str
      }
    """
    drama_ids = request.args.get('drama_ids', '')
    tab = request.args.get('tab', 'heat')
    if tab not in ('heat', 'play', 'social', 'score'):
        tab = 'heat'

    if not drama_ids:
        return error('请指定要对比的剧集', 400)

    try:
        ids = [int(x) for x in drama_ids.split(',') if x.strip()][:2]
    except (TypeError, ValueError):
        return error('剧集ID格式错误', 400)

    if len(ids) < 2:
        return error('至少需要两部剧集才能对比', 400)

    dramas = query(
        "SELECT id, title, poster_url, douban_score, douban_votes "
        "FROM dramas WHERE id IN (%s, %s)",
        tuple(ids)
    )
    dramas_by_id = {d['id']: d for d in dramas}
    if len(dramas_by_id) < 2:
        return error('剧集不存在', 404)

    a = dramas_by_id.get(ids[0])
    b = dramas_by_id.get(ids[1])
    if not a or not b:
        return error('剧集不存在', 404)

    metrics = _build_compare_metrics(tab, ids[0], ids[1], a, b)

    # 基于指标原值计算综合得分：每个指标 1 分，A>B 得 A 加分，B>A 得 B 加分，平手各 0.5
    a_points, b_points = 0.0, 0.0
    for m in metrics:
        ra, rb = m.get('raw_a') or 0, m.get('raw_b') or 0
        try:
            ra_f, rb_f = float(ra), float(rb)
        except (TypeError, ValueError):
            continue
        if ra_f > rb_f:
            a_points += 1
        elif rb_f > ra_f:
            b_points += 1
        else:
            a_points += 0.5
            b_points += 0.5

    total_points = a_points + b_points
    if total_points > 0:
        score_a = int(round(a_points / total_points * 100))
        score_b = 100 - score_a
    else:
        score_a, score_b = 50, 50

    if score_a > score_b:
        summary = f"在该维度 {a['title']} 略胜一筹"
    elif score_b > score_a:
        summary = f"在该维度 {b['title']} 略胜一筹"
    else:
        summary = "两部剧在该维度势均力敌"

    return success({
        'drama_a': {'id': a['id'], 'title': a['title'], 'poster_url': a.get('poster_url')},
        'drama_b': {'id': b['id'], 'title': b['title'], 'poster_url': b.get('poster_url')},
        'metrics': metrics,
        'score_a': score_a,
        'score_b': score_b,
        'summary': summary,
        'tab': tab
    })


def _build_compare_metrics(tab, id_a, id_b, drama_a, drama_b):
    """按维度构造对比指标列表。"""
    if tab == 'heat':
        return _compare_metrics_heat(id_a, id_b)
    if tab == 'play':
        return _compare_metrics_play(id_a, id_b)
    if tab == 'social':
        return _compare_metrics_social(id_a, id_b)
    if tab == 'score':
        return _compare_metrics_score(drama_a, drama_b, id_a, id_b)
    return []


def _latest_heat_stats(drama_id):
    """取某剧最近30分钟的实时热度：平均值/峰值/平台数。"""
    row = query_one(
        "SELECT AVG(heat_value) as avg_heat, MAX(heat_value) as max_heat, "
        "COUNT(DISTINCT platform_id) as plat_count, MIN(heat_rank) as best_rank "
        "FROM heat_realtime "
        "WHERE drama_id = %s "
        "AND record_time >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)",
        (drama_id,)
    )
    return row or {}


def _compare_metrics_heat(id_a, id_b):
    a = _latest_heat_stats(id_a)
    b = _latest_heat_stats(id_b)
    return [
        {'label': '平均热度', 'type': 'heat',
         'raw_a': float(a.get('avg_heat') or 0), 'raw_b': float(b.get('avg_heat') or 0)},
        {'label': '峰值热度', 'type': 'heat',
         'raw_a': float(a.get('max_heat') or 0), 'raw_b': float(b.get('max_heat') or 0)},
        {'label': '覆盖平台', 'type': 'number',
         'raw_a': int(a.get('plat_count') or 0), 'raw_b': int(b.get('plat_count') or 0)},
    ]


def _latest_play_stats(drama_id):
    row = query_one(
        "SELECT SUM(daily_increment) as daily_play, "
        "MAX(total_accumulated) as total_play, "
        "MAX(avg_per_episode) as avg_play, stat_date "
        "FROM playcount_daily WHERE drama_id = %s "
        "GROUP BY stat_date ORDER BY stat_date DESC LIMIT 1",
        (drama_id,)
    )
    return row or {}


def _compare_metrics_play(id_a, id_b):
    a = _latest_play_stats(id_a)
    b = _latest_play_stats(id_b)
    return [
        {'label': '累计播放', 'type': 'number',
         'raw_a': int(a.get('total_play') or 0), 'raw_b': int(b.get('total_play') or 0)},
        {'label': '日增播放', 'type': 'number',
         'raw_a': int(a.get('daily_play') or 0), 'raw_b': int(b.get('daily_play') or 0)},
        {'label': '单集均播', 'type': 'number',
         'raw_a': int(a.get('avg_play') or 0), 'raw_b': int(b.get('avg_play') or 0)},
    ]


def _latest_social_stats(drama_id):
    row = query_one(
        "SELECT weibo_topic_read_incr, douyin_topic_views_incr, baidu_index, "
        "weibo_hot_search_count "
        "FROM social_daily WHERE drama_id = %s "
        "ORDER BY stat_date DESC LIMIT 1",
        (drama_id,)
    )
    return row or {}


def _compare_metrics_social(id_a, id_b):
    a = _latest_social_stats(id_a)
    b = _latest_social_stats(id_b)
    return [
        {'label': '微博话题阅读', 'type': 'number',
         'raw_a': int(a.get('weibo_topic_read_incr') or 0),
         'raw_b': int(b.get('weibo_topic_read_incr') or 0)},
        {'label': '抖音相关播放', 'type': 'number',
         'raw_a': int(a.get('douyin_topic_views_incr') or 0),
         'raw_b': int(b.get('douyin_topic_views_incr') or 0)},
        {'label': '百度搜索指数', 'type': 'number',
         'raw_a': int(a.get('baidu_index') or 0),
         'raw_b': int(b.get('baidu_index') or 0)},
        {'label': '微博热搜次数', 'type': 'number',
         'raw_a': int(a.get('weibo_hot_search_count') or 0),
         'raw_b': int(b.get('weibo_hot_search_count') or 0)},
    ]


def _latest_index_row(drama_id):
    row = query_one(
        "SELECT index_total, index_reputation FROM drama_index_daily "
        "WHERE drama_id = %s ORDER BY stat_date DESC LIMIT 1",
        (drama_id,)
    )
    return row or {}


def _compare_metrics_score(drama_a, drama_b, id_a, id_b):
    idx_a = _latest_index_row(id_a)
    idx_b = _latest_index_row(id_b)
    return [
        {'label': '豆瓣评分', 'type': 'score',
         'raw_a': float(drama_a.get('douban_score') or 0),
         'raw_b': float(drama_b.get('douban_score') or 0)},
        {'label': '豆瓣人数', 'type': 'number',
         'raw_a': int(drama_a.get('douban_votes') or 0),
         'raw_b': int(drama_b.get('douban_votes') or 0)},
        {'label': '口碑指数', 'type': 'score',
         'raw_a': float(idx_a.get('index_reputation') or 0),
         'raw_b': float(idx_b.get('index_reputation') or 0)},
        {'label': '综合剧力指数', 'type': 'score',
         'raw_a': float(idx_a.get('index_total') or 0),
         'raw_b': float(idx_b.get('index_total') or 0)},
    ]
