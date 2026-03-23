from flask import Blueprint, request

from ..utils.db import query, query_one, execute
from ..utils.cache import cache_get, cache_set
from ..utils.response import success, error

news_bp = Blueprint('news', __name__)


@news_bp.route('/list', methods=['GET'])
def news_list():
    """资讯列表"""
    category = request.args.get('category', '')
    limit = min(int(request.args.get('limit', 20)), 50)
    page = max(int(request.args.get('page', 1)), 1)
    offset = (page - 1) * limit

    where_clauses = ["is_published = 1"]
    params = []

    if category:
        where_clauses.append("category = %s")
        params.append(category)

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT id, title, summary, cover_url, source, category,
               view_count, published_at
        FROM news
        WHERE {where_sql}
        ORDER BY published_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    items = query(sql, tuple(params))

    count = query_one(f"SELECT COUNT(*) as total FROM news WHERE {where_sql}", tuple(params[:-2]))

    return success({
        'list': items,
        'total': count['total'] if count else 0,
        'page': page
    })


@news_bp.route('/<int:news_id>', methods=['GET'])
def news_detail(news_id):
    """资讯详情"""
    item = query_one(
        "SELECT * FROM news WHERE id = %s AND is_published = 1",
        (news_id,)
    )
    if not item:
        return error('资讯不存在', 404)

    # 增加阅读量
    execute("UPDATE news SET view_count = view_count + 1 WHERE id = %s", (news_id,))

    return success(item)


@news_bp.route('/report/daily-brief', methods=['GET'])
def daily_brief():
    """每日数据简报"""
    cache_key = "news:daily_brief"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    report = query_one(
        "SELECT * FROM daily_report "
        "WHERE report_type = 'daily' AND published_at IS NOT NULL "
        "ORDER BY report_date DESC LIMIT 1"
    )

    if report:
        cache_set(cache_key, report, expire=1800)

    return success(report)
