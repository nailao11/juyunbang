import qiniu
from loguru import logger

from ..config import Config


def get_upload_token(key=None):
    auth = qiniu.Auth(Config.QINIU_ACCESS_KEY, Config.QINIU_SECRET_KEY)
    policy = {
        'returnBody': '{"key": $(key), "hash": $(etag), "url": "%s/$(key)"}' % Config.QINIU_DOMAIN
    }
    if key:
        token = auth.upload_token(Config.QINIU_BUCKET, key, 3600, policy)
    else:
        token = auth.upload_token(Config.QINIU_BUCKET, expires=3600, policy=policy)
    return token


def upload_file(local_path, key):
    auth = qiniu.Auth(Config.QINIU_ACCESS_KEY, Config.QINIU_SECRET_KEY)
    token = auth.upload_token(Config.QINIU_BUCKET, key, 3600)

    ret, info = qiniu.put_file(token, key, local_path)
    if ret and ret.get('key') == key:
        url = f"https://{Config.QINIU_DOMAIN}/{key}"
        logger.info(f"七牛云上传成功: {url}")
        return url
    else:
        logger.error(f"七牛云上传失败: {info}")
        return None


def upload_data(data, key):
    auth = qiniu.Auth(Config.QINIU_ACCESS_KEY, Config.QINIU_SECRET_KEY)
    token = auth.upload_token(Config.QINIU_BUCKET, key, 3600)

    ret, info = qiniu.put_data(token, key, data)
    if ret and ret.get('key') == key:
        url = f"https://{Config.QINIU_DOMAIN}/{key}"
        return url
    else:
        logger.error(f"七牛云上传失败: {info}")
        return None


def get_file_url(key):
    return f"https://{Config.QINIU_DOMAIN}/{key}"


def upload_flask_file(file_storage, prefix='uploads'):
    """上传Flask FileStorage对象到七牛云"""
    import uuid
    import os
    ext = os.path.splitext(file_storage.filename)[1] or '.jpg'
    key = f"{prefix}/{uuid.uuid4().hex}{ext}"
    data = file_storage.read()
    return upload_data(data, key)
