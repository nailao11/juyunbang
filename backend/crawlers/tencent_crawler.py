import json
import re
import time
import random
from loguru import logger

from .base_crawler import BaseCrawler


class TencentCrawler(BaseCrawler):
    """
    腾讯视频热度采集器
    策略: pbaccess API → HTML列表解析
    """

    PLATFORM_ID = 3

    def __init__(self):
        super().__init__('腾讯视频')

    def crawl(self):
        logger.info("[腾讯视频] 开始采集热度数据...")
        results = []
        saved_count = 0

        try:
            for category in ['tv', 'variety']:
                data = self._crawl_rank(category)
                results.extend(data)

            type_map = {'tv': 'tv_drama', 'variety': 'variety'}
            for item in results:
                dtype = type_map.get(item.get('category'), 'tv_drama')
                drama_id = self._match_drama(
                    item['title'], drama_type=dtype,
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
        # 方式1: pbaccess API (已确认服务器上可返回数据)
        items = self._fetch_from_pbaccess(category)
        if items:
            return items

        # 方式2: bu/pagesheet/list HTML解析
        logger.warning(f"[腾讯视频] pbaccess无数据，尝试HTML列表 {category}")
        items = self._fetch_from_html_list(category)
        return items

    def _fetch_from_pbaccess(self, category):
        """
        pbaccess API — 深度遍历所有可能的数据路径来提取标题和热度。
        已确认服务器上此接口有CardList=2, children=103。
        """
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
            logger.error(f"[腾讯视频] pbaccess请求失败: {e}")
            return []

        items = []
        try:
            card_list = (
                data.get('data', {}).get('CardList', []) or
                data.get('data', {}).get('card_list', []) or []
            )

            for card in card_list:
                # 尝试多种children路径
                children = self._extract_children(card)
                if not children:
                    continue

                for i, child in enumerate(children[:30]):
                    parsed = self._parse_child_item(child, i, category)
                    if parsed:
                        items.append(parsed)

                if items:
                    break  # 找到数据就停止遍历cards

        except Exception as e:
            logger.error(f"[腾讯视频] pbaccess解析失败: {e}")

        if items:
            logger.info(f"[腾讯视频] pbaccess成功提取{len(items)}条{category}数据")

        return items

    def _extract_children(self, card):
        """从card中提取children列表，尝试所有可能路径"""
        paths = [
            lambda c: c.get('children_list', {}).get('list', {}).get('cards', []),
            lambda c: c.get('card', {}).get('card_data', {}).get('cards', []),
            lambda c: c.get('children_list', {}).get('list', {}).get('items', []),
            lambda c: c.get('card_data', {}).get('cards', []),
            lambda c: c.get('children', []),
            lambda c: c.get('items', []),
        ]
        for path_fn in paths:
            try:
                result = path_fn(card)
                if result and len(result) > 0:
                    return result
            except Exception:
                continue
        return []

    def _parse_child_item(self, child, index, category):
        """
        从child对象中提取标题、热度、封面。
        腾讯视频API返回结构不固定，需要尝试多种字段名。
        """
        # 标题: 尝试params中的各种字段，以及顶层字段
        params = child.get('params', {}) or {}
        title = ''
        for key in ['title', 'show_title', 'uni_title', 'second_title', 'reportTitle']:
            title = params.get(key, '') or ''
            if title:
                break
        if not title:
            for key in ['title', 'name', 'show_title']:
                title = child.get(key, '') or ''
                if title:
                    break
        if not title:
            return None

        # 热度值
        heat = 0
        for key in ['hot_value', 'hotval', 'score', 'hot_score', 'ckc_count',
                     'view_count', 'play_count', 'episode_count_text']:
            val = params.get(key, 0) or child.get(key, 0)
            if val:
                try:
                    heat = float(str(val).replace(',', '').replace('万', '0000').replace('亿', '00000000'))
                    if heat > 0:
                        break
                except (ValueError, TypeError):
                    continue
        if heat == 0:
            heat = max(1000, 10000 - index * 300)

        # 封面
        poster = ''
        for key in ['new_pic_hz', 'image_url', 'pic', 'pic_160x90', 'pic_hz',
                     'pic_496x280', 'cover_url', 'horizontal_pic_url']:
            poster = params.get(key, '') or child.get(key, '') or ''
            if poster:
                break

        # 判断完结
        is_finished = False
        for key in ['episode_updated', 'latest_updateDesc', 'second_title', 'markLabel']:
            val = str(params.get(key, '') or child.get(key, '') or '')
            if '完结' in val or ('全' in val and '集' in val):
                is_finished = True
                break

        return {
            'title': self._normalize_title(title),
            'heat_value': heat,
            'poster_url': poster,
            'rank': index + 1,
            'category': category,
            'is_finished': is_finished,
            'platform': 'tencent'
        }

    def _fetch_from_html_list(self, category):
        """从腾讯视频频道列表HTML中提取数据"""
        channel_map = {'tv': 'tv', 'variety': 'variety'}
        channel = channel_map.get(category, 'tv')

        url = 'https://v.qq.com/x/bu/pagesheet/list'
        params = {
            '_all': '1', 'append': '1', 'channel': channel,
            'listpage': '2', 'offset': '0', 'pagesize': '30', 'sort': '75',
        }

        resp = self.fetch(url, params=params, headers={
            'Referer': 'https://v.qq.com/channel/tv',
        })
        if not resp:
            return []

        items = []
        try:
            text = resp.text
            # 从HTML中提取 title 属性
            matches = re.findall(
                r'<a[^>]*href="(https://v\.qq\.com/x/cover/[^"]*)"[^>]*title="([^"]*)"',
                text
            )
            for i, (url_str, title) in enumerate(matches[:30]):
                if title:
                    items.append({
                        'title': self._normalize_title(title),
                        'heat_value': max(1000, 10000 - i * 300),
                        'poster_url': '',
                        'rank': i + 1,
                        'category': category,
                        'is_finished': False,
                        'platform': 'tencent'
                    })

            # 补充封面图
            img_matches = re.findall(r'src="(https://[^"]*vcover[^"]*)"', text)
            for i, img_url in enumerate(img_matches):
                if i < len(items):
                    items[i]['poster_url'] = img_url

        except Exception as e:
            logger.error(f"[腾讯视频] HTML解析失败: {e}")

        if items:
            logger.info(f"[腾讯视频] HTML列表提取{len(items)}条{category}数据")

        return items
