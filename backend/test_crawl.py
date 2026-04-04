#!/usr/bin/env python3
"""
剧云榜 — 爬虫测试脚本 v3
测试四大平台（爱奇艺、腾讯视频、优酷、芒果TV）API可用性。

使用方法:
    cd /opt/juyunbang/backend
    python3 test_crawl.py          # 测试所有平台API（不写库）
    python3 test_crawl.py --save   # 测试并保存数据到数据库
"""
import sys
import os
import json
import requests
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('FLASK_ENV', 'production')


def create_session():
    s = requests.Session()
    s.trust_env = False
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    })
    return s


def test_tencent():
    print("\n" + "=" * 60)
    print("【腾讯视频】测试多种API接口")
    print("=" * 60)

    session = create_session()
    results = []

    for channel, cat_name in [('tv', '电视剧'), ('variety', '综艺')]:
        channel_map = {'tv': '100113', 'variety': '100109'}
        print(f"\n  --- {cat_name} ---")

        # 方式1: 热搜榜
        print(f"  [1] 测试热搜榜接口 ...")
        try:
            resp = session.post(
                'https://pbaccess.video.qq.com/trpc.videosearch.hot_rank.HotRankServantHttp/HotRankHttp',
                json={'pageNum': 0, 'pageSize': 30, 'channelId': channel_map.get(channel, '100113')},
                headers={'Content-Type': 'application/json', 'Referer': 'https://v.qq.com/'},
                timeout=15
            )
            data = resp.json()
            item_list = data.get('data', {}).get('itemList', []) or []
            if item_list:
                print(f"  ✅ 腾讯{cat_name}(热搜榜): 共 {len(item_list)} 条")
                for i, item in enumerate(item_list[:5]):
                    title = item.get('title', '')
                    heat = item.get('heatScore', 0)
                    poster = item.get('picUrl', '')
                    print(f"     [{i+1}] {title} | 热度={heat} | 封面={'✅' if poster else '❌'}")
                    results.append({'title': title, 'heat': heat})
                continue
            else:
                print(f"      热搜榜无数据")
        except Exception as e:
            print(f"      热搜榜失败: {e}")

        # 方式2: pbaccess getPage
        print(f"  [2] 测试 pbaccess getPage API ...")
        try:
            body = {
                'page_context': {'page_index': '0'},
                'page_params': {
                    'page_id': 'channel_list_second_page', 'page_type': 'operation',
                    'channel_id': channel_map.get(channel, '100113'),
                    'filter_params': 'sort=75', 'page': '0',
                },
                'page_bypass_params': {
                    'params': {'page_size': '30', 'page_num': '0', 'caller_id': '3000010', 'platform_id': '2'},
                    'global_params': {'ckey': '', 'vuession': ''},
                },
            }
            resp = session.post(
                'https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/getPage',
                json=body, headers={'Content-Type': 'application/json', 'Referer': 'https://v.qq.com/'},
                timeout=15
            )
            data = resp.json()
            card_list = data.get('data', {}).get('CardList', []) or []
            found_count = 0
            for card in card_list:
                children = card.get('children_list', {}).get('list', {}).get('cards', []) or []
                found_count += len(children)
            print(f"      pbaccess: CardList={len(card_list)}, children总数={found_count}")
        except Exception as e:
            print(f"      pbaccess失败: {e}")

        # 方式3: HTML列表
        print(f"  [3] 测试 HTML列表页 ...")
        try:
            resp = session.get('https://v.qq.com/x/bu/pagesheet/list', params={
                '_all': '1', 'append': '1', 'channel': channel,
                'listpage': '2', 'offset': '0', 'pagesize': '30', 'sort': '75'
            }, headers={'Referer': 'https://v.qq.com/channel/tv'}, timeout=15)
            titles = re.findall(r'title="([^"]{2,30})"', resp.text)
            titles = list(dict.fromkeys(titles))  # dedupe preserving order
            if titles:
                print(f"  ✅ 腾讯{cat_name}(HTML): 共 {len(titles)} 条")
                for i, t in enumerate(titles[:5]):
                    print(f"     [{i+1}] {t}")
            else:
                print(f"      HTML无数据")
        except Exception as e:
            print(f"      HTML失败: {e}")

    return results


def test_iqiyi():
    print("\n" + "=" * 60)
    print("【爱奇艺】测试排行榜API")
    print("=" * 60)

    session = create_session()
    results = []
    for cid, cat_name in [('2', '电视剧'), ('6', '综艺')]:
        print(f"\n  --- {cat_name} ---")

        # 主API: 风云榜
        print(f"  [1] 测试风云榜API ...")
        try:
            resp = session.get(
                'https://mesh.if.iqiyi.com/portal/lw/videolib/data/rank',
                params={'type': 'heat', 'cid': cid, 'limit': '30'}, timeout=15
            )
            data = resp.json()
            rank_list = data.get('data', {}).get('list', [])
            if rank_list:
                print(f"  ✅ 爱奇艺{cat_name}(风云榜): 共 {len(rank_list)} 条")
                for i, item in enumerate(rank_list[:5]):
                    title = item.get('name', '')
                    heat = item.get('hot', 0)
                    poster = item.get('imageUrl', '')
                    print(f"     [{i+1}] {title} | 站内热度={heat} | 封面={'✅' if poster else '❌'}")
                    results.append({'title': title, 'heat': heat})
                continue
            else:
                print(f"      风云榜无数据")
        except Exception as e:
            print(f"      风云榜失败: {e}")

        # 备用API: PCW
        print(f"  [2] 测试PCW备用API ...")
        try:
            resp = session.get(
                'https://pcw-api.iqiyi.com/search/recommend/list',
                params={'channel_id': cid, 'data_type': '1', 'mode': '24',
                        'page_id': '1', 'ret_num': '10'}, timeout=15
            )
            data = resp.json()
            items = data.get('data', {}).get('list', [])
            if items:
                print(f"  ✅ 爱奇艺{cat_name}(PCW): 共 {len(items)} 条")
                for i, item in enumerate(items[:5]):
                    title = item.get('title', '')
                    heat = item.get('hot', 0) or item.get('play_count', 0)
                    poster = item.get('imageUrl', '') or item.get('img', '')
                    desc = item.get('focus', '') or item.get('description', '')
                    print(f"     [{i+1}] {title} | hot={heat} | 封面={'✅' if poster else '❌'} | {desc[:30]}")
                continue
        except Exception as e:
            print(f"      PCW失败: {e}")

        print(f"  ❌ 爱奇艺{cat_name}: 所有接口均无数据")

    return results


def test_mgtv():
    print("\n" + "=" * 60)
    print("【芒果TV】测试排行榜API（检查热度字段）")
    print("=" * 60)

    session = create_session()
    results = []
    for channel_id, cat_name in [('2', '电视剧'), ('3', '综艺')]:
        try:
            resp = session.get(
                'https://pianku.api.mgtv.com/rider/list/pcweb/v3',
                params={'allowedRC': '1', 'platform': 'pcweb', 'channelId': channel_id,
                        'pn': '1', 'pc': '30', 'hudong': '1', 'orderType': 'c2'}, timeout=15
            )
            data = resp.json()
            hit_list = data.get('data', {}).get('hitDocs', [])
            if hit_list:
                print(f"\n  ✅ 芒果TV{cat_name}: 共 {len(hit_list)} 条")
                # 检查第一条的所有字段
                first = hit_list[0]
                heat_fields = {k: v for k, v in first.items()
                               if isinstance(v, (int, float)) and v > 0}
                print(f"     第一条有值的数字字段: {heat_fields}")

                for i, item in enumerate(hit_list[:5]):
                    title = item.get('title', '')
                    playcnt = item.get('playcnt', 0)
                    allcnt = item.get('allcnt', 0)
                    views = item.get('views', 0)
                    img = item.get('img', '')
                    update = item.get('updateInfo', '')

                    is_fin = ('全' in update and '集' in update) or '完结' in update

                    heat = playcnt or allcnt or views or 0
                    status = '完结' if is_fin else '在播'
                    print(f"     [{i+1}] {title} | playcnt={playcnt} allcnt={allcnt} views={views} | 封面={'✅' if img else '❌'} | {update} | {status}")
                    results.append({'title': title, 'heat': heat})
            else:
                print(f"  ❌ 芒果TV{cat_name}: 无数据")
        except Exception as e:
            print(f"  ❌ 芒果TV{cat_name}: {e}")
    return results


def test_youku():
    print("\n" + "=" * 60)
    print("【优酷】测试排行API")
    print("=" * 60)

    session = create_session()
    results = []
    for cid, cat_name in [('97', '电视剧'), ('85', '综艺')]:
        print(f"\n  --- {cat_name} ---")

        # 方式1: 移动端API
        print(f"  [1] 测试移动端网关API ...")
        try:
            resp = session.get(
                'https://acs.youku.com/h5/mtop.youku.columbus.gateway.new.execute/1.0/',
                params={
                    'jsv': '2.7.2', 'appKey': '24679788',
                    'api': 'mtop.youku.columbus.gateway.new.execute', 'v': '1.0',
                    'data': json.dumps({
                        'ms_codes': '2019030100',
                        'params': json.dumps({'st': '1', 'pn': '1', 'ps': '30', 'cid': cid})
                    })
                },
                headers={'Referer': 'https://www.youku.com/'}, timeout=15
            )
            data = resp.json()
            result = data.get('data', {})
            if isinstance(result, str):
                result = json.loads(result)
            show_list = result.get('data', {}).get('nodes', []) or result.get('nodes', []) or result.get('list', []) or []
            if show_list:
                print(f"  ✅ 优酷{cat_name}(API): 共 {len(show_list)} 条")
                for i, item in enumerate(show_list[:5]):
                    title = item.get('title', '') or item.get('show_name', '')
                    heat = item.get('heat', 0)
                    img = item.get('img', '')
                    print(f"     [{i+1}] {title} | 热度={heat} | 封面={'✅' if img else '❌'}")
                    results.append({'title': title, 'heat': heat})
                continue
            else:
                print(f"      API无数据")
        except Exception as e:
            print(f"      API失败: {e}")

        # 方式2: HTML
        print(f"  [2] 测试HTML列表页 ...")
        try:
            resp = session.get(f'https://list.youku.com/category/show/c_{cid}/s_1_d_1.html',
                               headers={'Referer': 'https://www.youku.com/'}, timeout=15)
            if resp.status_code == 200:
                title_count = len(re.findall(r'title="([^"]+)"', resp.text))
                print(f"      HTML页面: 找到 {title_count} 个title属性")
                if title_count > 5:
                    print(f"  ✅ HTML采集可行")
                else:
                    print(f"      HTML内容不足")
            else:
                print(f"      HTTP {resp.status_code}")
        except Exception as e:
            print(f"      HTML失败: {e}")

        print(f"  ⚠️ 优酷{cat_name}: 可能因反爬限制无法采集")

    return results


def run_full_crawl():
    """运行完整采集流程（写入数据库）"""
    print("\n" + "=" * 60)
    print("运行完整采集流程（写入数据库，仅保存在播剧）")
    print("=" * 60)

    try:
        from app import create_app
        app = create_app()

        with app.app_context():
            from crawlers.base_crawler import BaseCrawler
            from crawlers.iqiyi_crawler import IqiyiCrawler
            from crawlers.tencent_crawler import TencentCrawler
            from crawlers.youku_crawler import YoukuCrawler
            from crawlers.mgtv_crawler import MgtvCrawler

            BaseCrawler.clear_drama_cache()

            crawlers = [
                IqiyiCrawler(),
                TencentCrawler(),
                YoukuCrawler(),
                MgtvCrawler(),
            ]

            total = 0
            for crawler in crawlers:
                try:
                    results = crawler.crawl()
                    count = len(results) if results else 0
                    total += count
                    print(f"\n  {crawler.platform_name}: 采集 {count} 条")
                except Exception as e:
                    print(f"\n  {crawler.platform_name}: {e}")

            print(f"\n{'=' * 60}")
            print(f"采集完成！共处理 {total} 条数据")
            print(f"（仅在播剧被写入热度表，已完结剧自动跳过）")
            print(f"{'=' * 60}")

    except Exception as e:
        print(f"\n采集失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print("剧云榜 — 爬虫API测试工具 v3")
    print(f"平台: 爱奇艺 / 腾讯视频 / 优酷 / 芒果TV")
    print(f"Python {sys.version}")

    if '--save' in sys.argv:
        run_full_crawl()
    else:
        print("\n测试模式：只检测API可用性，不写入数据库")
        print("添加 --save 参数可执行完整采集（仅在播剧写入）\n")

        test_iqiyi()
        test_tencent()
        test_mgtv()
        test_youku()

        print("\n" + "=" * 60)
        print("测试完成！")
        print("如需采集写入数据库: python3 test_crawl.py --save")
        print("=" * 60)
