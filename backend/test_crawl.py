#!/usr/bin/env python3
"""
剧云榜 — 爬虫测试脚本 v3
仅测试四大平台: 爱奇艺、腾讯视频、优酷、芒果TV

使用方法:
    cd /opt/juyunbang/backend
    python3 test_crawl.py          # 测试API可用性（不写库）
    python3 test_crawl.py --save   # 执行完整采集并写入数据库
    python3 test_crawl.py --debug  # 运行深度调试（等同 debug_apis.py）
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
    print("【腾讯视频】测试")
    print("=" * 60)

    session = create_session()
    results = []

    for channel, cat_name in [('tv', '电视剧'), ('variety', '综艺')]:
        channel_map = {'tv': '100113', 'variety': '100109'}
        print(f"\n  --- {cat_name} ---")

        # 方式1: HotRankHttp热搜榜（多channelId）
        hot_found = False
        for cid in ['100173', '100113', '150203']:
            print(f"  [热搜榜] channelId={cid} ...")
            try:
                resp = session.post(
                    'https://pbaccess.video.qq.com/trpc.videosearch.hot_rank.HotRankServantHttp/HotRankHttp',
                    json={'pageNum': 0, 'pageSize': 30, 'channelId': cid},
                    headers={'Content-Type': 'application/json',
                             'Referer': 'https://v.qq.com/'},
                    timeout=15
                )
                data = resp.json()
                # 尝试多种响应路径
                for path in ['itemList', 'rankItemList', 'list', 'items']:
                    items = data.get('data', {}).get(path, [])
                    if items:
                        has_heat = sum(1 for x in items if x.get('heatScore', 0) or x.get('hotScore', 0))
                        print(f"    找到 {len(items)} 条, {has_heat}条有热度")
                        for i, item in enumerate(items[:5]):
                            title = item.get('title', '')
                            heat = item.get('heatScore', 0) or item.get('hotScore', 0)
                            poster = item.get('picUrl', '')
                            print(f"    [{i+1}] {title} | 热度={heat} | 封面={'有' if poster else '无'}")
                            results.append({'title': title, 'heat': heat})
                        hot_found = True
                        break
                if hot_found:
                    break
                if not items:
                    # 打印实际响应结构帮助调试
                    data_keys = list(data.get('data', {}).keys()) if isinstance(data.get('data'), dict) else []
                    print(f"    data字段: {data_keys}")
            except Exception as e:
                print(f"    失败: {e}")

        if hot_found:
            continue

        # 方式2: bu/pagesheet/list HTML
        print(f"  [HTML列表] bu/pagesheet/list ...")
        try:
            resp = session.get('https://v.qq.com/x/bu/pagesheet/list', params={
                '_all': '1', 'append': '1', 'channel': channel,
                'listpage': '2', 'offset': '0', 'pagesize': '30', 'sort': '75'
            }, headers={'Referer': 'https://v.qq.com/channel/tv'}, timeout=15)

            text = resp.text
            # 分割每个list_item
            blocks = re.split(r'<div[^>]*class="[^"]*list_item[^"]*"', text)
            found = []
            for block in blocks[1:]:
                title_m = re.search(r'title="([^"]{2,50})"', block)
                if title_m:
                    title = title_m.group(1)
                    # 查找热度数字
                    heat_m = re.search(r'(\d{3,6})\s*(?:热度|热)', block)
                    heat = int(heat_m.group(1)) if heat_m else 0
                    # 查找封面
                    img_m = re.search(r'src="(https?://[^"]+\.(?:jpg|png))"', block)
                    poster = img_m.group(1) if img_m else ''
                    found.append({'title': title, 'heat': heat, 'poster': poster})

            if found:
                has_heat = sum(1 for x in found if x['heat'] > 0)
                print(f"    HTML解析: {len(found)}条, {has_heat}条有热度")
                for i, item in enumerate(found[:5]):
                    print(f"    [{i+1}] {item['title']} | 热度={item['heat']} | 封面={'有' if item['poster'] else '无'}")
                results.extend(found[:5])
            else:
                print(f"    HTML无list_item数据")
        except Exception as e:
            print(f"    HTML失败: {e}")

        # 方式3: pbaccess
        print(f"  [pbaccess] getPage API ...")
        try:
            body = {
                'page_context': {'page_index': '0'},
                'page_params': {
                    'page_id': 'channel_list_second_page',
                    'page_type': 'operation',
                    'channel_id': channel_map.get(channel, '100113'),
                    'filter_params': 'sort=75', 'page': '0',
                },
                'page_bypass_params': {
                    'params': {'page_size': '30', 'page_num': '0',
                               'caller_id': '3000010', 'platform_id': '2'},
                    'global_params': {'ckey': '', 'vuession': ''},
                },
            }
            resp = session.post(
                'https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/getPage',
                json=body, headers={'Content-Type': 'application/json',
                                     'Referer': 'https://v.qq.com/'},
                timeout=15
            )
            data = resp.json()
            card_list = data.get('data', {}).get('CardList', []) or []
            total_children = 0
            parsed_items = []
            for card in card_list:
                children = _deep_find_list(card)
                total_children += len(children)
                for i, child in enumerate(children[:5]):
                    params = child.get('params', {}) or {}
                    title = ''
                    for k in ['title', 'show_title', 'uni_title', 'second_title']:
                        title = params.get(k, '') or child.get(k, '')
                        if title:
                            break
                    heat = 0
                    for k in ['hot_value', 'hotval', 'score', 'ckc_count']:
                        v = params.get(k, '') or child.get(k, '')
                        if v:
                            try:
                                heat = float(str(v).replace(',', ''))
                            except ValueError:
                                pass
                    if title:
                        parsed_items.append({'title': title, 'heat': heat})

            print(f"    CardList={len(card_list)}, children总数={total_children}")
            if parsed_items:
                print(f"    解析出{len(parsed_items)}条:")
                for i, item in enumerate(parsed_items[:5]):
                    print(f"    [{i+1}] {item['title']} | 热度={item['heat']}")
            else:
                print(f"    未能解析出标题（字段名不匹配，请运行 debug_apis.py 查看完整结构）")
        except Exception as e:
            print(f"    pbaccess失败: {e}")

    return results


def test_iqiyi():
    print("\n" + "=" * 60)
    print("【爱奇艺】测试")
    print("=" * 60)

    session = create_session()
    results = []

    for cid, cat_name in [('2', '电视剧'), ('6', '综艺')]:
        print(f"\n  --- {cat_name} ---")

        # 方式1: mesh风云榜
        print(f"  [风云榜] mesh API ...")
        found = False
        for type_val in ['heat', 'hot']:
            try:
                resp = session.get(
                    'https://mesh.if.iqiyi.com/portal/lw/videolib/data/rank',
                    params={'type': type_val, 'cid': cid, 'limit': '30'}, timeout=15
                )
                data = resp.json()
                rank_list = data.get('data', {}).get('list', [])
                if rank_list:
                    has_heat = sum(1 for x in rank_list if x.get('hot', 0) > 0)
                    print(f"    type={type_val}: {len(rank_list)}条, {has_heat}条有热度")
                    for i, item in enumerate(rank_list[:5]):
                        title = item.get('name', '')
                        heat = item.get('hot', 0)
                        poster = item.get('imageUrl', '')
                        print(f"    [{i+1}] {title} | 热度={heat} | 封面={'有' if poster else '无'}")
                        results.append({'title': title, 'heat': heat})
                    found = True
                    break
            except Exception as e:
                print(f"    type={type_val}: {e}")

        if found:
            continue

        # 方式2: 排行页HTML
        print(f"  [排行页] HTML解析 ...")
        for url in [f'https://www.iqiyi.com/ranks/热度/{cid}', 'https://www.iqiyi.com/ranks']:
            try:
                resp = session.get(url, timeout=15)
                match = re.search(r'window\.__INITIAL_DATA__\s*=\s*(\{.+?\});\s*</script>',
                                  resp.text, re.DOTALL)
                if match:
                    jd = json.loads(match.group(1))
                    # 递归查找含title的列表
                    rank_items = _find_rank_list(jd)
                    if rank_items:
                        has_heat = sum(1 for x in rank_items if x.get('hot', 0) or x.get('score', 0))
                        print(f"    {url}: 找到{len(rank_items)}条, {has_heat}条有热度")
                        for i, item in enumerate(rank_items[:5]):
                            title = item.get('name', '') or item.get('title', '')
                            heat = item.get('hot', 0) or item.get('score', 0)
                            print(f"    [{i+1}] {title} | 热度={heat}")
                            results.append({'title': title, 'heat': heat})
                        found = True
                        break
                    else:
                        print(f"    {url}: 有__INITIAL_DATA__但未找到排行列表")
                else:
                    print(f"    {url}: 无__INITIAL_DATA__")
            except Exception as e:
                print(f"    {url}: {e}")

        if found:
            continue

        # 方式3: PCW API
        print(f"  [PCW] 推荐API ...")
        for mode in ['24', '11']:
            try:
                resp = session.get(
                    'https://pcw-api.iqiyi.com/search/recommend/list',
                    params={'channel_id': cid, 'data_type': '1', 'mode': mode,
                            'page_id': '1', 'ret_num': '10'},
                    timeout=15
                )
                data = resp.json()
                items = data.get('data', {}).get('list', [])
                if items:
                    has_heat = sum(1 for x in items if x.get('hot', 0) > 0)
                    print(f"    mode={mode}: {len(items)}条, {has_heat}条有热度")
                    for i, item in enumerate(items[:5]):
                        title = item.get('title', '')
                        heat = item.get('hot', 0) or item.get('play_count', 0)
                        poster = item.get('imageUrl', '') or item.get('img', '')
                        desc = (item.get('focus', '') or item.get('description', ''))[:30]
                        print(f"    [{i+1}] {title} | hot={heat} | 封面={'有' if poster else '无'} | {desc}")
                    results.extend([{'title': x.get('title', ''), 'heat': x.get('hot', 0)} for x in items[:5]])
                    break
            except Exception as e:
                print(f"    mode={mode}: {e}")

    return results


def test_mgtv():
    print("\n" + "=" * 60)
    print("【芒果TV】测试")
    print("=" * 60)

    session = create_session()
    results = []

    for channel_id, cat_name in [('2', '电视剧'), ('3', '综艺')]:
        print(f"\n  --- {cat_name} ---")

        # 方式1: 其他排行API
        for api_name, url, params in [
            ('channelrank', 'https://vc.mgtv.com/v2/list/channelrank',
             {'channelId': channel_id, 'pageNo': '1', 'pageSize': '30'}),
            ('mobile rank', 'https://mobile.api.mgtv.com/v8/video/rank',
             {'channelId': channel_id, 'pageNo': '1', 'pageSize': '30'}),
        ]:
            print(f"  [{api_name}] ...")
            try:
                resp = session.get(url, params=params, timeout=15)
                data = resp.json()
                # 查找列表数据
                items = (data.get('data', {}).get('list', []) or
                         data.get('data', {}).get('items', []) or
                         data.get('data', {}).get('hitDocs', []) or [])
                if items:
                    print(f"    {len(items)}条")
                    for i, item in enumerate(items[:3]):
                        title = item.get('title', '') or item.get('name', '')
                        heat = next((item.get(k, 0) for k in ['hot', 'heat', 'score', 'playcnt']
                                     if item.get(k, 0)), 0)
                        print(f"    [{i+1}] {title} | 热度={heat}")
                else:
                    dkeys = list(data.get('data', {}).keys()) if isinstance(data.get('data'), dict) else []
                    print(f"    无列表数据, data字段={dkeys}")
            except Exception as e:
                print(f"    {e}")

        # 方式2: pianku API
        print(f"  [pianku] 列表API ...")
        try:
            resp = session.get(
                'https://pianku.api.mgtv.com/rider/list/pcweb/v3',
                params={'allowedRC': '1', 'platform': 'pcweb', 'channelId': channel_id,
                        'pn': '1', 'pc': '30', 'hudong': '1', 'orderType': 'c2'},
                timeout=15
            )
            data = resp.json()
            hit_list = data.get('data', {}).get('hitDocs', [])
            if hit_list:
                # 检查哪些数字字段有值
                first = hit_list[0]
                nonzero = {k: v for k, v in first.items() if isinstance(v, (int, float)) and v > 0}
                print(f"    {len(hit_list)}条, 第一条有值数字字段: {nonzero}")

                for i, item in enumerate(hit_list[:5]):
                    title = item.get('title', '')
                    playcnt = item.get('playcnt', 0)
                    allcnt = item.get('allcnt', 0)
                    views = item.get('views', 0)
                    img = item.get('img', '')
                    update = item.get('updateInfo', '')
                    is_fin = ('全' in update and '集' in update) or '完结' in update
                    print(f"    [{i+1}] {title} | playcnt={playcnt} allcnt={allcnt} views={views} | 封面={'有' if img else '无'} | {update} | {'完结' if is_fin else '在播'}")
                    results.append({'title': title, 'heat': playcnt or allcnt or views})
            else:
                print(f"    pianku无数据")
        except Exception as e:
            print(f"    pianku失败: {e}")

    return results


def test_youku():
    print("\n" + "=" * 60)
    print("【优酷】测试")
    print("=" * 60)

    session = create_session()
    results = []

    for cid, cat_name in [('97', '电视剧'), ('85', '综艺')]:
        print(f"\n  --- {cat_name} ---")

        # 方式1: 排行页HTML
        print(f"  [排行页] HTML ...")
        for url in [f'https://www.youku.com/category/show/c_{cid}_s_1_d_1.html',
                     'https://www.youku.com/rank']:
            try:
                resp = session.get(url, headers={'Referer': 'https://www.youku.com/'}, timeout=15)
                if resp.status_code == 200:
                    titles = re.findall(r'title="([^"]{2,30})"', resp.text)
                    titles = [t for t in titles if not any(s in t for s in ['优酷', '登录', '首页', '客户端'])]
                    titles = list(dict.fromkeys(titles))
                    if titles:
                        print(f"    {url}: 找到{len(titles)}个标题")
                        for i, t in enumerate(titles[:5]):
                            print(f"    [{i+1}] {t}")
                    else:
                        print(f"    {url}: 无标题")

                    # 检查嵌入JSON
                    for pat_name in ['__INITIAL_DATA__', '__NEXT_DATA__']:
                        match = re.search(rf'window\.{pat_name}\s*=\s*(\{{.+?\}});\s*</script>',
                                          resp.text, re.DOTALL)
                        if match:
                            print(f"    发现{pat_name}!")
                else:
                    print(f"    {url}: HTTP {resp.status_code}")
            except Exception as e:
                print(f"    {url}: {e}")

        # 方式2: 移动端API
        print(f"  [API] 移动端网关 ...")
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
            show_list = (result.get('data', {}).get('nodes', []) or
                         result.get('nodes', []) or result.get('list', []) or [])
            if show_list:
                print(f"    API: {len(show_list)}条")
                for i, item in enumerate(show_list[:5]):
                    title = item.get('title', '') or item.get('show_name', '')
                    heat = item.get('heat', 0)
                    print(f"    [{i+1}] {title} | 热度={heat}")
            else:
                print(f"    API无数据")
        except Exception as e:
            print(f"    API失败: {e}")

    return results


def _deep_find_list(obj, depth=0):
    """递归查找children列表"""
    if depth > 5:
        return []
    if isinstance(obj, list) and len(obj) >= 5:
        if obj and isinstance(obj[0], dict):
            return obj
    if isinstance(obj, dict):
        for v in obj.values():
            r = _deep_find_list(v, depth + 1)
            if r:
                return r
    if isinstance(obj, list):
        for v in obj:
            r = _deep_find_list(v, depth + 1)
            if r:
                return r
    return []


def _find_rank_list(data, depth=0):
    """递归查找含title/name的排行列表"""
    if depth > 8:
        return []
    if isinstance(data, list) and len(data) >= 5:
        has_titles = sum(1 for x in data[:5]
                         if isinstance(x, dict) and ('name' in x or 'title' in x))
        if has_titles >= 3:
            return data
    if isinstance(data, dict):
        for v in data.values():
            r = _find_rank_list(v, depth + 1)
            if r:
                return r
    if isinstance(data, list):
        for v in data:
            r = _find_rank_list(v, depth + 1)
            if r:
                return r
    return []


def run_full_crawl():
    """运行完整采集流程（写入数据库）"""
    print("\n" + "=" * 60)
    print("运行完整采集流程（写入数据库）")
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
                    import traceback
                    traceback.print_exc()

            print(f"\n{'=' * 60}")
            print(f"采集完成！共处理 {total} 条数据")
            print(f"（仅保存有真实热度值的在播剧数据）")
            print(f"{'=' * 60}")

    except Exception as e:
        print(f"\n采集失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print("剧云榜 — 爬虫测试工具 v3")
    print("平台: 爱奇艺 / 腾讯视频 / 优酷 / 芒果TV")
    print(f"Python {sys.version}")

    if '--debug' in sys.argv:
        print("\n运行深度调试...")
        exec(open(os.path.join(os.path.dirname(__file__), 'debug_apis.py')).read())
    elif '--save' in sys.argv:
        run_full_crawl()
    else:
        print("\n测试模式：检测API可用性，不写入数据库")
        print("  --save  执行完整采集并写入数据库")
        print("  --debug 运行深度API调试\n")

        test_iqiyi()
        test_tencent()
        test_mgtv()
        test_youku()

        print("\n" + "=" * 60)
        print("测试完成！")
        print("如需采集写入数据库: python3 test_crawl.py --save")
        print("如需深度调试: python3 test_crawl.py --debug")
        print("=" * 60)
