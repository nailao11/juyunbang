import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

    # MySQL
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_NAME = os.getenv('DB_NAME', 'juyunbang')
    DB_USER = os.getenv('DB_USER', 'juyunbang')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')

    # Redis
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))

    # 微信小程序
    WX_APPID = os.getenv('WX_APPID', '')
    WX_SECRET = os.getenv('WX_SECRET', '')

    # 七牛云
    QINIU_ACCESS_KEY = os.getenv('QINIU_ACCESS_KEY', '')
    QINIU_SECRET_KEY = os.getenv('QINIU_SECRET_KEY', '')
    QINIU_BUCKET = os.getenv('QINIU_BUCKET', 'juyunbang')
    QINIU_DOMAIN = os.getenv('QINIU_DOMAIN', '')

    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 86400))
    )
