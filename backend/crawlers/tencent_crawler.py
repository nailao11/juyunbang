import json
from loguru import logger

from .base_crawler import BaseCrawler


class TencentCrawler(BaseCrawler):
    """腾讯视频热度采集器 — 多接口策略"""

    PLATFORM_ID = 3

    CHANNEL_MAP = {
        'tv': 100113,
        'variety': 100109,
        'anime': 100119,
    }

    def __init__(self):
        super().__init__('腾讯视频')

    def crawl(self):
        """采集腾讯视频热搜榜"""
        logger.info("[腾讯视频] 开始采集热度数据...")
        results = []
        saved_count = 0

        try:
            tv_data = self._crawl_rank('tv')
            results.extend(tv_data)

            variety_data = self._crawl_rank('variety')
            results.extend(variety_data)

            type_map = {'tv': 'tv_drama', 'variety': 'variety', 'anime': 'anime'}

            for item in results:
                dtype = type_map.get(item.get('category'), 'tv_drama')
                drama_id = self._match_drama(
                    item['title'],
                    drama_type=dtype,
                    poster_url=item.get('poster_url', '')
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
                        logger.error(f"[腾讯视频] 保存失败 {item['title']}: {e}")

            self.log_task('tencent_heat', 'success', saved_count)
            logger.info(f"[腾讯视频] 采集完成，共{len(results)}条，保存{saved_count}条")

        except Exception as e:
            logger.error(f"[腾讯视频] 采集异常: {e}")
            self.log_task('tencent_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, category='tv'):
        """多接口策略采集排行"""
        channel_id = self.CHANNEL_MAP.get(category, self.CHANNEL_MAP['tv'])

        # 方式1: pbaccess API
        items = self._fetch_from_api(channel_id, category)
        if items:
            return items

        # 方式2: H5热播接口
        logger.warning(f"[腾讯视频] 主接口无数据，尝试H5接口 {category}")
        items = self._fetch_from_h5(category)
        if items:
            return items

        # 方式3: 热搜榜API
        logger.warning(f"[腾讯视频] H5接口也无数据，尝试热搜榜 {category}")
        items = self._fetch_from_hot_search(category)
        return items

    def _fetch_from_api(self, channel_id, category):
        """使用pbaccess内部API"""
        import time, random

        headers = {
            'Content-Type': 'application/json',
            'Referer': 'https://v.qq.com/',
            'Origin': 'https://v.qq.com',
        }

        body = {
            'page_context': {'page_index': '0'},
            'page_params': {
                'page_id': 'channel_list_second_page',
                'page_type': 'operation',
                'channel_id': str(channel_id),
                'filter_params': 'sort=75',
                'page': '0',
            },
            'page_bypass_params': {
                'params': {
                    'page_size': '30', 'page_num': '0',
                    'caller_id': '3000010', 'platform_id': '2',
                },
                'global_params': {'ckey': '', 'vuession': ''},
            },
        }

        time.sleep(random.uniform(1, 3))

        try:
            resp = self.session.post(
                'https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/getPage',
                json=body, headers=headers, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"[腾讯视频] API请求失败: {e}")
            return []

        items = []
        try:
            card_list = (
                data.get('data', {}).get('CardList', []) or
                data.get('data', {}).get('card_list', []) or []
            )

            for card in card_list:
                children = (
                    card.get('children_list', {}).get('list', {}).get('cards', []) or
                    card.get('card', {}).get('card_data', {}).get('cards', []) or []
                )
                for i, child in enumerate(children[:30]):
                    params = child.get('params', {})
                    title = params.get('title', '') or params.get('show_title', '') or child.get('title', '')
                    heat = params.get('hot_value', 0) or params.get('score', 0) or 0
                    # 封面：尝试多种字段
                    poster = (
                        params.get('new_pic_hz', '') or
                        params.get('image_url', '') or
                        params.get('pic', '') or
                        params.get('pic_hz', '') or
                        ''
                    )

                    if title:
                        try:
                            heat_value = float(str(heat).replace(',', '').replace('万', '0000'))
                        except ValueError:
                            heat_value = 0

                        items.append({
                            'title': self._normalize_title(title),
                            'heat_value': heat_value,
                            'poster_url': poster,
                            'rank': i + 1,
                            'category': category,
                            'platform': 'tencent'
                        })

                if items:
                    break

        except Exception as e:
            logger.error(f"[腾讯视频] 解析API响应失败: {e}")

        return items

    def _fetch_from_h5(self, category):
        """备用: H5热播接口"""
        category_map = {'tv': 2, 'variety': 10}
        cid = category_map.get(category, 2)

        url = 'https://i.q.qq.com/sns_vip/hot_play_data'
        params = {'cid': cid, 'type': 2, 'otype': 'json'}

        data = self.fetch_json(url, params=params)
        if not data:
            return []

        items = []
        try:
            play_list = data.get('data', {}).get('list', []) or data.get('list', []) or []
            for i, show in enumerate(play_list[:30]):
                title = show.get('title', '') or show.get('name', '')
                heat = show.get('hot', 0) or show.get('heat', 0) or 0
                poster = show.get('pic', '') or show.get('cover', '') or ''

                if title:
                    items.append({
                        'title': self._normalize_title(title),
                        'heat_value': float(heat),
                        'poster_url': poster,
                        'rank': i + 1,
                        'category': category,
                        'platform': 'tencent'
                    })
        except Exception as e:
            logger.error(f"[腾讯视频] H5接口解析失败: {e}")

        return items

    def _fetch_from_hot_search(self, category):
        """备用: 腾讯视频热搜榜接口"""
        url = 'https://pbaccess.video.qq.com/trpc.videosearch.hot_rank.HotRankServantHttp/HotRankHttp'
        headers = {
            'Content-Type': 'application/json',
            'Referer': 'https://v.qq.com/',
            'Origin': 'https://v.qq.com',
        }

        channel_map = {'tv': '100113', 'variety': '100109'}
        body = {
            'pageNum': 0,
            'pageSize': 30,
            'channelId': channel_map.get(category, '100113'),
        }

        try:
            resp = self.session.post(url, json=body, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"[腾讯视频] 热搜榜接口失败: {e}")
            return []

        items = []
        try:
            item_list = data.get('data', {}).get('itemList', []) or []
            for i, show in enumerate(item_list[:30]):
                title = show.get('title', '')
                heat = show.get('heatScore', 0) or show.get('hotValue', 0)
                poster = show.get('picUrl', '') or show.get('imgUrl', '') or ''

                if title:
                    items.append({
                        'title': self._normalize_title(title),
                        'heat_value': float(heat),
                        'poster_url': poster,
                        'rank': i + 1,
                        'category': category,
                        'platform': 'tencent'
                    })
        except Exception as e:
            logger.error(f"[腾讯视频] 热搜榜解析失败: {e}")

        return items
