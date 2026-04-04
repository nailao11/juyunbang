from loguru import logger

from .base_crawler import BaseCrawler


class IqiyiCrawler(BaseCrawler):
    """
    爱奇艺热度采集器
    策略：
      1. 风云榜 mesh API（返回站内热度值）
      2. PCW 推荐API（备用，基于排名估算热度）
      3. 爱奇艺热播页HTML解析（最终备用）
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
                if drama_id:
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
            logger.info(f"[爱奇艺] 采集完成，共{len(results)}条，保存{saved_count}条")

        except Exception as e:
            logger.error(f"[爱奇艺] 采集异常: {e}")
            self.log_task('iqiyi_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, category='tv'):
        """多接口采集"""
        # 方式1: 风云榜API
        items = self._crawl_main_api(category)
        if items:
            return items

        # 方式2: PCW推荐API
        items = self._crawl_pcw_api(category)
        if items:
            return items

        # 方式3: 爱奇艺热播HTML页
        logger.warning(f"[爱奇艺] API均失败，尝试HTML采集 {category}")
        items = self._crawl_hot_page(category)
        return items

    def _crawl_main_api(self, category):
        """主API: 风云榜"""
        url = 'https://mesh.if.iqiyi.com/portal/lw/videolib/data/rank'
        params = {
            'type': 'heat',
            'cid': '2' if category == 'tv' else '6',
            'limit': '30'
        }

        data = self.fetch_json(url, params=params)
        if not data:
            return []

        items = []
        try:
            rank_list = data.get('data', {}).get('list', [])
            for i, item in enumerate(rank_list):
                title = item.get('name', '')
                heat = item.get('hot', 0)
                poster = item.get('imageUrl', '') or item.get('img', '') or ''
                if title and heat:
                    items.append({
                        'title': title,
                        'heat_value': heat,
                        'poster_url': poster,
                        'rank': i + 1,
                        'category': category,
                        'is_finished': False,
                        'platform': 'iqiyi'
                    })
        except Exception as e:
            logger.error(f"[爱奇艺] 主API解析失败: {e}")

        return items

    def _crawl_pcw_api(self, category):
        """备用: PCW推荐API — 按排名位置估算热度值"""
        url = 'https://pcw-api.iqiyi.com/search/recommend/list'
        channel_map = {'tv': '2', 'variety': '6'}
        params = {
            'channel_id': channel_map.get(category, '2'),
            'data_type': '1',
            'mode': '24',
            'page_id': '1',
            'ret_num': '30',
        }

        data = self.fetch_json(url, params=params)
        if not data:
            return []

        items = []
        try:
            item_list = data.get('data', {}).get('list', [])
            for i, item in enumerate(item_list):
                title = item.get('title', item.get('name', ''))
                # 尝试获取热度值; 如果没有，按排名递减估算
                heat = item.get('hot', 0) or item.get('play_count', 0) or item.get('score', 0)
                if not heat:
                    heat = max(1000, 9800 - i * 300)

                poster = item.get('imageUrl', '') or item.get('img', '') or item.get('pic', '') or ''

                # 检查是否完结
                desc = item.get('description', '') or item.get('focus', '') or ''
                is_finished = '完结' in desc or '全集' in desc

                if title:
                    items.append({
                        'title': title,
                        'heat_value': float(heat),
                        'poster_url': poster,
                        'rank': i + 1,
                        'category': category,
                        'is_finished': is_finished,
                        'platform': 'iqiyi'
                    })
        except Exception as e:
            logger.error(f"[爱奇艺] PCW API解析失败: {e}")

        return items

    def _crawl_hot_page(self, category):
        """最终备用: 爱奇艺热播页HTML"""
        url_map = {
            'tv': 'https://www.iqiyi.com/ranks/hot/2',
            'variety': 'https://www.iqiyi.com/ranks/hot/6',
        }
        url = url_map.get(category, url_map['tv'])

        resp = self.fetch(url)
        if not resp:
            return []

        items = []
        try:
            import re
            # 爱奇艺排行页在HTML中嵌入JSON数据
            match = re.search(r'window\.__INITIAL_DATA__\s*=\s*(\{.*?\});\s*</script>', resp.text, re.DOTALL)
            if match:
                import json
                data = json.loads(match.group(1))
                # 尝试提取排行数据
                for key, value in data.items():
                    if isinstance(value, dict) and 'list' in value:
                        rank_list = value['list']
                        for i, show in enumerate(rank_list[:30]):
                            title = show.get('name', '') or show.get('title', '')
                            heat = show.get('hot', 0) or show.get('score', 0)
                            poster = show.get('imageUrl', '') or show.get('img', '')
                            if title:
                                items.append({
                                    'title': title,
                                    'heat_value': heat if heat else max(1000, 9800 - i * 300),
                                    'poster_url': poster,
                                    'rank': i + 1,
                                    'category': category,
                                    'is_finished': False,
                                    'platform': 'iqiyi'
                                })
                        if items:
                            break
        except Exception as e:
            logger.error(f"[爱奇艺] HTML解析失败: {e}")

        return items
