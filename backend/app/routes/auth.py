import requests
from flask import Blueprint, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from loguru import logger

from ..config import Config
from ..utils.db import query_one, insert, execute
from ..utils.response import success, error

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    """微信登录：小程序发送code，后端换取openid，返回JWT token"""
    data = request.get_json()
    code = data.get('code')

    if not code:
        return error('缺少登录code', 400)

    # 用code向微信服务器换取openid和session_key
    wx_url = 'https://api.weixin.qq.com/sns/jscode2session'
    params = {
        'appid': Config.WX_APPID,
        'secret': Config.WX_SECRET,
        'js_code': code,
        'grant_type': 'authorization_code'
    }

    try:
        resp = requests.get(wx_url, params=params, timeout=10)
        wx_data = resp.json()
    except Exception as e:
        logger.error(f"微信登录请求失败: {e}")
        return error('微信服务器请求失败', 500)

    if 'errcode' in wx_data and wx_data['errcode'] != 0:
        logger.error(f"微信登录失败: {wx_data}")
        return error('微信登录失败', 400)

    openid = wx_data.get('openid')
    if not openid:
        return error('获取openid失败', 400)

    # 查询或创建用户
    user = query_one("SELECT * FROM users WHERE openid = %s", (openid,))

    if user is None:
        user_id = insert(
            "INSERT INTO users (openid, last_login_at) VALUES (%s, NOW())",
            (openid,)
        )
    else:
        user_id = user['id']
        execute(
            "UPDATE users SET last_login_at = NOW() WHERE id = %s",
            (user_id,)
        )

    # 生成JWT token
    token = create_access_token(identity=str(user_id))

    return success({
        'token': token,
        'user_id': user_id,
        'is_new': user is None
    })


@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """获取用户信息"""
    user_id = get_jwt_identity()
    user = query_one(
        "SELECT id, nickname, avatar_url, gender, theme_mode, notify_enabled, "
        "created_at, last_login_at FROM users WHERE id = %s",
        (user_id,)
    )

    if not user:
        return error('用户不存在', 404)

    # 获取追剧统计
    stats = query_one(
        "SELECT "
        "COUNT(CASE WHEN status='watching' THEN 1 END) as watching_count, "
        "COUNT(CASE WHEN status='want_to_watch' THEN 1 END) as want_count, "
        "COUNT(CASE WHEN status='watched' THEN 1 END) as watched_count, "
        "COUNT(CASE WHEN status='dropped' THEN 1 END) as dropped_count "
        "FROM user_tracking WHERE user_id = %s",
        (user_id,)
    )

    user['stats'] = stats or {
        'watching_count': 0,
        'want_count': 0,
        'watched_count': 0,
        'dropped_count': 0
    }

    return success(user)


@auth_bp.route('/profile', methods=['PUT', 'POST'])
@jwt_required()
def update_profile():
    """更新用户信息"""
    user_id = get_jwt_identity()
    data = request.get_json()

    allowed_fields = ['nickname', 'avatar_url', 'gender', 'theme_mode', 'notify_enabled']
    updates = []
    params = []

    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = %s")
            params.append(data[field])

    if not updates:
        return error('没有可更新的字段', 400)

    params.append(user_id)
    sql = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
    execute(sql, tuple(params))

    return success(message='更新成功')


@auth_bp.route('/avatar', methods=['POST'])
@jwt_required()
def upload_avatar():
    """上传头像"""
    user_id = get_jwt_identity()

    if 'avatar' not in request.files:
        return error('未上传文件', 400)

    file = request.files['avatar']
    if not file.filename:
        return error('文件名为空', 400)

    # 尝试上传到七牛云
    try:
        from ..utils.qiniu_helper import upload_flask_file
        url = upload_flask_file(file, prefix='avatars')
        if url:
            execute(
                "UPDATE users SET avatar_url = %s WHERE id = %s",
                (url, user_id)
            )
            return success({'url': url}, message='头像更新成功')
    except Exception as e:
        logger.error(f"头像上传失败: {e}")

    return error('头像上传失败', 500)
