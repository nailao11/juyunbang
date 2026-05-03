"""
平台 URL 解析与归一化（仅接受完整页面链接，不再支持裸 ID）

支持的录入格式：
    腾讯视频    https://m.v.qq.com/x/m/play?cid=mzc002007tp60ap&vid=w41025my54z
    爱奇艺      https://www.iqiyi.com/a_1euk1nkfz9l.html      （只支持 a_ 专辑页）
    优酷        https://v.youku.com/v_show/id_xxxxxxxxxx.html
    芒果TV      https://www.mgtv.com/b/{partId}/{clipId}.html

任何不带 http(s):// 前缀、或不能匹配上述模式的输入，一律拒绝并提示用户填写完整页面链接。
"""

import re
from urllib.parse import urlparse, parse_qs


# 平台 short_name 别名表（容错用户输入；统一映射到 platforms 表的 short_name）
PLATFORM_ALIASES = {
    'tencent': 'tencent', '腾讯': 'tencent', '腾讯视频': 'tencent', 'qq': 'tencent', 'tx': 'tencent',
    'iqiyi':   'iqiyi',   '爱奇艺': 'iqiyi',   'iq': 'iqiyi',
    'youku':   'youku',   '优酷':   'youku',   'yk': 'youku',
    'mgtv':    'mgtv',    '芒果':   'mgtv',    '芒果tv': 'mgtv', '芒果TV': 'mgtv', 'mango': 'mgtv',
}


_TENCENT_HOST_RE = re.compile(r'^(m\.)?v\.qq\.com$', re.I)
_IQIYI_ALBUM_RE  = re.compile(r'^/(a_[a-z0-9]+)\.html$', re.I)
_YOUKU_PATH_RE   = re.compile(r'^/v_show/id_([a-zA-Z0-9=]+)\.html$', re.I)
_MGTV_PATH_RE    = re.compile(r'^/b/(\d+)/(\d+)\.html$', re.I)
_ID_TOKEN_RE     = re.compile(r'^[a-z0-9]{4,}$', re.I)


def normalize_platform(name):
    """把平台名/别名统一成 short_name；非法返回 None。"""
    if not name:
        return None
    return PLATFORM_ALIASES.get(str(name).strip().lower())


def parse_platform_input(platform, raw):
    """
    解析用户输入的完整页面链接 → (platform_drama_id, platform_url)
    若无法识别返回 (None, None)；裸 ID / 残缺 URL 一律拒绝。
    """
    platform = normalize_platform(platform)
    raw = (raw or '').strip()
    if not platform or not raw:
        return None, None

    # 必须是完整 URL
    if not (raw.startswith('http://') or raw.startswith('https://')):
        return None, None

    try:
        parsed = urlparse(raw)
    except (ValueError, TypeError):
        return None, None

    host = (parsed.netloc or '').lower()
    path = parsed.path or ''

    if platform == 'tencent':
        # 腾讯：必须是 m.v.qq.com/x/m/play?cid=...&vid=...
        if not _TENCENT_HOST_RE.match(host):
            return None, None
        if not path.startswith('/x/m/play'):
            return None, None
        qs = parse_qs(parsed.query or '')
        cid = (qs.get('cid') or [''])[0].strip()
        vid = (qs.get('vid') or [''])[0].strip()
        if not (cid and vid):
            return None, None
        if not (_ID_TOKEN_RE.match(cid) and _ID_TOKEN_RE.match(vid)):
            return None, None
        cid, vid = cid.lower(), vid.lower()
        url = f'https://m.v.qq.com/x/m/play?cid={cid}&vid={vid}'
        return f'{cid}:{vid}', url

    if platform == 'iqiyi':
        # 爱奇艺：仅支持 PC 专辑页 https://www.iqiyi.com/a_xxx.html
        if 'iqiyi.com' not in host:
            return None, None
        m = _IQIYI_ALBUM_RE.match(path)
        if not m:
            return None, None
        album_id = m.group(1).lower()
        return album_id, f'https://www.iqiyi.com/{album_id}.html'

    if platform == 'youku':
        # 优酷：完整播放页 https://v.youku.com/v_show/id_xxx.html
        if 'youku.com' not in host:
            return None, None
        m = _YOUKU_PATH_RE.match(path)
        if not m:
            return None, None
        show_id = m.group(1)
        return show_id, f'https://v.youku.com/v_show/id_{show_id}.html'

    if platform == 'mgtv':
        # 芒果：完整剧集页 https://www.mgtv.com/b/{partId}/{clipId}.html
        if 'mgtv.com' not in host:
            return None, None
        m = _MGTV_PATH_RE.match(path)
        if not m:
            return None, None
        part_id, clip_id = m.group(1), m.group(2)
        return f'{part_id}/{clip_id}', f'https://www.mgtv.com/b/{part_id}/{clip_id}.html'

    return None, None


def parse_multi(inputs):
    """
    批量解析：{'tencent': 'xxx', 'iqiyi': 'yyy', ...} → ([(short_name, drama_id, url), ...], errors)
    所有解析失败的平台都会进 errors，提示用户填写完整页面链接。
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
            errors.append(f"{platform}: 请填写完整页面链接")
    return results, errors
