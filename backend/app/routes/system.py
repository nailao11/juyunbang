import json
import os

from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..utils.db import query, insert
from ..utils.cache import cache_get, cache_set
from ..utils.response import success
from ..utils.qiniu_helper import get_upload_token

system_bp = Blueprint('system', __name__)


@system_bp.route('/stats', methods=['GET'])
def system_stats():
    """数据概览统计（用于个人中心展示）"""
    cache_key = "system:stats"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    rows = query("SELECT COUNT(*) as cnt FROM dramas WHERE status = 'airing'")
    drama_count = rows[0]['cnt'] if rows else 0

    rows2 = query("SELECT COUNT(*) as cnt FROM platforms WHERE is_active = 1")
    platform_count = rows2[0]['cnt'] if rows2 else 4

    result = {'drama_count': drama_count, 'platform_count': platform_count}
    cache_set(cache_key, result, expire=300)
    return success(result)


@system_bp.route('/platforms', methods=['GET'])
def platform_list():
    """获取平台列表"""
    cache_key = "system:platforms"
    cached = cache_get(cache_key)
    if cached:
        return success(cached)

    items = query(
        "SELECT id, name, short_name, logo_url, color, sort_order "
        "FROM platforms WHERE is_active = 1 ORDER BY sort_order ASC"
    )
    cache_set(cache_key, items, expire=86400)
    return success(items)


@system_bp.route('/about', methods=['GET'])
def about():
    """关于我们"""
    return success({
        'name': '剧云榜',
        'version': '1.0.0',
        'description': '全平台剧集实时热度监控与数据分析工具',
        'features': [
            '实时热度排行 — 聚合各大视频平台热度数据',
            '播放量统计 — 日榜/周榜/月榜全覆盖',
            '剧力指数 — 独家综合评分体系',
            '追剧管理 — 记录你的观剧历程',
            '数据对比 — 多剧横向对比分析',
            '深色模式 — 护眼夜间浏览'
        ],
        'data_sources': '数据来源于各视频平台公开页面展示的信息',
        'contact': '通过小程序内"意见反馈"联系我们'
    })


@system_bp.route('/data-explanation', methods=['GET'])
def data_explanation():
    """数据说明"""
    return success({
        'sections': [
            {
                'title': '热度数据说明',
                'content': '热度数据直接采集自各视频平台官方公开展示的热度值，'
                           '包括爱奇艺内容热度、优酷热度值、腾讯视频站内热度、'
                           '芒果TV热度值等。数据每15分钟更新一次。'
            },
            {
                'title': '播放量数据说明',
                'content': '日播放增量 = 当日最后采集的累计播放量 - 前一日最后采集的累计播放量。'
                           '全网播放量 = 各平台播放量之和。数据次日15:00发布。'
            },
            {
                'title': '剧力指数说明',
                'content': '剧力指数（0-100分）是我们自研的综合评估模型，由四个维度加权计算：'
                           '平台热度（35%）+ 全网讨论度（25%）+ 播放表现（25%）+ 口碑评价（15%）。'
                           '详细计算方法请参阅完整数据说明页面。'
            },
            {
                'title': '数据更新频率',
                'content': '实时热度：每15分钟更新\n'
                           '社交媒体数据：每30分钟-1小时更新\n'
                           '日榜数据：次日15:00发布\n'
                           '周榜数据：每周一15:00发布\n'
                           '月榜数据：每月2日15:00发布'
            },
            {
                'title': '免责声明',
                'content': '1. 本小程序展示的数据均来源于各视频平台公开页面，仅供参考。\n'
                           '2. 各平台热度值采用各平台自有算法，本小程序仅做展示和聚合。\n'
                           '3. 剧力指数为本小程序自研模型，仅供娱乐参考，不构成商业决策依据。\n'
                           '4. 本小程序与各视频平台无任何关联，非任何平台的官方产品。\n'
                           '5. 如认为本小程序侵犯了您的权益，请通过反馈渠道联系我们。'
            }
        ]
    })


@system_bp.route('/disclaimer', methods=['GET'])
def disclaimer():
    """免责声明"""
    return success({
        'title': '免责声明',
        'content': (
            '1. 本小程序"剧云榜"展示的数据均来源于各视频平台公开页面展示的信息，'
            '仅供参考，不代表绝对准确的播放数据。\n\n'
            '2. 各平台热度值采用各平台自有的计算规则，'
            '本小程序仅做展示和聚合，不对热度值的计算方式负责。\n\n'
            '3. "剧力指数"为本小程序自研的综合评估模型，'
            '仅供娱乐参考，不构成任何商业决策依据。\n\n'
            '4. 本小程序与各视频平台、社交媒体平台无任何关联，'
            '非任何平台的官方产品。\n\n'
            '5. 如果您认为本小程序侵犯了您的权益，'
            '请通过反馈渠道联系我们，我们将及时处理。\n\n'
            '6. 本小程序保留随时修改、中断或终止服务的权利。'
        )
    })


@system_bp.route('/feedback', methods=['POST'])
@jwt_required()
def submit_feedback():
    """提交反馈"""
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    content = (data.get('content') or '').strip()
    contact = data.get('contact', '')
    feedback_type = data.get('type', 'suggestion')

    raw_images = data.get('images') or []
    if isinstance(raw_images, list):
        image_urls = [str(u) for u in raw_images if u]
    else:
        image_urls = []
    images_json = json.dumps(image_urls, ensure_ascii=False) if image_urls else None

    if not content:
        return success(message='反馈内容不能为空')

    insert(
        "INSERT INTO feedback (user_id, content, contact, type, images) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, content, contact, feedback_type, images_json)
    )

    return success(message='感谢您的反馈！')


@system_bp.route('/upload/image', methods=['POST'])
@jwt_required()
def upload_image():
    """上传图片"""
    if 'file' not in request.files:
        return success({'url': ''})

    file = request.files['file']
    if not file.filename:
        return success({'url': ''})

    try:
        from ..utils.qiniu_helper import upload_flask_file
        url = upload_flask_file(file, prefix='images')
        return success({'url': url or ''})
    except Exception as e:
        return success({'url': ''})


@system_bp.route('/upload-token', methods=['GET'])
@jwt_required()
def upload_token():
    """获取七牛云上传凭证"""
    token = get_upload_token()
    return success({'token': token, 'domain': 'https://' + os.getenv('QINIU_DOMAIN', '')})
