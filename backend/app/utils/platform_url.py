"""
平台 URL 解析与归一化

支持从各种格式的 URL / 原始 ID 中提取标准的 platform_drama_id，
并生成爬虫统一使用的 platform_url。
"""

import re
from urllib.parse import urlparse


# 各平台 URL 匹配规则
# value = (从 URL 提取 ID 的正则, 由 ID 生成标准 URL 的模板)
_RULES = {
    'tencent': (
        [
            re.compile(r'/cover/([a-z0-9]+)\.html', re.I),
            re.compile(r'/x/cover/([a-z0-9]+)', re.I),
        ],
        'https://m.v.qq.com/x/cover/{id}.html',
    ),
    'iqiyi': (
        [
            re.compile(r'/([av]_[a-z0-9]+)\.html', re.I),      # /v_xxx.html 或 /a_xxx.html
            re.compile(r'/(v_[a-z0-9]+|a_[a-z0-9]+)(?:$|[?#])', re.I),
        ],
        'https://www.iqiyi.com/{id}.html',
    ),
    'youku': (
        [
            re.compile(r'/v_show/id_([a-zA-Z0-9=]+)\.html', re.I),
            re.compile(r'/alipay_video/id_([a-zA-Z0-9=]+)\.html', re.I),
            re.compile(r'/video\?vid=([a-zA-Z0-9=]+)', re.I),
        ],
        'https://v.youku.com/v_show/id_{id}.html',
    ),
    'mgtv': (
        [
            re.compile(r'/b/(\d+)/(\d+)\.html', re.I),           # /b/{partId}/{clipId}.html
        ],
        'https://www.mgtv.com/b/{id}.html',  # id 会是 "{partId}/{clipId}"
    ),
}


# 平台 short_name 别名表（容错用户输入）
PLATFORM_ALIASES = {
    'tencent': 'tencent', '腾讯': 'tencent', '腾讯视频': 'tencent', 'qq': 'tencent', 'tx': 'tencent',
    'iqiyi':   'iqiyi',   '爱奇艺': 'iqiyi',   'iq': 'iqiyi',
    'youku':   'youku',   '优酷':   'youku',   'yk': 'youku',
    'mgtv':    'mgtv',    '芒果':   'mgtv',    '芒果tv': 'mgtv', '芒果TV': 'mgtv', 'mango': 'mgtv',
}


def normalize_platform(name):
    """把平台名/别名统一成 short_name"""
    if not name:
        return None
    return PLATFORM_ALIASES.get(str(name).strip().lower())


def parse_platform_input(platform, raw):
    """
    解析用户输入（可能是完整 URL，也可能是裸 ID）
    返回 (platform_drama_id, platform_url) 或 (None, None) 表示无法解析

    支持的输入格式（以爱奇艺为例）:
        https://www.iqiyi.com/v_pz64qf5dtk.html                 → id=v_pz64qf5dtk
        http://m.iqiyi.com/v_pz64qf5dtk.html                    → id=v_pz64qf5dtk
        https://www.iqiyi.com/v_pz64qf5dtk.html?vfrm=pcw_home   → id=v_pz64qf5dtk
        v_pz64qf5dtk                                             → id=v_pz64qf5dtk
        pz64qf5dtk                                               → id=v_pz64qf5dtk (兜底加 v_ 前缀)
    """
    platform = normalize_platform(platform)
    if not platform or platform not in _RULES:
        return None, None

    raw = (raw or '').strip()
    if not raw:
        return None, None

    patterns, url_tpl = _RULES[platform]

    # 情况 1：完整 URL
    if raw.startswith('http://') or raw.startswith('https://'):
        for pat in patterns:
            m = pat.search(raw)
            if m:
                if platform == 'mgtv' and len(m.groups()) == 2:
                    drama_id = f"{m.group(1)}/{m.group(2)}"
                else:
                    drama_id = m.group(1)
                url = url_tpl.format(id=drama_id)
                return drama_id, url
        return None, None

    # 情况 2：看起来像路径片段（包含斜杠或关键前缀）
    if '/' in raw:
        # 芒果 TV 的 {partId}/{clipId} 形式
        if platform == 'mgtv' and re.fullmatch(r'\d+/\d+', raw):
            return raw, url_tpl.format(id=raw)
        # 其他平台不支持含斜杠的裸 ID
        return None, None

    # 情况 3：裸 ID，按平台做格式兜底
    if platform == 'tencent':
        # 腾讯 cid 全部小写字母+数字
        if re.fullmatch(r'[a-z0-9]{8,}', raw, re.I):
            return raw.lower(), url_tpl.format(id=raw.lower())
        return None, None

    if platform == 'iqiyi':
        # 爱奇艺短码
        if raw.startswith(('v_', 'a_')):
            return raw, url_tpl.format(id=raw)
        # 兜底：加 v_ 前缀
        if re.fullmatch(r'[a-z0-9]{6,}', raw, re.I):
            fixed = f"v_{raw}"
            return fixed, url_tpl.format(id=fixed)
        return None, None

    if platform == 'youku':
        # 优酷 showid 形如 XMTgyMDM5NTEyMA== 或十六进制串
        if re.fullmatch(r'[a-zA-Z0-9=]{12,}', raw):
            return raw, url_tpl.format(id=raw)
        return None, None

    if platform == 'mgtv':
        # 芒果 TV 需要 partId/clipId 两段
        return None, None

    return None, None


def parse_multi(inputs):
    """
    批量解析：给定 {'tencent': 'xxx', 'iqiyi': 'yyy', ...} 字典
    返回 [(short_name, platform_drama_id, platform_url), ...] 只包含解析成功的
    以及 errors（解析失败的平台）列表
    """
    results = []
    errors = []
    for platform, raw in inputs.items():
        if not raw:
            continue
        drama_id, url = parse_platform_input(platform, raw)
        if drama_id:
            results.append((normalize_platform(platform), drama_id, url))
        else:
            errors.append(f"{platform}: 无法识别 {raw!r}")
    return results, errors
