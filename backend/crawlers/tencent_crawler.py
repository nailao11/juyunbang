import json
import re
from loguru import logger

from .base_crawler import BaseCrawler


class TencentCrawler(BaseCrawler):
    """
    腾讯视频热度采集器 — 使用多种公开接口
    策略：
      1. 腾讯视频热播榜 Web API（bu/pagesheet/list）
      2. 腾讯视频搜索热词接口
      3. 腾讯视频 pbaccess API
    """

    PLATFORM_ID = 3

    def __init__(self):
        super().__init__('腾讯视频')

    def crawl(self):
        logger.info("[腾讯视频] 开始采集热度数据...")
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
                        logger.error(f"[腾讯视频] 保存失败 {item['title']}: {e}")

            self.log_task('tencent_heat', 'success', saved_count)
            logger.info(f"[腾讯视频] 采集完成，共{len(results)}条，保存{saved_count}条")

        except Exception as e:
            logger.error(f"[腾讯视频] 采集异常: {e}")
            self.log_task('tencent_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, category='tv'):
        """多接口策略"""
        # 方式1: 腾讯视频热播榜 Web API (最稳定的公开接口)
        items = self._fetch_from_web_list(category)
        if items:
            return items

        # 方式2: 腾讯视频热搜/热播接口
        logger.warning(f"[腾讯视频] Web列表接口无数据，尝试热播接口 {category}")
        items = self._fetch_from_hot_rank(category)
        if items:
            return items

        # 方式3: pbaccess API
        logger.warning(f"[腾讯视频] 热播接口无数据，尝试pbaccess {category}")
        items = self._fetch_from_pbaccess(category)
        return items

    def _fetch_from_web_list(self, category):
        """
        腾讯视频频道列表 API — GET 请求，返回 JSON
        https://v.qq.com/x/bu/pagesheet/list 是腾讯视频公开的频道列表接口
        sort=75 表示按热度排序
        """
        channel_map = {'tv': 'tv', 'variety': 'variety'}
        channel = channel_map.get(category, 'tv')

        url = 'https://v.qq.com/x/bu/pagesheet/list'
        params = {
            '_all': '1',
            'append': '1',
            'channel': channel,
            'listpage': '2',
            'offset': '0',
            'pagesize': '30',
            'sort': '75',  # 按热度排序
        }

        headers = {
            'Referer': 'https://v.qq.com/channel/tv',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
        }

        resp = self.fetch(url, params=params, headers=headers)
        if not resp:
            return []

        items = []
        try:
            # 尝试JSON解析
            try:
                data = resp.json()
                item_list = data.get('list', []) or data.get('data', {}).get('list', []) or []
            except Exception:
                # 如果不是JSON，尝试从HTML中提取JSON数据
                text = resp.text
                item_list = self._extract_from_html(text)

            for i, show in enumerate(item_list[:30]):
                if isinstance(show, dict):
                    title = show.get('title', '') or show.get('typeName', '')
                    heat = show.get('hotVal', 0) or show.get('epsodeCount', 0) or 0
                    poster = show.get('pic160x90', '') or show.get('pic', '') or show.get('horizontalPic', '') or ''
                    # 判断是否完结
                    type_name = show.get('typeName', '') or show.get('markLabel', '') or ''
                    episode_info = show.get('episode_updated', '') or show.get('latest_updateDesc', '')
                    is_finished = '完结' in type_name or '完结' in str(episode_info)

                    if title:
                        try:
                            heat_value = float(str(heat).replace(',', '').replace('万', '0000'))
                        except (ValueError, TypeError):
                            heat_value = max(0, 10000 - i * 300)

                        items.append({
                            'title': self._normalize_title(title),
                            'heat_value': heat_value if heat_value > 0 else max(0, 10000 - i * 300),
                            'poster_url': poster,
                            'rank': i + 1,
                            'category': category,
                            'is_finished': is_finished,
                            'platform': 'tencent'
                        })

        except Exception as e:
            logger.error(f"[腾讯视频] Web列表解析失败: {e}")

        return items

    def _extract_from_html(self, html_text):
        """从HTML中提取剧集数据"""
        items = []
        try:
            # 尝试找JSON数据块
            match = re.search(r'var\s+LIST_DATA\s*=\s*(\{.*?\});', html_text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                return data.get('list', [])

            match = re.search(r'"list"\s*:\s*(\[.*?\])', html_text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except Exception:
            pass
        return items

    def _fetch_from_hot_rank(self, category):
        """腾讯视频站内热搜榜"""
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
                        'heat_value': float(heat) if heat else max(0, 10000 - i * 300),
                        'poster_url': poster,
                        'rank': i + 1,
                        'category': category,
                        'is_finished': False,
                        'platform': 'tencent'
                    })
        except Exception as e:
            logger.error(f"[腾讯视频] 热搜榜解析失败: {e}")

        return items

    def _fetch_from_pbaccess(self, category):
        """pbaccess内部API（备用）"""
        import time, random

        channel_map = {'tv': '100113', 'variety': '100109'}
        channel_id = channel_map.get(category, '100113')

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
                'channel_id': channel_id,
                'filter_params': 'sort=75',
                'page': '0',
            },
            'page_bypass_params': {
                'params': {'page_size': '30', 'page_num': '0',
                           'caller_id': '3000010', 'platform_id': '2'},
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
            logger.error(f"[腾讯视频] pbaccess失败: {e}")
            return []

        items = []
        try:
            card_list = data.get('data', {}).get('CardList', []) or data.get('data', {}).get('card_list', []) or []
            for card in card_list:
                children = (
                    card.get('children_list', {}).get('list', {}).get('cards', []) or
                    card.get('card', {}).get('card_data', {}).get('cards', []) or []
                )
                for i, child in enumerate(children[:30]):
                    params = child.get('params', {})
                    title = params.get('title', '') or params.get('show_title', '')
                    heat = params.get('hot_value', 0) or params.get('score', 0)
                    poster = params.get('new_pic_hz', '') or params.get('image_url', '') or params.get('pic', '')

                    if title:
                        try:
                            heat_value = float(str(heat).replace(',', '').replace('万', '0000'))
                        except (ValueError, TypeError):
                            heat_value = 0

                        items.append({
                            'title': self._normalize_title(title),
                            'heat_value': heat_value,
                            'poster_url': poster,
                            'rank': i + 1,
                            'category': category,
                            'is_finished': False,
                            'platform': 'tencent'
                        })
                if items:
                    break
        except Exception as e:
            logger.error(f"[腾讯视频] pbaccess解析失败: {e}")

        return items
