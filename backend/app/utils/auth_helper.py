"""认证辅助工具"""
import requests
from flask import current_app
from loguru import logger


def wx_code_to_openid(code):
    """
    用微信登录code换取openid和session_key。
    返回 dict {'openid': ..., 'session_key': ...} 或 None。
    """
    appid = current_app.config.get('WX_APPID', '')
    secret = current_app.config.get('WX_SECRET', '')

    if not appid or not secret:
        logger.warning("WX_APPID 或 WX_SECRET 未配置，跳过微信登录验证")
        return None

    url = 'https://api.weixin.qq.com/sns/jscode2session'
    params = {
        'appid': appid,
        'secret': secret,
        'js_code': code,
        'grant_type': 'authorization_code'
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
    except Exception as e:
        logger.error(f"微信 code2session 请求失败: {e}")
        return None

    if 'openid' not in data:
        logger.error(f"微信登录失败，返回: {data}")
        return None

    return {
        'openid': data['openid'],
        'session_key': data.get('session_key', ''),
        'unionid': data.get('unionid'),
    }


def get_current_user_id():
    """从JWT中获取当前用户ID"""
    from flask_jwt_extended import get_jwt_identity
    try:
        return get_jwt_identity()
    except Exception:
        return None
