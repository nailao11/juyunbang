import re
import json
from loguru import logger

from .base_crawler import BaseCrawler


class MgtvCrawler(BaseCrawler):
    """
    芒果TV热度采集器
    策略优先级:
      1. 排行榜API（含热度参数）
      2. 排行榜HTML页面（解析嵌入数据）
      3. pianku列表API（备用）
    注意: 芒果TV网页版不直接展示热度值，需通过排行榜获取。
    """

    PLATFORM_ID = 4

    def __init__(self):
        super().__init__('芒果TV')

    def crawl(self):
        logger.info("[芒果TV] 开始采集热度数据...")
        results = []
        saved_count = 0

        try:
            tv_data = self._crawl_rank(channel_id='2', category='tv_drama')
            results.extend(tv_data)

            variety_data = self._crawl_rank(channel_id='3', category='variety')
            results.extend(variety_data)

            for item in results:
                drama_id = self._match_drama(
                    item['title'],
                    drama_type=item.get('category', 'tv_drama'),
                    poster_url=item.get('poster_url', ''),
                    is_finished=item.get('is_finished', False),
                )
                if drama_id and item.get('heat_value', 0) > 0:
                    try:
                        self.save_heat_data(
                            drama_id=drama_id,
                            platform_id=self.PLATFORM_ID,
                            heat_value=item['heat_value'],
                            heat_rank=item.get('rank'),
                        )
                        saved_count += 1
                    except Exception as e:
                        logger.error(f"[芒果TV] 保存失败 {item['title']}: {e}")

            self.log_task('mgtv_heat', 'success', saved_count)
            logger.info(f"[芒果TV] 采集完成，共{len(results)}条，保存热度{saved_count}条")

        except Exception as e:
            logger.error(f"[芒果TV] 采集异常: {e}")
            self.log_task('mgtv_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, channel_id='2', category='tv_drama'):
        # 方式1: 排行榜API
        items = self._fetch_rank_api(channel_id, category)
        if items:
            return items

        # 方式2: 排行页HTML
        items = self._fetch_rank_html(channel_id, category)
        if items:
            return items

        # 方式3: pianku列表API (多种排序)
        items = self._fetch_pianku(channel_id, category)
        return items

    # ----------------------------------------------------------------
    # 方式1: 排行榜API
    # ----------------------------------------------------------------
    def _fetch_rank_api(self, channel_id, category):
        """尝试多种芒果TV排行榜API"""

        # 排行榜API候选列表
        # 注意: pianku.api是片库API，热度字段永远为0
        # 真正的排行API在 top.bz.mgtv.com 域名下
        api_list = [
            # 芒果TV官方排行系统（最可能有真实热度）
            ('https://top.bz.mgtv.com/client/getHitList',
             {'channelId': channel_id, 'pageNo': '1', 'pageSize': '30'}),
            ('https://top.bz.mgtv.com/client/getTopList',
             {'channelId': channel_id}),
            # 频道排行API
            ('https://vc.mgtv.com/v2/list/channelrank',
             {'channelId': channel_id, 'pageNo': '1', 'pageSize': '30'}),
            # pcweb排行API
            ('https://pcweb.api.mgtv.com/video/rank',
             {'channelId': channel_id, 'pageSize': '30'}),
            # 移动端排行API
            ('https://mobile.api.mgtv.com/v8/video/rank',
             {'channelId': channel_id, 'pageNo': '1', 'pageSize': '30'}),
            # 热播推荐
            ('https://vc.mgtv.com/v2/dynamicList',
             {'channelId': channel_id, 'pageNo': '1', 'pageSize': '30',
              'kind': 'a1'}),
        ]

        for url, params in api_list:
            data = self.fetch_json(url, params=params)
            if not data:
                continue

            items = self._parse_rank_response(data, category)
            if items:
                has_heat = sum(1 for x in items if x['heat_value'] > 0)
                logger.info(f"[芒果TV] 排行API({url.split('/')[-1]}): "
                            f"{len(items)}条, {has_heat}条有热度")
                return items

        return []

    def _parse_rank_response(self, data, category):
        """解析芒果TV各种API的响应"""
        items = []

        # 尝试多种响应数据路径
        hit_list = (
            data.get('data', {}).get('hitDocs', []) or
            data.get('data', {}).get('list', []) or
            data.get('data', {}).get('items', []) or
            data.get('data', {}).get('contents', []) or
            data.get('data', []) if isinstance(data.get('data'), list) else [] or
            []
        )

        if not hit_list:
            return []

        for i, item in enumerate(hit_list[:30]):
            if not isinstance(item, dict):
                continue

            title = item.get('title', '') or item.get('name', '')
            if not title:
                continue

            # 热度值: 遍历所有可能的字段
            heat = 0
            for key in ['playcnt', 'allcnt', 'views', 'playPartCnt',
                         'viewsMonth', 'story_heat', 'hot', 'score',
                         'heatScore', 'heat', 'hotVal', 'playCount',
                         'totalHeat', 'weeklyHeat']:
                val = item.get(key, 0)
                if val:
                    try:
                        heat = float(str(val).replace(',', ''))
                        if heat > 0:
                            break
                    except (ValueError, TypeError):
                        continue

            # 如果常规字段没有，检查所有数字字段
            if heat == 0:
                for k, v in item.items():
                    if isinstance(v, (int, float)) and v > 100:
                        heat = float(v)
                        break

            # 封面图
            img = item.get('img', '') or item.get('clipImg', '') or item.get('pic', '') or ''
            if img and not img.startswith('http'):
                img = f'https://1img.hitv.com/preview/{img}'

            # 判断完结
            update_info = item.get('updateInfo', '') or ''
            is_finished = (
                ('全' in update_info and '集' in update_info) or
                '完结' in update_info
            )

            items.append({
                'title': self._normalize_title(title),
                'heat_value': heat,
                'poster_url': img,
                'rank': i + 1,
                'category': category,
                'is_finished': is_finished,
            })

        return items

    # ----------------------------------------------------------------
    # 方式2: 排行页HTML
    # ----------------------------------------------------------------
    def _fetch_rank_html(self, channel_id, category):
        """抓取芒果TV排行页HTML"""
        ch_map = {'2': 'tv', '3': 'variety'}
        ch_name = ch_map.get(channel_id, 'tv')

        urls = [
            f'https://www.mgtv.com/rank/{ch_name}',
            'https://www.mgtv.com/rank/',
            f'https://www.mgtv.com/lib/{ch_name}',
        ]

        for url in urls:
            resp = self.fetch(url, headers={'Referer': 'https://www.mgtv.com/'})
            if not resp:
                continue

            text = resp.text
            items = []

            # 1. 尝试提取嵌入JSON
            for pattern in [
                r'window\.__NUXT__\s*=\s*(\{.+?\});\s*</script>',
                r'window\.__INITIAL_DATA__\s*=\s*(\{.+?\});\s*</script>',
                r'"rankList"\s*:\s*(\[.+?\])\s*[,}]',
                r'"list"\s*:\s*(\[.+?\])\s*[,}]',
            ]:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    try:
                        json_data = json.loads(match.group(1))
                        if isinstance(json_data, list):
                            items = self._parse_json_list(json_data, category)
                        elif isinstance(json_data, dict):
                            items = self._search_json_for_rank(json_data, category)
                    except json.JSONDecodeError:
                        continue

                if items:
                    logger.info(f"[芒果TV] 排行HTML({url}): {len(items)}条")
                    return items

            # 2. 直接从HTML解析
            title_heat_pairs = re.findall(
                r'title="([^"]{2,30})".*?(\d{3,6})',
                text, re.DOTALL
            )
            seen = set()
            for title_raw, heat_str in title_heat_pairs:
                title = self._normalize_title(title_raw)
                if title in seen or not title:
                    continue
                seen.add(title)
                try:
                    heat = float(heat_str)
                except ValueError:
                    continue
                if heat > 100:
                    items.append({
                        'title': title,
                        'heat_value': heat,
                        'poster_url': '',
                        'rank': len(items) + 1,
                        'category': category,
                        'is_finished': False,
                    })
                if len(items) >= 30:
                    break

            if items:
                logger.info(f"[芒果TV] HTML直接解析: {len(items)}条")
                return items

        return []

    def _parse_json_list(self, data_list, category):
        """解析JSON列表"""
        items = []
        for i, item in enumerate(data_list[:30]):
            if not isinstance(item, dict):
                continue
            title = item.get('title', '') or item.get('name', '')
            heat = (item.get('heat', 0) or item.get('hot', 0) or
                    item.get('score', 0) or item.get('playcnt', 0) or 0)
            poster = item.get('img', '') or item.get('pic', '') or ''

            if title:
                try:
                    heat = float(str(heat).replace(',', ''))
                except (ValueError, TypeError):
                    heat = 0
                items.append({
                    'title': self._normalize_title(title),
                    'heat_value': heat,
                    'poster_url': poster,
                    'rank': i + 1,
                    'category': category,
                    'is_finished': False,
                })
        return items

    def _search_json_for_rank(self, data, category):
        """递归搜索JSON中的排行列表"""
        items = []

        def _search(obj, depth=0):
            if depth > 6 or len(items) >= 30:
                return
            if isinstance(obj, list) and len(obj) >= 5:
                has_titles = sum(1 for x in obj[:5]
                                if isinstance(x, dict) and
                                ('title' in x or 'name' in x))
                if has_titles >= 3:
                    result = self._parse_json_list(obj, category)
                    if result:
                        items.extend(result)
                        return
            if isinstance(obj, dict):
                for v in obj.values():
                    _search(v, depth + 1)
            elif isinstance(obj, list):
                for v in obj:
                    _search(v, depth + 1)

        _search(data)
        return items

    # ----------------------------------------------------------------
    # 方式3: pianku列表API（备用）
    # ----------------------------------------------------------------
    def _fetch_pianku(self, channel_id, category):
        """pianku列表API — 按热度排序"""
        for order_type in ['c2', 'c1']:
            data = self.fetch_json(
                'https://pianku.api.mgtv.com/rider/list/pcweb/v3',
                params={
                    'allowedRC': '1',
                    'platform': 'pcweb',
                    'channelId': channel_id,
                    'pn': '1',
                    'pc': '30',
                    'hudong': '1',
                    'orderType': order_type,
                }
            )
            if not data:
                continue

            items = self._parse_rank_response(data, category)
            if items:
                logger.info(f"[芒果TV] pianku(order={order_type}): {len(items)}条")
                return items

        return []
