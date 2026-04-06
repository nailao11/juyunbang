from flask import jsonify
import time


def success(data=None, message='success'):
    return jsonify({
        'code': 200,
        'message': message,
        'data': data,
        'timestamp': int(time.time())
    })


def error(message='服务器错误', code=500):
    return jsonify({
        'code': code,
        'message': message,
        'data': None,
        'timestamp': int(time.time())
    }), code if code >= 400 else 200


