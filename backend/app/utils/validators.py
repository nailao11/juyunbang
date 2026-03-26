"""请求参数验证工具"""


def validate_required(data, fields):
    """
    验证必填字段。
    返回 (True, None) 或 (False, '缺少字段: xxx')。
    """
    if not data:
        return False, '请求数据为空'
    missing = [f for f in fields if not data.get(f)]
    if missing:
        return False, f"缺少必填字段: {', '.join(missing)}"
    return True, None


def validate_page_params(args):
    """
    从请求参数中提取并验证分页参数。
    返回 (page, page_size)，默认 page=1, page_size=20。
    """
    try:
        page = max(1, int(args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = min(100, max(1, int(args.get('page_size', 20))))
    except (ValueError, TypeError):
        page_size = 20
    return page, page_size


def validate_date(date_str):
    """
    验证日期字符串格式 YYYY-MM-DD。
    返回 date_str 或 None。
    """
    if not date_str:
        return None
    import re
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    return None


def validate_int(value, default=None, min_val=None, max_val=None):
    """
    验证整数参数。
    返回整数值或默认值。
    """
    try:
        v = int(value)
        if min_val is not None and v < min_val:
            return default
        if max_val is not None and v > max_val:
            return default
        return v
    except (ValueError, TypeError):
        return default


def sanitize_string(value, max_length=200):
    """
    清理字符串输入：去除首尾空白，限制长度。
    """
    if not value or not isinstance(value, str):
        return ''
    return value.strip()[:max_length]
