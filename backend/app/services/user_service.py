"""用户业务逻辑"""
import requests
from flask import current_app
from loguru import logger


class UserService:
    @staticmethod
    def wx_login(code):
        """微信登录：用code换取openid，创建或更新用户"""
        appid = current_app.config.get('WX_APPID', '')
        secret = current_app.config.get('WX_SECRET', '')

        if not appid or not secret:
            logger.warning("WX_APPID 或 WX_SECRET 未配置")
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
            logger.error(f"微信登录请求失败: {e}")
            return None

        openid = data.get('openid')
        if not openid:
            logger.error(f"微信登录失败: {data}")
            return None

        from app.models.user import UserModel
        user = UserModel.get_by_openid(openid)
        if user:
            UserModel.update_login_time(user['id'])
        else:
            user_id = UserModel.create(openid)
            user = UserModel.get_by_id(user_id)

        return user

    @staticmethod
    def get_profile(user_id):
        """获取用户资料"""
        from app.models.user import UserModel
        from app.models.tracking import TrackingModel

        user = UserModel.get_by_id(user_id)
        if not user:
            return None

        stats = TrackingModel.get_stats(user_id)
        user['tracking_stats'] = stats
        return user

    @staticmethod
    def update_profile(user_id, **kwargs):
        """更新用户资料"""
        from app.models.user import UserModel
        UserModel.update_profile(user_id, **kwargs)
