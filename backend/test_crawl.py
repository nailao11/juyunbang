#!/usr/bin/env python3
"""
剧云榜 — 爬虫测试脚本
在服务器上运行此脚本测试各平台API是否可用，以及数据采集是否正常。

使用方法:
    cd /opt/juyunbang/backend
    python3 test_crawl.py          # 测试所有平台API（不写库）
    python3 test_crawl.py --save   # 测试并保存数据到数据库
"""
import sys
import os
import json
import requests

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('FLASK_ENV', 'production')


def test_bilibili():
    """测试B站API"""
    print("\n" + "="*60)
    print("【B站】测试排行榜API")
    print("="*60)

    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    results = []
    for season_type, cat_name in [('5', '电视剧'), ('7', '综艺'), ('1', '番剧')]:
        url = 'https://api.bilibili.com/pgc/web/rank/list'
        params = {'day': '3', 'season_type': season_type}

        try:
            resp = session.get(url, params=params, timeout=15)
            data = resp.json()
            if data.get('code') == 0:
                rank_list = data.get('result', {}).get('list', [])
                print(f"\n  ✅ B站{cat_name}排行: 共 {len(rank_list)} 条")
                for i, item in enumerate(rank_list[:3]):
                    title = item.get('title', '')
                    heat = item.get('stat', {}).get('view', 0)
                    cover = item.get('ss_horizontal_cover', '') or item.get('cover', '')
                    print(f"     [{i+1}] {title} | 播放={heat:,} | 封面={'✅' if cover else '❌'}")
                    results.append({'title': title, 'heat': heat, 'cover': cover, 'cat': cat_name})
            else:
                print(f"  ❌ B站{cat_name}: API返回错误 code={data.get('code')}")
        except Exception as e:
            print(f"  ❌ B站{cat_name}: 请求失败 {e}")

    return results


def test_tencent():
    """测试腾讯视频API"""
    print("\n" + "="*60)
    print("【腾讯视频】测试排行榜API")
    print("="*60)

    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/json',
        'Referer': 'https://v.qq.com/',
        'Origin': 'https://v.qq.com',
    })

    results = []
    for channel_id, cat_name in [('100113', '电视剧'), ('100109', '综艺')]:
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
                'params': {'page_size': '30', 'page_num': '0', 'caller_id': '3000010', 'platform_id': '2'},
                'global_params': {'ckey': '', 'vuession': ''},
            },
        }

        try:
            resp = session.post(
                'https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/getPage',
                json=body, timeout=15
            )
            data = resp.json()
            card_list = data.get('data', {}).get('CardList', []) or data.get('data', {}).get('card_list', []) or []

            items_found = []
            for card in card_list:
                children = (
                    card.get('children_list', {}).get('list', {}).get('cards', []) or
                    card.get('card', {}).get('card_data', {}).get('cards', []) or []
                )
                for child in children[:30]:
                    params = child.get('params', {})
                    title = params.get('title', '') or params.get('show_title', '')
                    heat = params.get('hot_value', 0) or params.get('score', 0)
                    poster = params.get('new_pic_hz', '') or params.get('image_url', '') or params.get('pic', '')
                    if title:
                        items_found.append({'title': title, 'heat': heat, 'cover': poster})
                if items_found:
                    break

            if items_found:
                print(f"\n  ✅ 腾讯{cat_name}排行: 共 {len(items_found)} 条")
                for i, item in enumerate(items_found[:3]):
                    print(f"     [{i+1}] {item['title']} | 热度={item['heat']} | 封面={'✅' if item['cover'] else '❌'}")
                results.extend(items_found[:3])
            else:
                print(f"  ⚠️ 腾讯{cat_name}: pbaccess API返回数据为空")

        except Exception as e:
            print(f"  ❌ 腾讯{cat_name}: 请求失败 {e}")

    # 测试备用接口
    if not results:
        print("\n  🔄 主接口无数据，测试热搜榜备用接口...")
        try:
            body2 = {'pageNum': 0, 'pageSize': 30, 'channelId': '100113'}
            resp = session.post(
                'https://pbaccess.video.qq.com/trpc.videosearch.hot_rank.HotRankServantHttp/HotRankHttp',
                json=body2, timeout=15
            )
            data = resp.json()
            item_list = data.get('data', {}).get('itemList', []) or []
            if item_list:
                print(f"  ✅ 热搜榜备用接口: 共 {len(item_list)} 条")
                for i, item in enumerate(item_list[:3]):
                    title = item.get('title', '')
                    heat = item.get('heatScore', 0)
                    poster = item.get('picUrl', '')
                    print(f"     [{i+1}] {title} | 热度={heat} | 封面={'✅' if poster else '❌'}")
            else:
                print(f"  ❌ 热搜榜备用接口也无数据")
        except Exception as e:
            print(f"  ❌ 热搜榜备用接口失败: {e}")

    return results


def test_iqiyi():
    """测试爱奇艺API"""
    print("\n" + "="*60)
    print("【爱奇艺】测试排行榜API")
    print("="*60)

    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    results = []
    for cid, cat_name in [('2', '电视剧'), ('6', '综艺')]:
        # 主API
        url = 'https://mesh.if.iqiyi.com/portal/lw/videolib/data/rank'
        params = {'type': 'heat', 'cid': cid, 'limit': '30'}

        try:
            resp = session.get(url, params=params, timeout=15)
            data = resp.json()
            rank_list = data.get('data', {}).get('list', [])
            if rank_list:
                print(f"\n  ✅ 爱奇艺{cat_name}排行(主API): 共 {len(rank_list)} 条")
                for i, item in enumerate(rank_list[:3]):
                    title = item.get('name', '')
                    heat = item.get('hot', 0)
                    poster = item.get('imageUrl', '') or item.get('img', '')
                    print(f"     [{i+1}] {title} | 热度={heat} | 封面={'✅' if poster else '❌'}")
                    results.append({'title': title, 'heat': heat, 'cover': poster})
            else:
                print(f"  ⚠️ 爱奇艺{cat_name}: 主API无数据，尝试备用...")
                # 备用API
                url2 = 'https://pcw-api.iqiyi.com/search/recommend/list'
                params2 = {'channel_id': cid, 'data_type': '1', 'mode': '24', 'page_id': '1', 'ret_num': '30'}
                resp2 = session.get(url2, params=params2, timeout=15)
                data2 = resp2.json()
                items = data2.get('data', {}).get('list', [])
                if items:
                    print(f"  ✅ 爱奇艺{cat_name}(备用API): 共 {len(items)} 条")
                    for i, item in enumerate(items[:3]):
                        title = item.get('title', '')
                        print(f"     [{i+1}] {title}")
                else:
                    print(f"  ❌ 爱奇艺{cat_name}: 所有API均无数据")
        except Exception as e:
            print(f"  ❌ 爱奇艺{cat_name}: {e}")

    return results


def test_mgtv():
    """测试芒果TV API"""
    print("\n" + "="*60)
    print("【芒果TV】测试排行榜API")
    print("="*60)

    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    results = []
    for channel_id, cat_name in [('2', '电视剧'), ('3', '综艺')]:
        url = 'https://pianku.api.mgtv.com/rider/list/pcweb/v3'
        params = {
            'allowedRC': '1', 'platform': 'pcweb',
            'channelId': channel_id, 'pn': '1', 'pc': '30',
            'hudong': '1', 'orderType': 'c2'
        }

        try:
            resp = session.get(url, params=params, timeout=15)
            data = resp.json()
            hit_list = data.get('data', {}).get('hitDocs', [])
            if hit_list:
                print(f"\n  ✅ 芒果TV{cat_name}排行: 共 {len(hit_list)} 条")
                for i, item in enumerate(hit_list[:3]):
                    title = item.get('title', '')
                    heat = item.get('playcnt', 0)
                    img = item.get('img', '')
                    print(f"     [{i+1}] {title} | 热度={heat} | 封面={'✅' if img else '❌'}")
                    results.append({'title': title, 'heat': heat, 'cover': img})
            else:
                print(f"  ❌ 芒果TV{cat_name}: 无数据")
        except Exception as e:
            print(f"  ❌ 芒果TV{cat_name}: {e}")

    return results


def test_youku():
    """测试优酷API"""
    print("\n" + "="*60)
    print("【优酷】测试排行榜API")
    print("="*60)

    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.youku.com/',
    })

    results = []
    for cid, cat_name in [('97', '电视剧'), ('85', '综艺')]:
        url = 'https://acs.youku.com/h5/mtop.youku.columbus.gateway.new.execute/1.0/'
        params = {
            'jsv': '2.7.2', 'appKey': '24679788',
            'api': 'mtop.youku.columbus.gateway.new.execute', 'v': '1.0',
            'data': json.dumps({
                'ms_codes': '2019030100',
                'params': json.dumps({'st': '1', 'pn': '1', 'ps': '30', 'cid': cid})
            })
        }

        try:
            resp = session.get(url, params=params, timeout=15)
            data = resp.json()
            result = data.get('data', {})
            if isinstance(result, str):
                result = json.loads(result)

            show_list = (
                result.get('data', {}).get('nodes', []) or
                result.get('nodes', []) or
                result.get('list', []) or []
            )

            if show_list:
                print(f"\n  ✅ 优酷{cat_name}排行: 共 {len(show_list)} 条")
                for i, item in enumerate(show_list[:3]):
                    title = item.get('title', '') or item.get('show_name', '')
                    heat = item.get('heat', 0) or item.get('hot_value', 0)
                    img = item.get('img', '') or item.get('cover', '')
                    print(f"     [{i+1}] {title} | 热度={heat} | 封面={'✅' if img else '❌'}")
                    results.append({'title': title, 'heat': heat, 'cover': img})
            else:
                print(f"  ⚠️ 优酷{cat_name}: API无数据（优酷反爬较严，属正常现象）")
        except Exception as e:
            print(f"  ❌ 优酷{cat_name}: {e}")

    return results


def run_full_crawl():
    """运行完整的爬虫采集流程（写入数据库）"""
    print("\n" + "="*60)
    print("🚀 运行完整采集流程（写入数据库）")
    print("="*60)

    try:
        from app import create_app
        app = create_app()

        with app.app_context():
            from crawlers.base_crawler import BaseCrawler
            from crawlers.bilibili_crawler import BilibiliCrawler
            from crawlers.iqiyi_crawler import IqiyiCrawler
            from crawlers.tencent_crawler import TencentCrawler
            from crawlers.youku_crawler import YoukuCrawler
            from crawlers.mgtv_crawler import MgtvCrawler

            BaseCrawler.clear_drama_cache()

            crawlers = [
                BilibiliCrawler(),
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
                    print(f"\n  {crawler.platform_name}: 采集 {count} 条数据")
                except Exception as e:
                    print(f"\n  ❌ {crawler.platform_name} 采集失败: {e}")

            print(f"\n{'='*60}")
            print(f"✅ 采集完成！共采集 {total} 条数据，已写入数据库。")
            print(f"{'='*60}")

    except Exception as e:
        print(f"\n❌ 采集失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print("剧云榜 — 爬虫API测试工具")
    print(f"Python {sys.version}")

    if '--save' in sys.argv:
        run_full_crawl()
    else:
        print("\n📡 测试模式：只检测API可用性，不写入数据库")
        print("   添加 --save 参数可执行完整采集并写入数据库\n")

        test_bilibili()
        test_tencent()
        test_iqiyi()
        test_mgtv()
        test_youku()

        print("\n" + "="*60)
        print("测试完成！")
        print("如需执行采集并写入数据库，请运行: python3 test_crawl.py --save")
        print("="*60)
