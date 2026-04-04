import json
import re
import time
import random
from loguru import logger

from .base_crawler import BaseCrawler


class TencentCrawler(BaseCrawler):
    """
    腾讯视频热度采集器
    策略优先级:
      1. HotRankHttp 热搜榜API（多channelId尝试） — 返回heatScore
      2. 排行榜HTML页面解析 — 解析v.qq.com/rank页面中的热度值
      3. bu/pagesheet/list HTML — 提取标题/封面/热度
      4. pbaccess getPage API — 深度遍历子项
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
                        logger.error(f"[腾讯视频] 保存失败 {item['title']}: {e}")

            self.log_task('tencent_heat', 'success', saved_count)
            logger.info(f"[腾讯视频] 采集完成，共{len(results)}条，保存热度{saved_count}条")

        except Exception as e:
            logger.error(f"[腾讯视频] 采集异常: {e}")
            self.log_task('tencent_heat', 'failed', error_message=str(e))

        return results

    def _crawl_rank(self, category='tv'):
        # 方式1: HotRankHttp 热搜榜（有真实热度值heatScore）
        items = self._fetch_hot_rank(category)
        if items:
            return items

        # 方式2: 排行榜HTML页面
        items = self._fetch_rank_page_html(category)
        if items:
            return items

        # 方式3: bu/pagesheet/list HTML
        items = self._fetch_from_html_list(category)
        if items:
            return items

        # 方式4: pbaccess API
        items = self._fetch_from_pbaccess(category)
        return items

    # ----------------------------------------------------------------
    # 方式1: HotRankHttp — 腾讯视频热搜榜API
    # ----------------------------------------------------------------
    def _fetch_hot_rank(self, category):
        """
        腾讯视频热搜榜API。
        响应结构: data.navItemList[N].hotRankResult.rankItemList
        每个navItem是一个分类tab（热搜/电视剧/综艺等），
        rankItemList包含排行数据（title, heatScore等）。
        """
        headers = {
            'Content-Type': 'application/json',
            'Referer': 'https://v.qq.com/',
            'Origin': 'https://v.qq.com',
        }

        # 所有channelId返回相同navItemList，只需请求一次
        time.sleep(random.uniform(0.5, 1.5))
        try:
            resp = self.session.post(
                'https://pbaccess.video.qq.com/trpc.videosearch.hot_rank.HotRankServantHttp/HotRankHttp',
                json={'pageNum': 0, 'pageSize': 50, 'channelId': '2'},
                headers=headers, timeout=15
            )
            data = resp.json()
        except Exception as e:
            logger.error(f"[腾讯视频] HotRankHttp请求失败: {e}")
            return []

        # 从navItemList中找到对应分类的tab
        nav_list = data.get('data', {}).get('navItemList', [])
        if not nav_list:
            logger.warning("[腾讯视频] HotRankHttp无navItemList")
            return []

        # 分类关键词匹配
        category_keywords = {
            'tv': ['电视剧', '剧集', '电视'],
            'variety': ['综艺'],
        }
        keywords = category_keywords.get(category, ['电视剧'])

        # 遍历所有tab，优先找精确分类，其次用第一个有数据的tab（热搜=全部）
        target_tab = None
        fallback_tab = None

        for tab in nav_list:
            tab_name = tab.get('tabName', '')
            rank_result = tab.get('hotRankResult', {})
            rank_items = rank_result.get('rankItemList', [])

            if not rank_items:
                continue

            # 检查是否匹配目标分类
            if any(kw in tab_name for kw in keywords):
                target_tab = tab
                break

            # 第一个有数据的tab作为fallback（通常是"热搜"=全部）
            if fallback_tab is None:
                fallback_tab = tab

        chosen_tab = target_tab or fallback_tab
        if not chosen_tab:
            logger.warning("[腾讯视频] HotRankHttp所有tab均无rankItemList")
            return []

        tab_name = chosen_tab.get('tabName', '?')
        rank_result = chosen_tab.get('hotRankResult', {})
        rank_items = rank_result.get('rankItemList', [])

        logger.info(f"[腾讯视频] HotRank使用tab '{tab_name}', 共{len(rank_items)}条")

        items = []
        for i, item in enumerate(rank_items[:30]):
            title = (item.get('title', '') or item.get('name', '') or
                     item.get('showTitle', '') or '')
            if not title:
                continue

            # 热度值: 尝试多种字段名
            heat = 0
            for key in ['heatScore', 'hotScore', 'score', 'hot', 'heat',
                         'changeOrder', 'totalSize']:
                val = item.get(key)
                if val is not None:
                    try:
                        h = float(str(val).replace(',', ''))
                        if h > 0:
                            heat = h
                            break
                    except (ValueError, TypeError):
                        continue

            # 封面图
            poster = (item.get('picUrl', '') or item.get('coverUrl', '') or
                      item.get('pic', '') or '')

            items.append({
                'title': self._normalize_title(title),
                'heat_value': heat,
                'poster_url': poster,
                'rank': i + 1,
                'category': category,
                'is_finished': False,
            })

        if items:
            has_heat = sum(1 for x in items if x['heat_value'] > 0)
            logger.info(f"[腾讯视频] HotRank: {len(items)}条, {has_heat}条有热度")

        return items

    # ----------------------------------------------------------------
    # 方式2: 排行榜HTML页面
    # ----------------------------------------------------------------
    def _fetch_rank_page_html(self, category):
        """
        抓取腾讯视频排行榜HTML页面，解析嵌入的JSON数据。
        如果是SSR页面会包含 window.__INITIAL_DATA__ 等。
        """
        url_map = {
            'tv': [
                'https://v.qq.com/rank/detail/tv_hot',
                'https://v.qq.com/biu/ranks/?t=hotsearch&channel=tv',
                'https://v.qq.com/rank',
            ],
            'variety': [
                'https://v.qq.com/rank/detail/variety_hot',
                'https://v.qq.com/biu/ranks/?t=hotsearch&channel=variety',
            ],
        }

        for url in url_map.get(category, []):
            time.sleep(random.uniform(1, 2))
            try:
                resp = self.fetch(url, headers={'Referer': 'https://v.qq.com/'})
                if not resp:
                    continue

                text = resp.text
                items = []

                # 尝试提取嵌入的JSON数据
                for pattern in [
                    r'window\.__INITIAL_DATA__\s*=\s*(\{.+?\});\s*</script>',
                    r'window\.__NUXT__\s*=\s*(\{.+?\});\s*</script>',
                    r'window\.__pinia\s*=\s*(\{.+?\});\s*</script>',
                    r'__NEXT_DATA__[^>]*>\s*(\{.+?\})\s*</script>',
                ]:
                    match = re.search(pattern, text, re.DOTALL)
                    if match:
                        try:
                            json_data = json.loads(match.group(1))
                            items = self._extract_from_embedded_json(json_data, category)
                            if items:
                                logger.info(f"[腾讯视频] 排行HTML({url}): 提取{len(items)}条")
                                return items
                        except json.JSONDecodeError:
                            continue

                # 直接从HTML中提取排行数据
                items = self._parse_rank_html(text, category)
                if items:
                    logger.info(f"[腾讯视频] 排行HTML({url}): 解析{len(items)}条")
                    return items

            except Exception as e:
                logger.debug(f"[腾讯视频] 排行页({url}): {e}")
                continue

        return []

    def _extract_from_embedded_json(self, data, category):
        """从嵌入的JSON中递归查找排行数据"""
        items = []

        def _search(obj, depth=0):
            if depth > 8 or len(items) >= 30:
                return
            if isinstance(obj, list) and len(obj) >= 5:
                # 检查是否像排行列表（每项都有title类字段）
                has_titles = sum(1 for x in obj[:5]
                                if isinstance(x, dict) and
                                any(k in x for k in ('title', 'name', 'showTitle')))
                if has_titles >= 3:
                    for i, item in enumerate(obj[:30]):
                        if not isinstance(item, dict):
                            continue
                        title = (item.get('title', '') or item.get('name', '') or
                                 item.get('showTitle', '') or '')
                        heat = (item.get('heatScore', 0) or item.get('hotScore', 0) or
                                item.get('hot', 0) or item.get('score', 0) or
                                item.get('heat_value', 0) or 0)
                        poster = (item.get('picUrl', '') or item.get('cover', '') or
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
                    return
            if isinstance(obj, dict):
                for v in obj.values():
                    _search(v, depth + 1)
            elif isinstance(obj, list):
                for v in obj:
                    _search(v, depth + 1)

        _search(data)
        return items

    def _parse_rank_html(self, text, category):
        """直接从HTML标签中提取排行数据（带热度）"""
        items = []
        # 通用排行列表项模式：标题 + 热度数字
        # 匹配类似 "白日提灯" ... "24269" 这样的模式
        blocks = re.findall(
            r'title="([^"]{2,30})"[^>]*>.*?(\d{3,6})\s*(?:热度|热|分)',
            text, re.DOTALL
        )
        for i, (title, heat_str) in enumerate(blocks[:30]):
            try:
                heat = float(heat_str)
            except ValueError:
                heat = 0
            items.append({
                'title': self._normalize_title(title),
                'heat_value': heat,
                'poster_url': '',
                'rank': i + 1,
                'category': category,
                'is_finished': False,
            })
        return items

    # ----------------------------------------------------------------
    # 方式3: bu/pagesheet/list HTML解析
    # ----------------------------------------------------------------
    def _fetch_from_html_list(self, category):
        """
        从腾讯视频频道列表HTML中提取数据。
        此API已确认在服务器上可用。
        """
        channel = 'tv' if category == 'tv' else 'variety'

        resp = self.fetch(
            'https://v.qq.com/x/bu/pagesheet/list',
            params={
                '_all': '1', 'append': '1', 'channel': channel,
                'listpage': '2', 'offset': '0', 'pagesize': '30', 'sort': '75',
            },
            headers={'Referer': f'https://v.qq.com/channel/{channel}'}
        )
        if not resp:
            return []

        items = []
        try:
            text = resp.text

            # 分割每个list_item块
            item_blocks = re.split(r'<div[^>]*class="[^"]*list_item[^"]*"', text)

            for i, block in enumerate(item_blocks[1:31]):  # 跳过第一个空块
                # 提取标题
                title_match = re.search(r'title="([^"]{2,50})"', block)
                if not title_match:
                    continue
                title = title_match.group(1).strip()

                # 提取链接
                link_match = re.search(
                    r'href="(https://v\.qq\.com/x/cover/[^"]*)"', block)
                link = link_match.group(1) if link_match else ''

                # 提取封面图
                img_match = re.search(
                    r'src="(https?://[^"]*(?:vcover|puui|puic)[^"]*)"', block)
                if not img_match:
                    img_match = re.search(r'src="(https?://[^"]+\.(?:jpg|png))"', block)
                poster = img_match.group(1) if img_match else ''

                # 提取热度值（在HTML文本中查找数字+热度的模式）
                heat = 0
                heat_match = re.search(r'(\d[\d,]{2,})\s*(?:热度|热|万)', block)
                if heat_match:
                    heat_str = heat_match.group(1).replace(',', '')
                    try:
                        heat = float(heat_str)
                        if '万' in block[heat_match.start():heat_match.end() + 5]:
                            heat *= 10000
                    except ValueError:
                        heat = 0

                # 检查完结状态
                is_finished = bool(re.search(r'全\d+集|完结', block))

                items.append({
                    'title': self._normalize_title(title),
                    'heat_value': heat,
                    'poster_url': poster,
                    'rank': i + 1,
                    'category': category,
                    'is_finished': is_finished,
                })

        except Exception as e:
            logger.error(f"[腾讯视频] HTML列表解析失败: {e}")

        if items:
            has_heat = sum(1 for x in items if x['heat_value'] > 0)
            logger.info(f"[腾讯视频] HTML列表: {len(items)}条, {has_heat}条有热度")

        return items

    # ----------------------------------------------------------------
    # 方式4: pbaccess getPage API (深度遍历)
    # ----------------------------------------------------------------
    def _fetch_from_pbaccess(self, category):
        """pbaccess API — 深度遍历提取数据"""
        channel_map = {'tv': '100113', 'variety': '100109'}
        channel_id = channel_map.get(category, '100113')

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

        time.sleep(random.uniform(1, 2))

        try:
            resp = self.session.post(
                'https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/getPage',
                json=body,
                headers={
                    'Content-Type': 'application/json',
                    'Referer': 'https://v.qq.com/',
                    'Origin': 'https://v.qq.com',
                },
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"[腾讯视频] pbaccess请求失败: {e}")
            return []

        items = []
        try:
            card_list = data.get('data', {}).get('CardList', []) or []

            for card in card_list:
                # 深度查找所有children列表
                children = self._deep_find_children(card)
                if not children:
                    continue

                for i, child in enumerate(children[:30]):
                    parsed = self._deep_parse_child(child, i, category)
                    if parsed:
                        items.append(parsed)

                if items:
                    break

        except Exception as e:
            logger.error(f"[腾讯视频] pbaccess解析失败: {e}")

        if items:
            has_heat = sum(1 for x in items if x['heat_value'] > 0)
            logger.info(f"[腾讯视频] pbaccess: {len(items)}条, {has_heat}条有热度")

        return items

    def _deep_find_children(self, obj, depth=0):
        """递归查找包含多个子项的列表"""
        if depth > 5:
            return []
        if isinstance(obj, list) and len(obj) >= 5:
            # 检查是否每项都有params或title字段
            has_params = sum(1 for x in obj[:5]
                            if isinstance(x, dict) and
                            ('params' in x or 'title' in x))
            if has_params >= 3:
                return obj
        if isinstance(obj, dict):
            for v in obj.values():
                result = self._deep_find_children(v, depth + 1)
                if result:
                    return result
        if isinstance(obj, list):
            for v in obj:
                result = self._deep_find_children(v, depth + 1)
                if result:
                    return result
        return []

    def _deep_parse_child(self, child, index, category):
        """从child中提取数据，尝试params和顶层字段"""
        if not isinstance(child, dict):
            return None

        params = child.get('params', {}) or {}

        # 收集所有可能的字段（合并params和顶层）
        all_fields = {}
        all_fields.update(params)
        for k, v in child.items():
            if k != 'params' and isinstance(v, str):
                all_fields[k] = v

        # 提取标题 — 尝试所有已知的title字段名
        title = ''
        for key in ['title', 'show_title', 'uni_title', 'second_title',
                     'reportTitle', 'name', 'cover_title', 'main_title']:
            val = all_fields.get(key, '')
            if val and len(val) >= 2 and not val.startswith('http'):
                title = val
                break

        if not title:
            return None

        # 提取热度值
        heat = 0
        for key in ['hot_value', 'hotval', 'heatScore', 'score', 'hot_score',
                     'ckc_count', 'view_count', 'play_count', 'heat']:
            val = all_fields.get(key, '') or params.get(key, '')
            if val:
                try:
                    heat = float(str(val).replace(',', '')
                                 .replace('万', '0000').replace('亿', '00000000'))
                    if heat > 0:
                        break
                except (ValueError, TypeError):
                    continue

        # 提取封面
        poster = ''
        for key in ['new_pic_hz', 'image_url', 'pic', 'pic_160x90', 'pic_hz',
                     'pic_496x280', 'cover_url', 'horizontal_pic_url',
                     'posterUrl', 'cover_img']:
            val = all_fields.get(key, '')
            if val and val.startswith('http'):
                poster = val
                break

        # 判断完结
        is_finished = False
        for key in ['episode_updated', 'latest_updateDesc', 'second_title',
                     'markLabel', 'update_desc']:
            val = str(all_fields.get(key, ''))
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
        }
