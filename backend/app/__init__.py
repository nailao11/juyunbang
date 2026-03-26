from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from loguru import logger

from .config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 跨域支持（微信小程序请求不受CORS限制，此处为开发调试用）
    CORS(app, resources={r"/api/*": {"origins": ["https://servicewechat.com", "https://sqnl8.cn"]}})

    # JWT认证
    JWTManager(app)

    # 日志配置
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level="INFO",
        encoding="utf-8"
    )

    # 注册蓝图
    from .routes.auth import auth_bp
    from .routes.heat import heat_bp
    from .routes.daily import daily_bp
    from .routes.weekly import weekly_bp
    from .routes.drama import drama_bp
    from .routes.search import search_bp
    from .routes.tracking import tracking_bp
    from .routes.notes import notes_bp
    from .routes.news import news_bp
    from .routes.system import system_bp

    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(heat_bp, url_prefix='/api/v1/heat')
    app.register_blueprint(daily_bp, url_prefix='/api/v1/daily')
    app.register_blueprint(weekly_bp, url_prefix='/api/v1/weekly')
    app.register_blueprint(drama_bp, url_prefix='/api/v1/drama')
    app.register_blueprint(search_bp, url_prefix='/api/v1/search')
    app.register_blueprint(tracking_bp, url_prefix='/api/v1/tracking')
    app.register_blueprint(notes_bp, url_prefix='/api/v1/notes')
    app.register_blueprint(news_bp, url_prefix='/api/v1/news')
    app.register_blueprint(system_bp, url_prefix='/api/v1/system')

    # 健康检查
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'juyunbang-api'}

    @app.route('/api/v1/test')
    def test():
        return {'code': 200, 'message': 'API服务运行正常', 'data': None}

    return app
