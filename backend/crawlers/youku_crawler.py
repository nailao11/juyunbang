import json
import re
from loguru import logger

from .base_crawler import BaseCrawler


class YoukuCrawler(BaseCrawler):
    """
    优酷热度采集器
    策略优先级:
      1. 排行榜HTML页面（解析嵌入JSON数据）
      2. 移动端网关API
      3. 频道列表页HTML解析
    注意: 优酷反爬较严格，部分接口可能不可用。
    """

    PLATFORM_ID = 2

    def __init__(self):
        super().__init__('优酷')

    def crawl(self):
        logger.info("[优酷] 开始采集热度数据...")
        results = []
        saved_count = 0

        try:
            tv_data = self._crawl_rank(category='电视剧', cid='97')
            results.extend(tv_data)

            variety_data = self._crawl_rank(category='综艺', cid='85')
            results.extend(variety_data)

            type_map = {'电视剧': 'tv_drama', '综艺': 'variety'}

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
                        logger.error(f"[优酷] 保存失败 {item['title']}: {e}")

            self.log_task('youku_heat', 'success', saved_count)
            logger.info(f"[优酷] 采集完成，共{len(results)}条，保存热度{saved_count}条")

        except Exception as e:
            logger.error(f"[优酷] 采集异常: {e}")
            self.log_task('youku_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, category='电视剧', cid='97'):
        # 方式1: 排行榜页面HTML（嵌入JSON数据）
        items = self._fetch_rank_html(cid, category)
        if items:
            return items

        # 方式2: 移动端API
        items = self._fetch_from_api(cid, category)
        if items:
            return items

        # 方式3: 频道列表页HTML
        items = self._fetch_from_channel_html(cid, category)
        return items

    # ----------------------------------------------------------------
    # 方式1: 排行榜HTML页面
    # ----------------------------------------------------------------
    def _fetch_rank_html(self, cid, category):
        """优酷排行榜HTML — 解析嵌入JSON"""
        cid_map = {'97': 'tv', '85': 'variety'}
        cat = cid_map.get(cid, 'tv')

        urls = [
            f'https://www.youku.com/rank/{cat}',
            'https://www.youku.com/rank',
            f'https://www.youku.com/category/show/c_{cid}_s_1_d_1.html',
        ]

        for url in urls:
            resp = self.fetch(url, headers={'Referer': 'https://www.youku.com/'})
            if not resp:
                continue

            text = resp.text
            items = []

            # 尝试提取嵌入JSON
            for pattern in [
                r'window\.__INITIAL_DATA__\s*=\s*(\{.+?\});\s*</script>',
                r'window\.__NEXT_DATA__[^>]*>\s*(\{.+?\})\s*</script>',
                r'window\.__NUXT__\s*=\s*(\{.+?\});\s*</script>',
                r'"rankList"\s*:\s*(\[.+?\])\s*[,}]',
            ]:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    try:
                        json_data = json.loads(match.group(1))
                        items = self._extract_from_json(json_data, category)
                    except json.JSONDecodeError:
                        continue

                if items:
                    has_heat = sum(1 for x in items if x['heat_value'] > 0)
                    logger.info(f"[优酷] 排行HTML({url}): {len(items)}条, {has_heat}条有热度")
                    return items

            # 直接从HTML提取标题和热度
            items = self._parse_html_items(text, category)
            if items:
                logger.info(f"[优酷] HTML直接解析: {len(items)}条")
                return items

        return []

    def _extract_from_json(self, data, category):
        """递归搜索JSON中的排行列表"""
        items = []

        def _search(obj, depth=0):
            if depth > 8 or len(items) >= 30:
                return
            if isinstance(obj, list) and len(obj) >= 5:
                has_titles = sum(1 for x in obj[:5]
                                if isinstance(x, dict) and
                                any(k in x for k in ('title', 'name', 'show_name',
                                                       'showName', 'videoTitle')))
                if has_titles >= 3:
                    for i, item in enumerate(obj[:30]):
                        if not isinstance(item, dict):
                            continue
                        title = (item.get('title', '') or item.get('name', '') or
                                 item.get('show_name', '') or item.get('showName', '') or '')
                        heat = (item.get('heat', 0) or item.get('hot', 0) or
                                item.get('score', 0) or item.get('hotScore', 0) or
                                item.get('total_vv', 0) or 0)
                        poster = (item.get('img', '') or item.get('cover', '') or
                                  item.get('thumb_url', '') or item.get('pic', '') or '')

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
                    return
            if isinstance(obj, dict):
                for v in obj.values():
                    _search(v, depth + 1)
            elif isinstance(obj, list):
                for v in obj:
                    _search(v, depth + 1)

        _search(data)
        return items

    def _parse_html_items(self, text, category):
        """从HTML标签中提取标题和热度"""
        items = []
        seen = set()

        # 方式1: 匹配 title 属性
        for match in re.finditer(r'title="([^"]{2,30})"', text):
            title = self._normalize_title(match.group(1))
            if not title or title in seen:
                continue
            if any(skip in title for skip in ['优酷', '登录', '客户端', '首页']):
                continue
            seen.add(title)
            items.append({
                'title': title,
                'heat_value': 0,  # HTML中可能没有热度
                'poster_url': '',
                'rank': len(items) + 1,
                'category': category,
                'is_finished': False,
            })
            if len(items) >= 30:
                break

        # 补充封面图
        imgs = re.findall(r'src="(https?://[^"]*(?:ykimg|youku)[^"]*\.(?:jpg|png))"', text)
        for i, img_url in enumerate(imgs):
            if i < len(items):
                items[i]['poster_url'] = img_url

        return items

    # ----------------------------------------------------------------
    # 方式2: 移动端API
    # ----------------------------------------------------------------
    def _fetch_from_api(self, cid, category):
        """优酷移动端网关API"""
        headers = {'Referer': 'https://www.youku.com/'}
        params = {
            'jsv': '2.7.2',
            'appKey': '24679788',
            'api': 'mtop.youku.columbus.gateway.new.execute',
            'v': '1.0',
            'data': json.dumps({
                'ms_codes': '2019030100',
                'params': json.dumps({'st': '1', 'pn': '1', 'ps': '30', 'cid': cid})
            })
        }

        data = self.fetch_json(
            'https://acs.youku.com/h5/mtop.youku.columbus.gateway.new.execute/1.0/',
            params=params, headers=headers
        )
        if not data:
            return []

        items = []
        try:
            result = data.get('data', {})
            if isinstance(result, str):
                result = json.loads(result)

            show_list = (
                result.get('data', {}).get('nodes', []) or
                result.get('nodes', []) or
                result.get('list', []) or []
            )

            for i, show in enumerate(show_list[:30]):
                title = (show.get('title', '') or show.get('show_name', '') or
                         show.get('name', '') or '')
                heat = (show.get('heat', 0) or show.get('hot_value', 0) or
                        show.get('total_vv', 0) or 0)
                poster = (show.get('img', '') or show.get('cover', '') or
                          show.get('thumb_url', '') or '')
                is_finished = show.get('completed', False) or '完结' in str(
                    show.get('episode_total', ''))

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
        except Exception as e:
            logger.error(f"[优酷] API解析失败: {e}")

        if items:
            has_heat = sum(1 for x in items if x['heat_value'] > 0)
            logger.info(f"[优酷] API: {len(items)}条, {has_heat}条有热度")

        return items

    # ----------------------------------------------------------------
    # 方式3: 频道列表页HTML
    # ----------------------------------------------------------------
    def _fetch_from_channel_html(self, cid, category):
        """从优酷列表页HTML提取"""
        url = f'https://list.youku.com/category/show/c_{cid}/s_1_d_1.html'
        resp = self.fetch(url)
        if not resp:
            return []

        return self._parse_html_items(resp.text, category)
