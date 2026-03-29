import json
from loguru import logger

from .base_crawler import BaseCrawler


class TencentCrawler(BaseCrawler):
    """腾讯视频热度采集器 — 使用腾讯视频内部API"""

    PLATFORM_ID = 3

    # 腾讯视频排行数据接口（POST请求，返回JSON）
    RANK_API = 'https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/getPage'

    # 频道ID映射
    CHANNEL_MAP = {
        'tv': 100113,       # 电视剧
        'variety': 100109,  # 综艺
        'anime': 100119,    # 动漫
    }

    def __init__(self):
        super().__init__('腾讯视频')

    def crawl(self):
        """采集腾讯视频热搜榜，匹配剧名并保存到数据库"""
        logger.info("[腾讯视频] 开始采集热度数据...")
        results = []
        saved_count = 0

        try:
            tv_data = self._crawl_rank('tv')
            results.extend(tv_data)

            variety_data = self._crawl_rank('variety')
            results.extend(variety_data)

            for item in results:
                drama_id = self._match_drama(item['title'])
                if drama_id:
                    try:
                        self.save_heat_data(
                            drama_id=drama_id,
                            platform_id=self.PLATFORM_ID,
                            heat_value=item['heat_value'],
                            heat_rank=item.get('rank'),
                        )
                        saved_count += 1
                        logger.debug(
                            f"[腾讯视频] 保存成功: {item['title']} "
                            f"热度={item['heat_value']} 排名={item.get('rank')}"
                        )
                    except Exception as e:
                        logger.error(f"[腾讯视频] 保存失败 {item['title']}: {e}")

            self.log_task('tencent_heat', 'success', saved_count)
            logger.info(
                f"[腾讯视频] 采集完成，共{len(results)}条数据，"
                f"成功匹配并保存{saved_count}条"
            )

        except Exception as e:
            logger.error(f"[腾讯视频] 采集异常: {e}")
            self.log_task('tencent_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, category='tv'):
        """通过腾讯视频内部API采集排行"""
        channel_id = self.CHANNEL_MAP.get(category, self.CHANNEL_MAP['tv'])

        # 方式1：使用腾讯视频的 pbaccess API（POST请求）
        items = self._fetch_from_api(channel_id, category)

        if not items:
            # 方式2：使用腾讯视频的H5热播接口
            logger.warning(f"[腾讯视频] 主接口无数据，尝试H5接口采集{category}")
            items = self._fetch_from_h5(category)

        return items

    def _fetch_from_api(self, channel_id, category):
        """使用pbaccess内部API获取排行数据"""
        import time
        import random

        headers = {
            'Content-Type': 'application/json',
            'Referer': 'https://v.qq.com/',
            'Origin': 'https://v.qq.com',
        }

        body = {
            'page_context': {
                'page_index': '0',
            },
            'page_params': {
                'page_id': 'channel_list_second_page',
                'page_type': 'operation',
                'channel_id': str(channel_id),
                'filter_params': 'sort=75',  # 按热度排序
                'page': '0',
            },
            'page_bypass_params': {
                'params': {
                    'page_size': '30',
                    'page_num': '0',
                    'caller_id': '3000010',
                    'platform_id': '2',
                },
                'global_params': {
                    'ckey': '',
                    'vuession': '',
                },
            },
        }

        time.sleep(random.uniform(1, 3))

        try:
            resp = self.session.post(
                self.RANK_API,
                json=body,
                headers=headers,
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"[腾讯视频] API请求失败: {e}")
            return []

        items = []
        try:
            # 解析腾讯视频API返回结构
            card_list = (
                data.get('data', {}).get('CardList', []) or
                data.get('data', {}).get('card_list', []) or
                []
            )

            for card in card_list:
                children = (
                    card.get('children_list', {}).get('list', {}).get('cards', []) or
                    card.get('card', {}).get('card_data', {}).get('cards', []) or
                    []
                )
                for i, child in enumerate(children[:30]):
                    params = child.get('params', {})
                    title = (
                        params.get('title', '') or
                        params.get('show_title', '') or
                        child.get('title', '')
                    )
                    heat = (
                        params.get('hot_value', 0) or
                        params.get('score', 0) or
                        0
                    )

                    if title:
                        try:
                            heat_value = float(str(heat).replace(',', '').replace('万', '0000'))
                        except ValueError:
                            heat_value = 0

                        items.append({
                            'title': self._normalize_title(title),
                            'heat_value': heat_value,
                            'rank': i + 1,
                            'category': category,
                            'platform': 'tencent'
                        })

                if items:
                    break  # 找到排行数据就停止

        except Exception as e:
            logger.error(f"[腾讯视频] 解析API响应失败: {e}")

        return items

    def _fetch_from_h5(self, category):
        """备用方式：使用腾讯视频H5热播接口"""
        category_map = {
            'tv': 2,       # 电视剧
            'variety': 10,  # 综艺
        }
        cid = category_map.get(category, 2)

        url = 'https://i.q.qq.com/sns_vip/hot_play_data'
        params = {
            'cid': cid,
            'type': 2,
            'otype': 'json',
        }

        data = self.fetch_json(url, params=params)
        if not data:
            return []

        items = []
        try:
            play_list = data.get('data', {}).get('list', []) or data.get('list', []) or []
            for i, show in enumerate(play_list[:30]):
                title = show.get('title', '') or show.get('name', '')
                heat = show.get('hot', 0) or show.get('heat', 0) or 0

                if title:
                    items.append({
                        'title': self._normalize_title(title),
                        'heat_value': float(heat),
                        'rank': i + 1,
                        'category': category,
                        'platform': 'tencent'
                    })

        except Exception as e:
            logger.error(f"[腾讯视频] H5接口解析失败: {e}")

        return items
