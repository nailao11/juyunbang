from datetime import datetime, timedelta
from loguru import logger

from app.utils.db import query, query_one, execute


def calculate_drama_index(stat_date=None):
    """计算剧力指数"""
    if stat_date is None:
        stat_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    logger.info(f"开始计算 {stat_date} 剧力指数...")

    # 获取权重配置
    weights = _get_weights()

    # 获取所有在播剧集
    dramas = query(
        "SELECT id, douban_score FROM dramas WHERE status = 'airing'"
    )

    if not dramas:
        logger.warning("没有在播剧集，跳过剧力指数计算")
        return

    # 计算各维度得分
    heat_scores = _calc_heat_scores(stat_date)
    social_scores = _calc_social_scores(stat_date)
    play_scores = _calc_play_scores(stat_date)

    results = []
    for drama in dramas:
        did = drama['id']

        # 热度维度得分
        index_heat = heat_scores.get(did, 0)

        # 讨论度维度得分
        index_social = social_scores.get(did, 0)

        # 播放表现维度得分
        index_play = play_scores.get(did, 0)

        # 口碑维度得分
        douban = drama.get('douban_score')
        index_reputation = float(douban) * 10 if douban else 50  # 未评分取50

        # 综合指数
        index_total = (
            index_heat * weights['heat'] +
            index_social * weights['social'] +
            index_play * weights['play'] +
            index_reputation * weights['reputation']
        )
        index_total = round(min(100, max(0, index_total)), 2)

        results.append({
            'drama_id': did,
            'index_total': index_total,
            'index_heat': round(index_heat, 2),
            'index_social': round(index_social, 2),
            'index_playcount': round(index_play, 2),
            'index_reputation': round(index_reputation, 2)
        })

    # 按总分排序并写入数据库
    results.sort(key=lambda x: x['index_total'], reverse=True)

    # 获取前一天的排名用于计算变化
    prev_ranks = {}
    prev_data = query(
        "SELECT drama_id, rank_total FROM drama_index_daily "
        "WHERE stat_date = DATE_SUB(%s, INTERVAL 1 DAY)",
        (stat_date,)
    )
    for p in prev_data:
        prev_ranks[p['drama_id']] = p['rank_total']

    for rank, item in enumerate(results, 1):
        prev_rank = prev_ranks.get(item['drama_id'])
        rank_change = (prev_rank - rank) if prev_rank else 0

        execute(
            "INSERT INTO drama_index_daily "
            "(drama_id, stat_date, index_total, index_heat, index_social, "
            "index_playcount, index_reputation, rank_total, rank_change) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "index_total=VALUES(index_total), index_heat=VALUES(index_heat), "
            "index_social=VALUES(index_social), index_playcount=VALUES(index_playcount), "
            "index_reputation=VALUES(index_reputation), rank_total=VALUES(rank_total), "
            "rank_change=VALUES(rank_change)",
            (item['drama_id'], stat_date, item['index_total'],
             item['index_heat'], item['index_social'],
             item['index_playcount'], item['index_reputation'],
             rank, rank_change)
        )

    logger.info(f"{stat_date} 剧力指数计算完成，共{len(results)}部剧")


def _get_weights():
    """获取权重配置"""
    from app.utils.db import query_one
    w = {}
    for key, field in [('heat', 'index_weight_heat'), ('social', 'index_weight_social'),
                       ('play', 'index_weight_play'), ('reputation', 'index_weight_reputation')]:
        row = query_one("SELECT config_value FROM system_config WHERE config_key = %s", (field,))
        w[key] = float(row['config_value']) if row else 0.25
    return w


def _calc_heat_scores(stat_date):
    """计算热度维度得分（标准化到0-100）"""
    data = query(
        "SELECT drama_id, AVG(heat_avg) as avg_heat "
        "FROM heat_daily WHERE stat_date = %s GROUP BY drama_id",
        (stat_date,)
    )
    if not data:
        return {}

    values = [float(d['avg_heat']) for d in data if d['avg_heat']]
    if not values:
        return {}

    min_v, max_v = min(values), max(values)
    range_v = max_v - min_v if max_v > min_v else 1

    scores = {}
    for d in data:
        if d['avg_heat']:
            scores[d['drama_id']] = (float(d['avg_heat']) - min_v) / range_v * 100
        else:
            scores[d['drama_id']] = 0
    return scores


def _calc_social_scores(stat_date):
    """计算讨论度维度得分"""
    data = query(
        "SELECT drama_id, "
        "COALESCE(weibo_topic_read_incr, 0) as weibo, "
        "COALESCE(douyin_topic_views_incr, 0) as douyin, "
        "COALESCE(baidu_index, 0) as baidu "
        "FROM social_daily WHERE stat_date = %s",
        (stat_date,)
    )
    if not data:
        return {}

    # 加权社交总分
    social_totals = {}
    for d in data:
        total = float(d['weibo']) * 0.4 + float(d['douyin']) * 0.3 + float(d['baidu']) * 10000 * 0.3
        social_totals[d['drama_id']] = total

    if not social_totals:
        return {}

    max_v = max(social_totals.values()) or 1
    return {did: (v / max_v * 100) for did, v in social_totals.items()}


def _calc_play_scores(stat_date):
    """计算播放表现维度得分（排名百分位）"""
    data = query(
        "SELECT drama_id, SUM(daily_increment) as total_play "
        "FROM playcount_daily WHERE stat_date = %s "
        "GROUP BY drama_id ORDER BY total_play DESC",
        (stat_date,)
    )
    if not data:
        return {}

    total = len(data)
    scores = {}
    for i, d in enumerate(data):
        # 百分位排名：排名第1得100分
        scores[d['drama_id']] = (1 - i / max(total, 1)) * 100

    return scores
