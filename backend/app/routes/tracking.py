from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..utils.db import query, query_one, insert, execute
from ..utils.response import success, error

tracking_bp = Blueprint('tracking', __name__)


@tracking_bp.route('/list', methods=['GET'])
@jwt_required()
def tracking_list():
    """获取我的追剧列表"""
    user_id = get_jwt_identity()
    status = request.args.get('status', '')

    where_clauses = ["ut.user_id = %s"]
    params = [user_id]

    if status:
        where_clauses.append("ut.status = %s")
        params.append(status)

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT d.id, d.title, d.type, d.poster_url, d.douban_score,
               d.status as drama_status, d.current_episode, d.total_episodes,
               ut.status as tracking_status, ut.current_episode as my_episode,
               ut.user_score, ut.user_comment, ut.started_at, ut.finished_at,
               ut.updated_at
        FROM user_tracking ut
        JOIN dramas d ON ut.drama_id = d.id
        WHERE {where_sql}
        ORDER BY ut.updated_at DESC
    """
    items = query(sql, tuple(params))
    return success(items)


@tracking_bp.route('/status/<int:drama_id>', methods=['GET'])
@jwt_required()
def tracking_status(drama_id):
    """获取某剧的追剧状态"""
    user_id = get_jwt_identity()
    record = query_one(
        "SELECT status, current_episode, user_score, started_at, updated_at "
        "FROM user_tracking WHERE user_id = %s AND drama_id = %s",
        (user_id, drama_id)
    )
    if not record:
        return success({'status': '', 'tracked': False})
    record['tracked'] = True
    return success(record)


@tracking_bp.route('/expect/<int:drama_id>', methods=['POST'])
@jwt_required()
def expect_add(drama_id):
    """期待待播剧"""
    user_id = get_jwt_identity()
    existing = query_one(
        "SELECT id FROM user_tracking WHERE user_id = %s AND drama_id = %s",
        (user_id, drama_id)
    )
    if existing:
        execute(
            "UPDATE user_tracking SET status = 'want_to_watch', updated_at = NOW() "
            "WHERE user_id = %s AND drama_id = %s",
            (user_id, drama_id)
        )
    else:
        insert(
            "INSERT INTO user_tracking (user_id, drama_id, status, started_at) "
            "VALUES (%s, %s, 'want_to_watch', CURDATE())",
            (user_id, drama_id)
        )
    return success(message='已加入期待')


@tracking_bp.route('/expect/<int:drama_id>', methods=['DELETE'])
@jwt_required()
def expect_remove(drama_id):
    """取消期待"""
    user_id = get_jwt_identity()
    execute(
        "DELETE FROM user_tracking WHERE user_id = %s AND drama_id = %s AND status = 'want_to_watch'",
        (user_id, drama_id)
    )
    return success(message='已取消期待')


@tracking_bp.route('/add', methods=['POST'])
@jwt_required()
def tracking_add():
    """添加追剧"""
    user_id = get_jwt_identity()
    data = request.get_json()
    drama_id = data.get('drama_id')
    status = data.get('status', 'watching')

    if not drama_id:
        return error('缺少剧集ID', 400)

    # 检查是否已存在
    existing = query_one(
        "SELECT id FROM user_tracking WHERE user_id = %s AND drama_id = %s",
        (user_id, drama_id)
    )
    if existing:
        execute(
            "UPDATE user_tracking SET status = %s, updated_at = NOW() "
            "WHERE user_id = %s AND drama_id = %s",
            (status, user_id, drama_id)
        )
        return success(message='追剧状态已更新')

    insert(
        "INSERT INTO user_tracking (user_id, drama_id, status, started_at) "
        "VALUES (%s, %s, %s, CURDATE())",
        (user_id, drama_id, status)
    )
    return success(message='已添加到追剧列表')


@tracking_bp.route('/<int:drama_id>', methods=['PUT'])
@jwt_required()
def tracking_update(drama_id):
    """更新追剧状态"""
    user_id = get_jwt_identity()
    data = request.get_json()

    updates = []
    params = []

    for field in ['status', 'current_episode', 'user_score', 'user_comment']:
        if field in data:
            updates.append(f"{field} = %s")
            params.append(data[field])

    if data.get('status') == 'watched':
        updates.append("finished_at = CURDATE()")

    if not updates:
        return error('没有可更新的内容', 400)

    params.extend([user_id, drama_id])
    sql = f"UPDATE user_tracking SET {', '.join(updates)}, updated_at = NOW() " \
          f"WHERE user_id = %s AND drama_id = %s"
    affected = execute(sql, tuple(params))

    if affected == 0:
        return error('追剧记录不存在', 404)

    return success(message='更新成功')


@tracking_bp.route('/<int:drama_id>', methods=['DELETE'])
@jwt_required()
def tracking_delete(drama_id):
    """移除追剧"""
    user_id = get_jwt_identity()
    affected = execute(
        "DELETE FROM user_tracking WHERE user_id = %s AND drama_id = %s",
        (user_id, drama_id)
    )
    if affected == 0:
        return error('追剧记录不存在', 404)
    return success(message='已从追剧列表移除')


@tracking_bp.route('/stats', methods=['GET'])
@jwt_required()
def tracking_stats():
    """追剧统计"""
    user_id = get_jwt_identity()

    stats = query_one(
        "SELECT "
        "COUNT(*) as total, "
        "COUNT(CASE WHEN status='watching' THEN 1 END) as watching, "
        "COUNT(CASE WHEN status='want_to_watch' THEN 1 END) as want_to_watch, "
        "COUNT(CASE WHEN status='watched' THEN 1 END) as watched, "
        "COUNT(CASE WHEN status='dropped' THEN 1 END) as dropped, "
        "SUM(current_episode) as total_episodes_watched "
        "FROM user_tracking WHERE user_id = %s",
        (user_id,)
    )

    # 估算观看时长（假设每集45分钟）
    total_eps = int(stats['total_episodes_watched'] or 0)
    stats['estimated_hours'] = round(total_eps * 45 / 60, 1)

    return success(stats)


@tracking_bp.route('/report/monthly', methods=['GET'])
@jwt_required()
def monthly_report():
    """月度追剧报告"""
    user_id = get_jwt_identity()
    month = request.args.get('month', '')

    if not month:
        from datetime import datetime
        month = datetime.now().strftime('%Y-%m')

    # 本月新追的剧
    new_tracking = query(
        "SELECT d.title, ut.status, ut.started_at "
        "FROM user_tracking ut "
        "JOIN dramas d ON ut.drama_id = d.id "
        "WHERE ut.user_id = %s AND DATE_FORMAT(ut.started_at, '%%Y-%%m') = %s",
        (user_id, month)
    )

    # 本月完成的剧
    finished = query(
        "SELECT d.title, ut.user_score, ut.finished_at "
        "FROM user_tracking ut "
        "JOIN dramas d ON ut.drama_id = d.id "
        "WHERE ut.user_id = %s AND DATE_FORMAT(ut.finished_at, '%%Y-%%m') = %s",
        (user_id, month)
    )

    # 本月弃剧
    dropped = query(
        "SELECT d.title FROM user_tracking ut "
        "JOIN dramas d ON ut.drama_id = d.id "
        "WHERE ut.user_id = %s AND ut.status = 'dropped' "
        "AND DATE_FORMAT(ut.updated_at, '%%Y-%%m') = %s",
        (user_id, month)
    )

    return success({
        'month': month,
        'new_tracking': new_tracking,
        'finished': finished,
        'dropped': dropped,
        'new_count': len(new_tracking),
        'finished_count': len(finished),
        'dropped_count': len(dropped)
    })
