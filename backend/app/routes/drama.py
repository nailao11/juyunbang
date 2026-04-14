import json

from flask import Blueprint, request

from ..utils.db import query, query_one
from ..utils.cache import cache_get, cache_set
from ..utils.response import success, error

drama_bp = Blueprint('drama', __name__)


def _parse_cast_list(cast_main_raw):
    """解析 cast_main 字段为 [{name, role, avatar}] 列表。

    兼容多种历史格式：
    - JSON 数组：["赵丽颖", "林更新"]
    - JSON 对象数组：[{"name": "赵丽颖", "role": "沈璃"}]
    - 逗号分隔字符串：'赵丽颖,林更新'
    """
    if not cast_main_raw:
        return []

    cast = None
    if isinstance(cast_main_raw, (list, tuple)):
        cast = list(cast_main_raw)
    else:
        text = str(cast_main_raw).strip()
        if not text:
            return []
        if text.startswith('[') or text.startswith('{'):
            try:
                cast = json.loads(text)
            except (ValueError, TypeError):
                cast = None
        if cast is None:
            # 回退：按 , / 、 等分隔符切分
            cast = [s.strip() for s in text.replace('，', ',').replace('、', ',').split(',') if s.strip()]

    if not isinstance(cast, list):
        return []

    result = []
    for item in cast:
        if isinstance(item, dict):
            name = item.get('name') or item.get('actor') or ''
            if not name:
                continue
            result.append({
                'name': name,
                'role': item.get('role') or item.get('character') or '',
                'avatar': item.get('avatar') or ''
            })
        elif item:
            result.append({'name': str(item), 'role': '', 'avatar': ''})
    return result


@drama_bp.route('/<int:drama_id>', methods=['GET'])
def drama_detail(drama_id):
    """获取剧集详细信息"""
    cache_key = f"drama:detail:{drama_id}"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    drama = query_one(
        "SELECT * FROM dramas WHERE id = %s", (drama_id,)
    )
    if not drama:
        return error('剧集不存在', 404)

    # 解析主演 JSON 为结构化 cast_list，供前端直接渲染
    drama['cast_list'] = _parse_cast_list(drama.get('cast_main'))

    # 解析题材为数组（前端标签渲染使用）
    genre_str = drama.get('genre') or ''
    if genre_str:
        drama['genres'] = [g.strip() for g in genre_str.replace('，', ',').replace('、', ',').replace('/', ',').split(',') if g.strip()]
    else:
        drama['genres'] = []

    # 从 air_date 推导出年份（供前端 drama-detail 页渲染使用）
    air_date = drama.get('air_date')
    year = None
    if air_date is not None:
        if hasattr(air_date, 'year'):
            year = air_date.year
        else:
            try:
                year = int(str(air_date)[:4])
            except (ValueError, TypeError):
                year = None
    drama['year'] = year

    # 获取播出平台
    platforms = query(
        "SELECT p.name, p.short_name, p.color, dp.is_exclusive, dp.platform_url "
        "FROM drama_platforms dp "
        "JOIN platforms p ON dp.platform_id = p.id "
        "WHERE dp.drama_id = %s",
        (drama_id,)
    )
    drama['platforms'] = platforms

    # 获取最新实时热度
    heat = query(
        "SELECT p.name as platform_name, p.short_name, p.color, "
        "hr.heat_value, hr.heat_rank, hr.record_time "
        "FROM heat_realtime hr "
        "JOIN platforms p ON hr.platform_id = p.id "
        "WHERE hr.drama_id = %s "
        "AND hr.record_time >= DATE_SUB(NOW(), INTERVAL 30 MINUTE) "
        "ORDER BY hr.heat_value DESC",
        (drama_id,)
    )
    drama['current_heat'] = heat

    # 获取最新剧力指数
    index_data = query_one(
        "SELECT * FROM drama_index_daily "
        "WHERE drama_id = %s ORDER BY stat_date DESC LIMIT 1",
        (drama_id,)
    )
    drama['drama_index'] = index_data

    # 获取最新播放量
    play_data = query_one(
        "SELECT SUM(daily_increment) as latest_daily_play, "
        "MAX(total_accumulated) as total_play, "
        "MAX(avg_per_episode) as avg_episode_play, stat_date "
        "FROM playcount_daily WHERE drama_id = %s "
        "GROUP BY stat_date ORDER BY stat_date DESC LIMIT 1",
        (drama_id,)
    )
    drama['play_data'] = play_data

    # 获取社交媒体数据
    social = query_one(
        "SELECT * FROM social_daily WHERE drama_id = %s "
        "ORDER BY stat_date DESC LIMIT 1",
        (drama_id,)
    )
    drama['social_data'] = social

    cache_set(cache_key, drama, expire=300)
    return success(drama)


@drama_bp.route('/<int:drama_id>/episodes', methods=['GET'])
def drama_episodes(drama_id):
    """获取分集列表"""
    episodes = query(
        "SELECT * FROM drama_episodes WHERE drama_id = %s "
        "ORDER BY episode_number ASC",
        (drama_id,)
    )
    return success(episodes)


@drama_bp.route('/<int:drama_id>/heat-history', methods=['GET'])
def drama_heat_history(drama_id):
    """获取热度历史趋势"""
    days = min(int(request.args.get('days', 30)), 90)

    sql = """
        SELECT p.short_name as platform, hd.stat_date,
               hd.heat_avg, hd.heat_max, hd.rank_avg
        FROM heat_daily hd
        JOIN platforms p ON hd.platform_id = p.id
        WHERE hd.drama_id = %s
          AND hd.stat_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        ORDER BY hd.stat_date ASC, p.short_name
    """
    items = query(sql, (drama_id, days))

    # 按平台分组
    trend = {}
    for item in items:
        plat = item['platform']
        if plat not in trend:
            trend[plat] = {'dates': [], 'heat_avg': [], 'heat_max': [], 'rank': []}
        trend[plat]['dates'].append(str(item['stat_date']))
        trend[plat]['heat_avg'].append(float(item['heat_avg']) if item['heat_avg'] else 0)
        trend[plat]['heat_max'].append(float(item['heat_max']) if item['heat_max'] else 0)
        trend[plat]['rank'].append(item['rank_avg'] or 0)

    return success(trend)


@drama_bp.route('/<int:drama_id>/play-history', methods=['GET'])
def drama_play_history(drama_id):
    """获取播放量历史趋势"""
    days = min(int(request.args.get('days', 30)), 90)

    sql = """
        SELECT pd.stat_date,
               SUM(pd.daily_increment) as daily_play,
               MAX(pd.total_accumulated) as total_play
        FROM playcount_daily pd
        WHERE pd.drama_id = %s
          AND pd.stat_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        GROUP BY pd.stat_date
        ORDER BY pd.stat_date ASC
    """
    items = query(sql, (drama_id, days))

    dates = [str(i['stat_date']) for i in items]
    daily_plays = [int(i['daily_play'] or 0) for i in items]
    total_plays = [int(i['total_play'] or 0) for i in items]

    return success({
        'dates': dates,
        'daily_plays': daily_plays,
        'total_plays': total_plays
    })


@drama_bp.route('/<int:drama_id>/social-history', methods=['GET'])
def drama_social_history(drama_id):
    """获取社交数据历史趋势"""
    days = min(int(request.args.get('days', 30)), 90)

    sql = """
        SELECT stat_date, weibo_topic_read_incr, weibo_topic_discuss_incr,
               weibo_hot_search_count, douyin_topic_views_incr,
               baidu_index, wechat_index
        FROM social_daily
        WHERE drama_id = %s
          AND stat_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        ORDER BY stat_date ASC
    """
    items = query(sql, (drama_id, days))
    return success(items)


@drama_bp.route('/<int:drama_id>/index-history', methods=['GET'])
def drama_index_history(drama_id):
    """获取剧力指数历史趋势"""
    days = min(int(request.args.get('days', 30)), 90)

    sql = """
        SELECT stat_date, index_total, index_heat, index_social,
               index_playcount, index_reputation, rank_total, rank_change
        FROM drama_index_daily
        WHERE drama_id = %s
          AND stat_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        ORDER BY stat_date ASC
    """
    items = query(sql, (drama_id, days))
    return success(items)


@drama_bp.route('/<int:drama_id>/related', methods=['GET'])
def drama_related(drama_id):
    """获取相关推荐剧集"""
    drama = query_one("SELECT type, genre, region FROM dramas WHERE id = %s", (drama_id,))
    if not drama:
        return error('剧集不存在', 404)

    sql = """
        SELECT id, title, type, genre, poster_url, douban_score, status
        FROM dramas
        WHERE id != %s AND status = 'airing'
          AND (type = %s OR genre LIKE %s)
        ORDER BY douban_score DESC
        LIMIT 10
    """
    genre_keyword = f"%{drama['genre'].split(',')[0]}%" if drama.get('genre') else '%'
    items = query(sql, (drama_id, drama['type'], genre_keyword))

    return success(items)
