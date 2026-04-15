"""请求参数安全解析工具。

处理 HTTP 查询参数的类型转换，避免客户端传入非数字字符串时
`int(request.args.get(...))` 直接抛出 ValueError 导致 500。
"""
from flask import request


def get_int_arg(name, default, min_val=None, max_val=None):
    """从 request.args 中安全读取整数参数。

    - 参数不存在或非数字时，返回 default
    - 若提供 min_val / max_val，则结果会被 clamp 到该闭区间
    """
    raw = request.args.get(name)
    if raw is None or raw == '':
        value = default
    else:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = default

    if min_val is not None and value < min_val:
        value = min_val
    if max_val is not None and value > max_val:
        value = max_val
    return value
