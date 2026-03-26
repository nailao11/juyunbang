"""Flask扩展初始化"""
from flask_cors import CORS
from flask_jwt_extended import JWTManager

cors = CORS()
jwt = JWTManager()


def init_extensions(app):
    """初始化所有Flask扩展"""
    cors.init_app(app, resources={r"/api/*": {"origins": ["https://servicewechat.com", "https://sqnl8.cn"]}})
    jwt.init_app(app)
