import re
import json
from loguru import logger

from .base_crawler import BaseCrawler


class IqiyiCrawler(BaseCrawler):
    """
    爱奇艺热度采集器
    策略优先级:
      1. 风云榜 mesh API（有真实站内热度值）
      2. 排行榜HTML页面（解析嵌入JSON，含热度）
      3. PCW推荐API（备用，可能无热度值）
    """

    PLATFORM_ID = 1

    def __init__(self):
        super().__init__('爱奇艺')

    def crawl(self):
        logger.info("[爱奇艺] 开始采集热度数据...")
        results = []
        saved_count = 0

        try:
            tv_data = self._crawl_rank('tv')
            results.extend(tv_data)

            variety_data = self._crawl_rank('variety')
            results.extend(variety_data)

            type_map = {'tv': 'tv_drama', 'variety': 'variety'}

            for item in results:
                dtype = type_map.get(item.get('category'), 'tv_drama')
                drama_id = self._match_drama(
                    item['title'],
                    drama_type=dtype,
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
                        logger.error(f"[爱奇艺] 保存失败 {item['title']}: {e}")

            self.log_task('iqiyi_heat', 'success', saved_count)
            logger.info(f"[爱奇艺] 采集完成，共{len(results)}条，保存热度{saved_count}条")

        except Exception as e:
            logger.error(f"[爱奇艺] 采集异常: {e}")
            self.log_task('iqiyi_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, category='tv'):
        # 方式1: 风云榜 mesh API（优先，有真实热度）
        items = self._crawl_mesh_api(category)
        if items:
            return items

        # 方式2: 排行榜HTML页面（嵌入JSON包含热度）
        items = self._crawl_rank_html(category)
        if items:
            return items

        # 方式3: 其他排行API变体
        items = self._crawl_alt_apis(category)
        if items:
            return items

        # 方式4: PCW推荐API（备用，热度可能为0）
        items = self._crawl_pcw_api(category)
        return items

    # ----------------------------------------------------------------
    # 方式1: 风云榜 mesh API
    # ----------------------------------------------------------------
    def _crawl_mesh_api(self, category):
        """主API: 爱奇艺风云榜（返回真实hot热度值）"""
        cid = '2' if category == 'tv' else '6'

        # 尝试多种参数组合
        param_variants = [
            {'type': 'heat', 'cid': cid, 'limit': '30'},
            {'type': 'hot', 'cid': cid, 'limit': '30'},
            {'type': 'heat', 'cid': cid, 'limit': '30', 'date': ''},
        ]

        for params in param_variants:
            data = self.fetch_json(
                'https://mesh.if.iqiyi.com/portal/lw/videolib/data/rank',
                params=params
            )
            if not data:
                continue

            items = []
            rank_list = data.get('data', {}).get('list', [])
            if not rank_list:
                # 尝试其他响应路径
                rank_list = (data.get('data', {}).get('rankList', []) or
                             data.get('data', {}).get('items', []) or
                             data.get('list', []) or [])

            for i, item in enumerate(rank_list[:30]):
                title = item.get('name', '') or item.get('title', '')
                heat = item.get('hot', 0) or item.get('score', 0) or item.get('heat', 0)
                poster = (item.get('imageUrl', '') or item.get('img', '') or
                          item.get('pic', '') or '')

                if title and heat:
                    items.append({
                        'title': self._normalize_title(title),
                        'heat_value': float(heat),
                        'poster_url': poster,
                        'rank': i + 1,
                        'category': category,
                        'is_finished': False,
                    })

            if items:
                logger.info(f"[爱奇艺] 风云榜: {len(items)}条有热度")
                return items

        return []

    # ----------------------------------------------------------------
    # 方式2: 排行榜HTML页面
    # ----------------------------------------------------------------
    def _crawl_rank_html(self, category):
        """
        爱奇艺排行榜HTML页面 — 解析 window.__INITIAL_DATA__ 或页面内容。
        排行榜页面地址: https://www.iqiyi.com/ranks/热度
        """
        cid = '2' if category == 'tv' else '6'
        urls = [
            f'https://www.iqiyi.com/ranks/热度/{cid}',
            f'https://www.iqiyi.com/ranks/hot/{cid}',
            'https://www.iqiyi.com/ranks',
        ]

        for url in urls:
            resp = self.fetch(url)
            if not resp:
                continue

            text = resp.text
            items = []

            # 1. 提取 window.__INITIAL_DATA__
            match = re.search(
                r'window\.__INITIAL_DATA__\s*=\s*(\{.+?\});\s*</script>',
                text, re.DOTALL
            )
            if match:
                try:
                    json_data = json.loads(match.group(1))
                    items = self._extract_from_initial_data(json_data, category)
                except json.JSONDecodeError:
                    pass

            if items:
                logger.info(f"[爱奇艺] 排行HTML({url}): {len(items)}条")
                return items

            # 2. 尝试其他嵌入JSON模式
            for pattern in [
                r'window\.__NUXT__\s*=\s*(\{.+?\});\s*</script>',
                r'"rankList"\s*:\s*(\[.+?\])\s*[,}]',
            ]:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    try:
                        json_data = json.loads(match.group(1))
                        if isinstance(json_data, list):
                            items = self._parse_rank_list(json_data, category)
                        elif isinstance(json_data, dict):
                            items = self._extract_from_initial_data(json_data, category)
                    except json.JSONDecodeError:
                        continue

                if items:
                    logger.info(f"[爱奇艺] 排行JSON: {len(items)}条")
                    return items

            # 3. 直接从HTML提取
            items = self._parse_html_rank_items(text, category)
            if items:
                logger.info(f"[爱奇艺] HTML直接解析: {len(items)}条")
                return items

        return []

    def _extract_from_initial_data(self, data, category):
        """递归搜索INITIAL_DATA中的排行列表"""
        items = []

        def _search(obj, depth=0):
            if depth > 8 or len(items) >= 30:
                return
            if isinstance(obj, list) and len(obj) >= 5:
                # 检查是否像排行列表
                has_names = sum(1 for x in obj[:5]
                                if isinstance(x, dict) and
                                ('name' in x or 'title' in x))
                if has_names >= 3:
                    result = self._parse_rank_list(obj, category)
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

    def _parse_rank_list(self, rank_list, category):
        """解析排行列表数组"""
        items = []
        for i, item in enumerate(rank_list[:30]):
            if not isinstance(item, dict):
                continue
            title = (item.get('name', '') or item.get('title', '') or
                     item.get('albumName', '') or '')
            heat = (item.get('hot', 0) or item.get('score', 0) or
                    item.get('heat', 0) or item.get('hotScore', 0) or
                    item.get('contentRating', 0) or 0)
            poster = (item.get('imageUrl', '') or item.get('img', '') or
                      item.get('pic', '') or item.get('coverUrl', '') or '')

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

        return items if any(x['heat_value'] > 0 for x in items) else []

    def _parse_html_rank_items(self, text, category):
        """从HTML元素中直接提取排行信息"""
        items = []
        # 匹配 title="..." 后跟热度数字
        blocks = re.findall(
            r'(?:title|alt)="([^"]{2,30})".*?(\d{3,6})',
            text, re.DOTALL
        )
        seen = set()
        for title_raw, heat_str in blocks:
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

        return items

    # ----------------------------------------------------------------
    # 方式3: 其他排行API变体
    # ----------------------------------------------------------------
    def _crawl_alt_apis(self, category):
        """尝试其他爱奇艺排行API"""
        cid = '2' if category == 'tv' else '6'

        alt_urls = [
            ('https://mesh.if.iqiyi.com/portal/lw/videolib/data/charts',
             {'type': 'hot', 'cid': cid, 'limit': '30'}),
            ('https://pcw-api.iqiyi.com/search/video/videolists',
             {'channel_id': cid, 'mode': '24', 'pageSize': '30', 'page': '1'}),
        ]

        for url, params in alt_urls:
            data = self.fetch_json(url, params=params)
            if not data:
                continue

            items = []
            # 尝试多种响应路径
            rank_list = (data.get('data', {}).get('list', []) or
                         data.get('data', {}).get('items', []) or
                         data.get('list', []) or [])

            for i, item in enumerate(rank_list[:30]):
                title = item.get('name', '') or item.get('title', '')
                heat = (item.get('hot', 0) or item.get('score', 0) or
                        item.get('heat', 0) or 0)
                poster = (item.get('imageUrl', '') or item.get('img', '') or
                          item.get('pic', '') or '')

                if title and heat:
                    items.append({
                        'title': self._normalize_title(title),
                        'heat_value': float(heat),
                        'poster_url': poster,
                        'rank': i + 1,
                        'category': category,
                        'is_finished': False,
                    })

            if items:
                return items

        return []

    # ----------------------------------------------------------------
    # 方式4: PCW推荐API（备用）
    # ----------------------------------------------------------------
    def _crawl_pcw_api(self, category):
        """
        备用: PCW推荐API。
        注意：此API通常hot=0，仅用于获取在播剧标题和封面。
        不保存热度值为0的数据。
        """
        cid = '2' if category == 'tv' else '6'

        # 尝试多种mode
        for mode in ['24', '11', '4']:
            data = self.fetch_json(
                'https://pcw-api.iqiyi.com/search/recommend/list',
                params={
                    'channel_id': cid,
                    'data_type': '1',
                    'mode': mode,
                    'page_id': '1',
                    'ret_num': '30',
                }
            )
            if not data:
                continue

            items = []
            item_list = data.get('data', {}).get('list', [])
            for i, item in enumerate(item_list):
                title = item.get('title', '') or item.get('name', '')
                heat = (item.get('hot', 0) or item.get('play_count', 0) or
                        item.get('score', 0) or 0)
                poster = (item.get('imageUrl', '') or item.get('img', '') or
                          item.get('pic', '') or '')

                desc = item.get('description', '') or item.get('focus', '') or ''
                is_finished = '完结' in desc or '全集' in desc

                if title:
                    try:
                        heat = float(heat) if heat else 0
                    except (ValueError, TypeError):
                        heat = 0

                    items.append({
                        'title': self._normalize_title(title),
                        'heat_value': heat,
                        'poster_url': poster,
                        'rank': i + 1,
                        'category': category,
                        'is_finished': is_finished,
                    })

            if items:
                has_heat = sum(1 for x in items if x['heat_value'] > 0)
                logger.info(f"[爱奇艺] PCW(mode={mode}): {len(items)}条, {has_heat}条有热度")
                return items

        return []
