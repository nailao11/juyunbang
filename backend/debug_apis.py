#!/usr/bin/env python3
"""
剧云榜 — 全平台API深度调试工具
在服务器上运行此脚本，完整展示每个API的响应结构和字段。
用于定位热度值的真实字段名。

使用方法:
    cd /opt/juyunbang/backend
    python3 debug_apis.py
"""
import sys
import os
import json
import re
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def create_session():
    s = requests.Session()
    s.trust_env = False
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    })
    return s


def debug_tencent(session):
    print("\n" + "=" * 70)
    print("【腾讯视频】完整API调试")
    print("=" * 70)

    # --- 1. HotRankHttp 热搜榜 ---
    print("\n--- [1] HotRankHttp 热搜榜API ---")
    for cid in ['2', '1', '3', '5', '0', '100173', '100113', '150203', '电视剧', 'tv']:
        try:
            resp = session.post(
                'https://pbaccess.video.qq.com/trpc.videosearch.hot_rank.HotRankServantHttp/HotRankHttp',
                json={'pageNum': 0, 'pageSize': 10, 'channelId': cid},
                headers={'Content-Type': 'application/json',
                         'Referer': 'https://v.qq.com/',
                         'Origin': 'https://v.qq.com'},
                timeout=15
            )
            data = resp.json()
            # 打印完整响应key结构
            print(f"\n  channelId={cid}:")
            print(f"    顶层key: {list(data.keys())}")
            if 'data' in data:
                d = data['data']
                print(f"    data key: {list(d.keys()) if isinstance(d, dict) else type(d)}")
                if isinstance(d, dict):
                    for k, v in d.items():
                        if isinstance(v, list):
                            print(f"    data.{k}: list[{len(v)}]")
                            if v:
                                print(f"      第1项key: {list(v[0].keys()) if isinstance(v[0], dict) else v[0]}")
                                if isinstance(v[0], dict):
                                    for fk, fv in list(v[0].items())[:10]:
                                        print(f"        {fk} = {str(fv)[:60]}")
                        elif isinstance(v, dict):
                            print(f"    data.{k}: dict[{list(v.keys())[:5]}]")
                        else:
                            print(f"    data.{k}: {str(v)[:80]}")
            else:
                print(f"    完整响应: {json.dumps(data, ensure_ascii=False)[:500]}")
        except Exception as e:
            print(f"  channelId={cid}: 请求失败 {e}")

    # --- 2. bu/pagesheet/list HTML ---
    print("\n--- [2] bu/pagesheet/list HTML ---")
    try:
        resp = session.get('https://v.qq.com/x/bu/pagesheet/list', params={
            '_all': '1', 'append': '1', 'channel': 'tv',
            'listpage': '2', 'offset': '0', 'pagesize': '5', 'sort': '75',
        }, headers={'Referer': 'https://v.qq.com/channel/tv'}, timeout=15)

        text = resp.text
        print(f"  响应长度: {len(text)}")
        print(f"  Content-Type: {resp.headers.get('content-type', '?')}")

        # 分割list_item块
        blocks = re.split(r'<div[^>]*class="[^"]*list_item[^"]*"', text)
        print(f"  list_item块数: {len(blocks) - 1}")

        for i, block in enumerate(blocks[1:3]):  # 只看前2个
            print(f"\n  === 第{i+1}个list_item ===")
            # 提取所有属性和文本
            titles = re.findall(r'title="([^"]+)"', block)
            hrefs = re.findall(r'href="([^"]+)"', block)
            srcs = re.findall(r'src="([^"]+)"', block)
            texts = re.findall(r'>([^<]{2,})<', block)
            numbers = re.findall(r'(\d{3,})', block)

            print(f"    title属性: {titles}")
            print(f"    href: {hrefs[:2]}")
            print(f"    src(图片): {[s[:60] for s in srcs[:2]]}")
            print(f"    文本内容: {[t.strip() for t in texts if t.strip()][:5]}")
            print(f"    数字: {numbers[:5]}")

            # 打印完整HTML（方便分析）
            clean = block[:500]
            print(f"    完整HTML(前500字符):\n      {clean}")

    except Exception as e:
        print(f"  HTML请求失败: {e}")

    # --- 3. pbaccess getPage ---
    print("\n--- [3] pbaccess getPage API ---")
    try:
        body = {
            'page_context': {'page_index': '0'},
            'page_params': {
                'page_id': 'channel_list_second_page',
                'page_type': 'operation',
                'channel_id': '100113',
                'filter_params': 'sort=75', 'page': '0',
            },
            'page_bypass_params': {
                'params': {'page_size': '5', 'page_num': '0',
                           'caller_id': '3000010', 'platform_id': '2'},
                'global_params': {'ckey': '', 'vuession': ''},
            },
        }
        resp = session.post(
            'https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/getPage',
            json=body,
            headers={'Content-Type': 'application/json',
                     'Referer': 'https://v.qq.com/',
                     'Origin': 'https://v.qq.com'},
            timeout=15
        )
        data = resp.json()
        card_list = data.get('data', {}).get('CardList', []) or []
        print(f"  CardList数量: {len(card_list)}")

        for ci, card in enumerate(card_list[:2]):
            print(f"\n  Card {ci} key: {list(card.keys())[:8]}")

            # 深度查找children
            children = _deep_find_list(card)
            if children:
                print(f"  找到children列表: {len(children)}条")
                # 打印前2个children的完整结构
                for i, child in enumerate(children[:2]):
                    print(f"\n    === child[{i}] ===")
                    if isinstance(child, dict):
                        for k, v in child.items():
                            if k == 'params' and isinstance(v, dict):
                                print(f"      params字段({len(v)}个):")
                                for pk, pv in sorted(v.items()):
                                    print(f"        {pk} = {str(pv)[:80]}")
                            else:
                                print(f"      {k} = {str(v)[:100]}")
            else:
                print(f"  未找到children列表")

    except Exception as e:
        print(f"  pbaccess失败: {e}")

    # --- 4. 排行榜HTML页面 ---
    print("\n--- [4] 排行榜HTML页面 ---")
    for url in ['https://v.qq.com/rank', 'https://v.qq.com/rank/detail/tv_hot']:
        try:
            resp = session.get(url, headers={'Referer': 'https://v.qq.com/'}, timeout=15)
            text = resp.text
            print(f"\n  URL: {url}")
            print(f"  状态码: {resp.status_code}")
            print(f"  响应长度: {len(text)}")

            # 查找嵌入JSON
            for pat_name, pattern in [
                ('__INITIAL_DATA__', r'window\.__INITIAL_DATA__\s*=\s*(\{.+?\});\s*</script>'),
                ('__NEXT_DATA__', r'__NEXT_DATA__[^>]*>\s*(\{.+?\})\s*</script>'),
                ('__NUXT__', r'window\.__NUXT__\s*=\s*(\{.+?\});\s*</script>'),
            ]:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    try:
                        jd = json.loads(match.group(1))
                        print(f"  找到{pat_name}! 顶层key: {list(jd.keys())[:8]}")
                        # 深度搜索含title的列表
                        _find_title_lists(jd, prefix=pat_name)
                    except json.JSONDecodeError:
                        print(f"  找到{pat_name}但JSON解析失败")

            # 查找标题和热度
            title_heat = re.findall(r'(\d{3,6})\s*(?:热度|热|分)', text)
            print(f"  HTML中的热度数字: {title_heat[:10]}")

        except Exception as e:
            print(f"  {url}: {e}")


def debug_iqiyi(session):
    print("\n" + "=" * 70)
    print("【爱奇艺】完整API调试")
    print("=" * 70)

    # --- 1. mesh风云榜 ---
    print("\n--- [1] mesh风云榜API ---")
    for params in [
        {'type': 'heat', 'cid': '2', 'limit': '5'},
        {'type': 'hot', 'cid': '2', 'limit': '5'},
    ]:
        try:
            resp = session.get(
                'https://mesh.if.iqiyi.com/portal/lw/videolib/data/rank',
                params=params, timeout=15
            )
            data = resp.json()
            print(f"\n  params={params}:")
            print(f"    顶层key: {list(data.keys())}")
            if 'data' in data:
                d = data['data']
                if isinstance(d, dict):
                    print(f"    data key: {list(d.keys())}")
                    for k, v in d.items():
                        if isinstance(v, list):
                            print(f"    data.{k}: list[{len(v)}]")
                            if v and isinstance(v[0], dict):
                                print(f"      第1项key: {list(v[0].keys())}")
                                for fk, fv in list(v[0].items())[:8]:
                                    print(f"        {fk} = {str(fv)[:60]}")
                        else:
                            print(f"    data.{k}: {str(v)[:80]}")
        except Exception as e:
            print(f"  失败: {e}")

    # --- 2. PCW推荐API ---
    print("\n--- [2] PCW推荐API ---")
    for mode in ['24', '11', '4']:
        try:
            resp = session.get(
                'https://pcw-api.iqiyi.com/search/recommend/list',
                params={'channel_id': '2', 'data_type': '1', 'mode': mode,
                        'page_id': '1', 'ret_num': '5'},
                timeout=15
            )
            data = resp.json()
            items = data.get('data', {}).get('list', [])
            if items:
                print(f"\n  mode={mode}: 共{len(items)}条")
                first = items[0]
                print(f"    第1项key: {list(first.keys())}")
                for k, v in list(first.items())[:12]:
                    print(f"      {k} = {str(v)[:80]}")
            else:
                print(f"\n  mode={mode}: 无数据")
        except Exception as e:
            print(f"  mode={mode}: {e}")

    # --- 3. 排行榜HTML ---
    print("\n--- [3] 排行榜HTML ---")
    for url in ['https://www.iqiyi.com/ranks/热度/2', 'https://www.iqiyi.com/ranks']:
        try:
            resp = session.get(url, timeout=15)
            text = resp.text
            print(f"\n  URL: {url}")
            print(f"  状态码: {resp.status_code}, 长度: {len(text)}")

            # 查找嵌入JSON
            match = re.search(r'window\.__INITIAL_DATA__\s*=\s*(\{.+?\});\s*</script>',
                              text, re.DOTALL)
            if match:
                try:
                    jd = json.loads(match.group(1))
                    print(f"  __INITIAL_DATA__ key: {list(jd.keys())[:8]}")
                    _find_title_lists(jd, prefix='INITIAL')
                except json.JSONDecodeError:
                    print(f"  JSON解析失败")
            else:
                print(f"  无__INITIAL_DATA__")
                # 查找其他数据
                titles = re.findall(r'title="([^"]{2,30})"', text)
                print(f"  HTML中title属性: {titles[:5]}")
        except Exception as e:
            print(f"  {url}: {e}")


def debug_mgtv(session):
    print("\n" + "=" * 70)
    print("【芒果TV】完整API调试")
    print("=" * 70)

    # --- 1. pianku API（完整字段） ---
    print("\n--- [1] pianku API 完整字段 ---")
    try:
        resp = session.get(
            'https://pianku.api.mgtv.com/rider/list/pcweb/v3',
            params={'allowedRC': '1', 'platform': 'pcweb', 'channelId': '2',
                    'pn': '1', 'pc': '3', 'hudong': '1', 'orderType': 'c2'},
            timeout=15
        )
        data = resp.json()
        hit_list = data.get('data', {}).get('hitDocs', [])
        if hit_list:
            print(f"  hitDocs数量: {len(hit_list)}")
            first = hit_list[0]
            print(f"  第1项所有字段({len(first)}个):")
            for k, v in sorted(first.items()):
                v_str = str(v)[:100]
                marker = " ★" if isinstance(v, (int, float)) and v > 0 else ""
                print(f"    {k} = {v_str}{marker}")
        else:
            print(f"  无hitDocs数据")
            print(f"  data key: {list(data.get('data', {}).keys())}")
    except Exception as e:
        print(f"  pianku失败: {e}")

    # --- 2. 其他排行API ---
    print("\n--- [2] 其他排行API ---")
    for name, url, params in [
        ('top.bz getHitList', 'https://top.bz.mgtv.com/client/getHitList',
         {'channelId': '2', 'pageNo': '1', 'pageSize': '5'}),
        ('top.bz getTopList', 'https://top.bz.mgtv.com/client/getTopList',
         {'channelId': '2'}),
        ('top.bz getRuleInfo', 'https://top.bz.mgtv.com/client/getRuleInfo',
         {}),
        ('channelrank', 'https://vc.mgtv.com/v2/list/channelrank',
         {'channelId': '2', 'pageNo': '1', 'pageSize': '5'}),
        ('pcweb rank', 'https://pcweb.api.mgtv.com/video/rank',
         {'channelId': '2', 'pageSize': '5'}),
        ('mobile rank', 'https://mobile.api.mgtv.com/v8/video/rank',
         {'channelId': '2', 'pageNo': '1', 'pageSize': '5'}),
    ]:
        try:
            resp = session.get(url, params=params, timeout=15)
            print(f"\n  {name}: HTTP {resp.status_code}")
            try:
                data = resp.json()
                print(f"    响应key: {list(data.keys())[:5]}")
                if 'data' in data:
                    d = data['data']
                    if isinstance(d, dict):
                        print(f"    data key: {list(d.keys())[:5]}")
                        for k, v in d.items():
                            if isinstance(v, list) and v:
                                print(f"    data.{k}: list[{len(v)}]")
                                if isinstance(v[0], dict):
                                    print(f"      第1项key: {list(v[0].keys())[:8]}")
                    elif isinstance(d, list) and d:
                        print(f"    data: list[{len(d)}]")
                        if isinstance(d[0], dict):
                            print(f"      第1项key: {list(d[0].keys())[:8]}")
            except Exception:
                print(f"    非JSON响应: {resp.text[:100]}")
        except Exception as e:
            print(f"  {name}: {e}")

    # --- 3. 排行页HTML ---
    print("\n--- [3] 排行页HTML ---")
    for url in ['https://www.mgtv.com/rank/', 'https://www.mgtv.com/rank/tv']:
        try:
            resp = session.get(url, headers={'Referer': 'https://www.mgtv.com/'}, timeout=15)
            text = resp.text
            print(f"\n  {url}: HTTP {resp.status_code}, 长度={len(text)}")

            for pat_name, pattern in [
                ('__NUXT__', r'window\.__NUXT__\s*=\s*(\{.+?\});\s*</script>'),
                ('__INITIAL_DATA__', r'window\.__INITIAL_DATA__\s*=\s*(\{.+?\});\s*</script>'),
            ]:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    try:
                        jd = json.loads(match.group(1))
                        print(f"  找到{pat_name}! key: {list(jd.keys())[:8]}")
                        _find_title_lists(jd, prefix=pat_name)
                    except json.JSONDecodeError:
                        print(f"  {pat_name}: JSON解析失败")
        except Exception as e:
            print(f"  {url}: {e}")


def debug_youku(session):
    print("\n" + "=" * 70)
    print("【优酷】完整API调试")
    print("=" * 70)

    # --- 1. 移动端API ---
    print("\n--- [1] 移动端网关API ---")
    try:
        resp = session.get(
            'https://acs.youku.com/h5/mtop.youku.columbus.gateway.new.execute/1.0/',
            params={
                'jsv': '2.7.2', 'appKey': '24679788',
                'api': 'mtop.youku.columbus.gateway.new.execute', 'v': '1.0',
                'data': json.dumps({
                    'ms_codes': '2019030100',
                    'params': json.dumps({'st': '1', 'pn': '1', 'ps': '5', 'cid': '97'})
                })
            },
            headers={'Referer': 'https://www.youku.com/'}, timeout=15
        )
        print(f"  HTTP {resp.status_code}")
        try:
            data = resp.json()
            print(f"  响应key: {list(data.keys())[:5]}")
            result = data.get('data', {})
            if isinstance(result, str):
                result = json.loads(result)
            if isinstance(result, dict):
                print(f"  data key: {list(result.keys())[:5]}")
        except Exception:
            print(f"  非JSON: {resp.text[:200]}")
    except Exception as e:
        print(f"  API失败: {e}")

    # --- 2. 排行页HTML ---
    print("\n--- [2] 排行页HTML ---")
    for url in ['https://acz.youku.com/wow/ykpage/act/top_hot',
                 'http://top.youku.com/rank/',
                 'https://www.youku.com/rank',
                 'https://www.youku.com/category/show/c_97_s_1_d_1.html']:
        try:
            resp = session.get(url, headers={'Referer': 'https://www.youku.com/'}, timeout=15)
            text = resp.text
            print(f"\n  {url}: HTTP {resp.status_code}, 长度={len(text)}")

            for pat_name, pattern in [
                ('__INITIAL_DATA__', r'window\.__INITIAL_DATA__\s*=\s*(\{.+?\});\s*</script>'),
                ('__NEXT_DATA__', r'__NEXT_DATA__[^>]*>\s*(\{.+?\})\s*</script>'),
            ]:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    try:
                        jd = json.loads(match.group(1))
                        print(f"  找到{pat_name}! key: {list(jd.keys())[:8]}")
                        _find_title_lists(jd, prefix=pat_name)
                    except json.JSONDecodeError:
                        print(f"  {pat_name}: JSON解析失败")

            titles = re.findall(r'title="([^"]{2,30})"', text)
            print(f"  HTML中title属性: {titles[:5]}")
        except Exception as e:
            print(f"  {url}: {e}")


def debug_maoyan(session):
    """
    猫眼专业版 — 聚合了全部平台的真实热度数据
    这可能是获取各平台热度值的最佳单一数据源
    """
    print("\n" + "=" * 70)
    print("【猫眼专业版】全平台热度聚合数据")
    print("=" * 70)

    # --- 1. 网播热度页面 ---
    print("\n--- [1] 网播热度页面 ---")
    for url in [
        'https://piaofang.maoyan.com/web-heat',
        'https://piaofang.maoyan.com/dashboard/web-heat',
    ]:
        try:
            resp = session.get(url, headers={
                'Referer': 'https://piaofang.maoyan.com/',
            }, timeout=15)
            text = resp.text
            print(f"\n  {url}: HTTP {resp.status_code}, 长度={len(text)}")

            # 查找嵌入JSON
            for pat_name, pattern in [
                ('__INITIAL_DATA__', r'window\.__INITIAL_DATA__\s*=\s*(\{.+?\});\s*</script>'),
                ('__NEXT_DATA__', r'__NEXT_DATA__[^>]*>\s*(\{.+?\})\s*</script>'),
                ('__NUXT__', r'window\.__NUXT__\s*=\s*(\{.+?\});\s*</script>'),
            ]:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    try:
                        jd = json.loads(match.group(1))
                        print(f"  找到{pat_name}! key: {list(jd.keys())[:8]}")
                        _find_title_lists(jd, prefix=pat_name)
                    except json.JSONDecodeError:
                        print(f"  {pat_name}: JSON解析失败")

            # 查找标题
            titles = re.findall(r'title="([^"]{2,30})"', text)
            if titles:
                print(f"  HTML中title: {titles[:5]}")

        except Exception as e:
            print(f"  {url}: {e}")

    # --- 2. 猫眼API ---
    print("\n--- [2] 猫眼热度API ---")
    for name, url, params in [
        ('web-heat-api', 'https://piaofang.maoyan.com/dashboard-ajax/webHeat',
         {'orderType': '0', 'platform': '0', 'pageSize': '10', 'pageNum': '1'}),
        ('heat-overall', 'https://piaofang.maoyan.com/dashboard-ajax/heatData',
         {'type': 'tv', 'date': ''}),
        ('second-box', 'https://piaofang.maoyan.com/second-box',
         {}),
    ]:
        try:
            resp = session.get(url, params=params, headers={
                'Referer': 'https://piaofang.maoyan.com/',
            }, timeout=15)
            print(f"\n  {name}: HTTP {resp.status_code}")
            try:
                data = resp.json()
                print(f"    响应key: {list(data.keys())[:5]}")
                if 'data' in data:
                    d = data['data']
                    if isinstance(d, dict):
                        print(f"    data key: {list(d.keys())[:5]}")
                        for k, v in d.items():
                            if isinstance(v, list) and v:
                                print(f"    data.{k}: list[{len(v)}]")
                                if isinstance(v[0], dict):
                                    print(f"      第1项key: {list(v[0].keys())[:10]}")
                                    for fk, fv in list(v[0].items())[:8]:
                                        print(f"        {fk} = {str(fv)[:80]}")
                    elif isinstance(d, list) and d:
                        print(f"    data: list[{len(d)}]")
                        if isinstance(d[0], dict):
                            print(f"      第1项key: {list(d[0].keys())[:10]}")
                            for fk, fv in list(d[0].items())[:8]:
                                print(f"        {fk} = {str(fv)[:80]}")
            except Exception:
                print(f"    非JSON: {resp.text[:200]}")
        except Exception as e:
            print(f"  {name}: {e}")

    # --- 3. 第三方免费API ---
    print("\n--- [3] 第三方热度API ---")
    for name, url in [
        ('aa1-txvideo', 'https://api.aa1.cn/api/txvideo/'),
        ('DailyHot', 'https://api-hot.imsyy.top/tencent'),
    ]:
        try:
            resp = session.get(url, timeout=10)
            print(f"\n  {name}: HTTP {resp.status_code}")
            try:
                data = resp.json()
                print(f"    响应key: {list(data.keys())[:5]}")
                # 查找列表数据
                for k, v in data.items():
                    if isinstance(v, list) and v:
                        print(f"    {k}: list[{len(v)}]")
                        if isinstance(v[0], dict):
                            print(f"      第1项key: {list(v[0].keys())[:8]}")
                            for fk, fv in list(v[0].items())[:5]:
                                print(f"        {fk} = {str(fv)[:80]}")
                        break
            except Exception:
                print(f"    非JSON: {resp.text[:100]}")
        except Exception as e:
            print(f"  {name}: {e}")


# ============================================================
# 辅助函数
# ============================================================

def _deep_find_list(obj, depth=0):
    """递归查找包含5+项的dict列表"""
    if depth > 5:
        return []
    if isinstance(obj, list) and len(obj) >= 5:
        if obj and isinstance(obj[0], dict) and ('params' in obj[0] or 'title' in obj[0]):
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


def _find_title_lists(data, prefix='', depth=0, found=None):
    """递归查找包含title字段的列表，打印路径和内容"""
    if found is None:
        found = set()
    if depth > 6 or id(data) in found:
        return
    found.add(id(data))

    if isinstance(data, list) and len(data) >= 3:
        has_titles = sum(1 for x in data[:5]
                         if isinstance(x, dict) and
                         any(k in x for k in ('title', 'name', 'show_title')))
        if has_titles >= 2:
            print(f"  [{prefix}] 找到列表[{len(data)}条]:")
            for i, item in enumerate(data[:3]):
                if isinstance(item, dict):
                    title = item.get('title', '') or item.get('name', '')
                    heat = item.get('hot', '') or item.get('heat', '') or item.get('heatScore', '') or item.get('score', '')
                    print(f"    [{i+1}] title={title} | heat={heat}")
            return

    if isinstance(data, dict):
        for k, v in data.items():
            _find_title_lists(v, f"{prefix}.{k}", depth + 1, found)
    elif isinstance(data, list):
        for i, v in enumerate(data[:5]):
            _find_title_lists(v, f"{prefix}[{i}]", depth + 1, found)


if __name__ == '__main__':
    print("剧云榜 — 全平台API深度调试工具")
    print(f"Python {sys.version}")
    print("\n此脚本会测试所有API并输出完整字段结构，")
    print("用于确认哪些字段包含真实热度值。")

    session = create_session()

    debug_tencent(session)
    debug_iqiyi(session)
    debug_mgtv(session)
    debug_youku(session)
    debug_maoyan(session)

    print("\n" + "=" * 70)
    print("调试完成！请将以上输出发给开发者分析。")
    print("=" * 70)
