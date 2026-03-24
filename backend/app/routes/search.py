from flask import Blueprint, request

from ..utils.db import query, query_one, execute
from ..utils.cache import cache_get, cache_set
from ..utils.response import success

search_bp = Blueprint('search', __name__)


@search_bp.route('', methods=['GET'])
def search():
    """全局搜索"""
    keyword = request.args.get('keyword', '').strip()
    drama_type = request.args.get('type', '')
    limit = min(int(request.args.get('limit', 20)), 50)
    page = max(int(request.args.get('page', 1)), 1)
    offset = (page - 1) * limit

    if not keyword:
        return success({'list': [], 'total': 0})

    where_extra = ""
    params = [f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"]

    if drama_type:
        where_extra = "AND d.type = %s"
        params.append(drama_type)

    sql = f"""
        SELECT d.id, d.title, d.type, d.genre, d.region,
               d.poster_url, d.douban_score, d.status,
               d.current_episode, d.total_episodes, d.air_date,
               d.director, d.cast_main
        FROM dramas d
        WHERE (d.title LIKE %s OR d.director LIKE %s OR d.cast_main LIKE %s)
        {where_extra}
        ORDER BY d.status = 'airing' DESC, d.air_date DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    items = query(sql, tuple(params))

    count_params = [f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"]
    if drama_type:
        count_params.append(drama_type)
    count = query_one(
        f"SELECT COUNT(*) as total FROM dramas d "
        f"WHERE (d.title LIKE %s OR d.director LIKE %s OR d.cast_main LIKE %s) "
        f"{where_extra}",
        tuple(count_params)
    )

    return success({
        'list': items,
        'total': count['total'] if count else 0,
        'page': page,
        'keyword': keyword
    })


@search_bp.route('/hot', methods=['GET'])
def search_hot():
    """搜索热词"""
    cache_key = "search:hot"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    # 取在播剧中热度最高的作为热词
    items = query(
        "SELECT d.title FROM dramas d "
        "WHERE d.status = 'airing' "
        "ORDER BY d.douban_score DESC "
        "LIMIT 10"
    )
    hot_words = [item['title'] for item in items]

    cache_set(cache_key, hot_words, expire=3600)
    return success(hot_words)


@search_bp.route('/suggest', methods=['GET'])
def search_suggest():
    """搜索建议（自动补全）"""
    keyword = request.args.get('keyword', '').strip()
    if not keyword or len(keyword) < 1:
        return success([])

    items = query(
        "SELECT id, title, type, poster_url FROM dramas "
        "WHERE title LIKE %s LIMIT 8",
        (f"%{keyword}%",)
    )
    return success(items)


@search_bp.route('/discover/genres', methods=['GET'])
def genres():
    """获取所有类型"""
    cache_key = "discover:genres"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    items = query("SELECT DISTINCT genre FROM dramas WHERE genre IS NOT NULL AND genre != ''")
    genre_set = set()
    for item in items:
        for g in item['genre'].split(','):
            g = g.strip()
            if g:
                genre_set.add(g)

    genre_list = sorted(genre_set)
    cache_set(cache_key, genre_list, expire=86400)
    return success(genre_list)


@search_bp.route('/discover/upcoming', methods=['GET'])
def upcoming():
    """待播期待榜"""
    cache_key = "discover:upcoming"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    sql = """
        SELECT id, title, type, genre, poster_url, douban_score,
               status, air_date, total_episodes, director, cast_main
        FROM dramas
        WHERE status = 'upcoming' AND air_date >= CURDATE()
        ORDER BY air_date ASC
        LIMIT 30
    """
    items = query(sql)
    cache_set(cache_key, items, expire=3600)
    return success(items)


@search_bp.route('/discover/by-genre', methods=['GET'])
def by_genre():
    """按类型浏览"""
    genre = request.args.get('genre', '')
    limit = min(int(request.args.get('limit', 20)), 50)
    page = max(int(request.args.get('page', 1)), 1)
    offset = (page - 1) * limit

    if not genre:
        return success({'list': [], 'total': 0})

    sql = """
        SELECT id, title, type, genre, poster_url, douban_score,
               status, air_date, current_episode, total_episodes
        FROM dramas
        WHERE genre LIKE %s
        ORDER BY status = 'airing' DESC, air_date DESC
        LIMIT %s OFFSET %s
    """
    items = query(sql, (f"%{genre}%", limit, offset))

    count = query_one(
        "SELECT COUNT(*) as total FROM dramas WHERE genre LIKE %s",
        (f"%{genre}%",)
    )

    return success({
        'list': items,
        'total': count['total'] if count else 0,
        'page': page,
        'genre': genre
    })


@search_bp.route('/discover/by-year', methods=['GET'])
def by_year():
    """按年份浏览"""
    year = request.args.get('year', '')
    limit = min(int(request.args.get('limit', 20)), 50)
    page = max(int(request.args.get('page', 1)), 1)
    offset = (page - 1) * limit

    if not year:
        return success({'list': [], 'total': 0})

    sql = """
        SELECT id, title, type, genre, poster_url, douban_score,
               status, air_date
        FROM dramas
        WHERE YEAR(air_date) = %s
        ORDER BY air_date DESC
        LIMIT %s OFFSET %s
    """
    items = query(sql, (year, limit, offset))
    return success({'list': items, 'page': page, 'year': year})


@search_bp.route('/discover/by-actor', methods=['GET'])
def by_actor():
    """按演员浏览"""
    actor = request.args.get('actor_name', '').strip()
    if not actor:
        return success({'list': []})

    sql = """
        SELECT id, title, type, genre, poster_url, douban_score,
               status, air_date, cast_main
        FROM dramas
        WHERE cast_main LIKE %s
        ORDER BY air_date DESC
        LIMIT 30
    """
    items = query(sql, (f"%{actor}%",))
    return success({'list': items, 'actor': actor})


@search_bp.route('/discover/high-rated', methods=['GET'])
def high_rated():
    """高分推荐"""
    cache_key = "discover:high_rated"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    sql = """
        SELECT id, title, type, genre, poster_url, douban_score,
               douban_votes, status, air_date
        FROM dramas
        WHERE douban_score >= 8.0 AND douban_votes >= 1000
        ORDER BY douban_score DESC, douban_votes DESC
        LIMIT 30
    """
    items = query(sql)
    cache_set(cache_key, items, expire=3600)
    return success(items)


@search_bp.route('/discover/hidden-gems', methods=['GET'])
def hidden_gems():
    """冷门佳作"""
    cache_key = "discover:hidden_gems"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    sql = """
        SELECT id, title, type, genre, poster_url, douban_score,
               douban_votes, status, air_date
        FROM dramas
        WHERE douban_score >= 7.5 AND douban_votes BETWEEN 100 AND 5000
        ORDER BY douban_score DESC
        LIMIT 20
    """
    items = query(sql)
    cache_set(cache_key, items, expire=3600)
    return success(items)
