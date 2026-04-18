#!/usr/bin/env python3
"""
热剧榜 — 爬虫测试脚本 v4（Playwright）

使用方法:
    cd /opt/rejubang/backend
    ./venv/bin/python test_crawl.py              # 测试Playwright浏览器和各平台连通性
    ./venv/bin/python test_crawl.py --save       # 完整采集并写入数据库
    ./venv/bin/python test_crawl.py --platform tencent  # 只测试单个平台

说明:
    采集策略: 只采集近30天内上线的新剧，每次采集自动去重。
    各平台热度获取方式:
      - 腾讯视频: 移动端 m.v.qq.com/x/cover/{cid}.html 的 "XXX热度"
      - 爱奇艺:   PC端详情页 iqiyi.com/v_XXX.html 的热度值
      - 优酷:     PC端详情页 v.youku.com/v_show/id_XXX.html 的热度值
      - 芒果TV:   移动端 m.mgtv.com/b/XXX/YYY.html 的 "X.X亿次播放"（用作热度替代）
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('FLASK_ENV', 'production')


def _diagnose_api(crawler, url, params, json_mode=False):
    """诊断API接口返回内容，帮助定位发现失败原因"""
    try:
        resp = crawler.fetch(url, params=params)
        if not resp:
            print(f"  [诊断] 请求失败：无响应（网络不通或被封禁）")
            return
        print(f"  [诊断] HTTP {resp.status_code}, 长度={len(resp.text)} 字节")
        if json_mode:
            try:
                data = resp.json()
                # 显示顶层结构
                if isinstance(data, dict):
                    print(f"  [诊断] JSON顶层key: {list(data.keys())[:10]}")
                    for k in ['code', 'status', 'msg', 'message', 'ret']:
                        if k in data:
                            print(f"  [诊断] {k}={data[k]}")
                else:
                    print(f"  [诊断] JSON类型: {type(data).__name__}, 长度={len(data) if hasattr(data, '__len__') else '?'}")
            except Exception as e:
                print(f"  [诊断] 非JSON响应，前200字符: {resp.text[:200]}")
        else:
            print(f"  [诊断] 响应前300字符: {resp.text[:300]}")
    except Exception as e:
        print(f"  [诊断] 请求异常: {e}")


def check_playwright():
    """检查Playwright是否可用"""
    print("\n[1/3] 检查Playwright...")
    try:
        from playwright.sync_api import sync_playwright
        print("  ✓ playwright模块已安装")
    except ImportError:
        print("  ✗ playwright未安装！请执行:")
        print("    ./venv/bin/pip install playwright==1.40.0")
        print("    ./venv/bin/playwright install chromium")
        print("    ./venv/bin/playwright install-deps chromium")
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            browser.close()
        print("  ✓ chromium浏览器可启动")
        return True
    except Exception as e:
        print(f"  ✗ chromium启动失败: {e}")
        print("    请执行: ./venv/bin/playwright install chromium")
        print("    Debian依赖: ./venv/bin/playwright install-deps chromium")
        return False


def test_discovery():
    """测试各平台的新剧列表API"""
    print("\n[2/3] 测试各平台新剧发现API...")
    from crawlers.airing_crawler import AiringCrawler

    crawler = AiringCrawler()

    results = {}

    print("\n  --- 腾讯视频 ---")
    dramas = crawler._discover_tencent_dramas()
    print(f"  发现 {len(dramas)} 部候选剧")
    if not dramas:
        print("  [诊断] 尝试直接请求腾讯API...")
        _diagnose_api(crawler, 'https://v.qq.com/x/bu/pagesheet/list',
                      {'_all': '1', 'append': '1', 'channel': 'tv',
                       'listpage': '2', 'offset': '0', 'pagesize': '60', 'sort': '75'})
    for d in dramas[:3]:
        print(f"    {d['title']} (cid={d['cid']})")
    results['tencent'] = len(dramas)

    print("\n  --- 爱奇艺 ---")
    dramas = crawler._discover_iqiyi_dramas()
    print(f"  发现 {len(dramas)} 部候选剧")
    if not dramas:
        print("  [诊断] 尝试直接请求爱奇艺API...")
        _diagnose_api(crawler, 'https://pcw-api.iqiyi.com/search/recommend/list',
                      {'channel_id': '2', 'data_type': '1', 'mode': '24',
                       'page_id': '1', 'ret_num': '60'}, json_mode=True)
    for d in dramas[:3]:
        print(f"    {d['title']} -> {d['url']}")
    results['iqiyi'] = len(dramas)

    print("\n  --- 芒果TV ---")
    dramas = crawler._discover_mgtv_dramas()
    print(f"  发现 {len(dramas)} 部候选剧")
    if not dramas:
        print("  [诊断] 尝试直接请求芒果TV API...")
        _diagnose_api(crawler, 'https://pianku.api.mgtv.com/rider/list/pcweb/v3',
                      {'allowedRC': '1', 'platform': 'pcweb', 'channelId': '2',
                       'pn': '1', 'pc': '60', 'hudong': '1', 'orderType': 'c2'}, json_mode=True)
    for d in dramas[:3]:
        print(f"    {d['title']} (part_id={d['part_id']}, vid={d['vid']})")
    results['mgtv'] = len(dramas)

    return results


def test_heat_extraction(platform=None):
    """用Playwright访问一部剧的详情页，测试热度提取"""
    print("\n[3/3] 测试热度值提取（使用Playwright）...")
    from crawlers.airing_crawler import AiringCrawler
    from crawlers.browser_helper import BrowserHelper

    crawler = AiringCrawler()

    tests = [
        ('tencent', crawler._discover_tencent_dramas, crawler._extract_tencent_heat,
         lambda d: f"https://m.v.qq.com/x/cover/{d['cid']}.html", '热度值'),
        ('iqiyi', crawler._discover_iqiyi_dramas, crawler._extract_iqiyi_heat,
         lambda d: d['url'], '热度值'),
    ]

    with BrowserHelper(headless=True) as browser:
        for name, discover, extract, url_fn, label in tests:
            if platform and platform != name:
                continue
            print(f"\n  --- {name} ---")
            try:
                dramas = discover()
                if not dramas:
                    print(f"  !! {name}未发现任何剧")
                    continue
                d = dramas[0]
                url = url_fn(d)
                print(f"  访问: {url}")
                value = extract(browser, url)
                print(f"  {label}: {value}")
                if value > 0:
                    print(f"  ✓ {name}热度提取成功")
                else:
                    print(f"  ✗ {name}未提取到热度（页面可能改版或有反爬）")
                    _diagnose_page(browser, url, name)
            except Exception as e:
                print(f"  ✗ {name}失败: {e}")

        if not platform or platform == 'youku':
            print(f"\n  --- youku ---")
            try:
                dramas = crawler._discover_youku_dramas(browser)
                if dramas:
                    d = dramas[0]
                    print(f"  访问: {d['url']}")
                    value = crawler._extract_youku_heat(browser, d['url'])
                    print(f"  热度值: {value}")
                    if value > 0:
                        print(f"  ✓ youku热度提取成功")
                    else:
                        print(f"  ✗ youku未提取到热度")
                        _diagnose_page(browser, d['url'], 'youku')
                else:
                    print(f"  !! youku未发现任何剧")
                    print(f"  [诊断] 尝试用浏览器访问优酷分类页...")
                    _diagnose_page(browser, 'https://www.youku.com/category/show/c_97_s_1_d_1.html', 'youku_category')
            except Exception as e:
                print(f"  ✗ youku失败: {e}")

        # 芒果TV
        if not platform or platform == 'mgtv':
            print(f"\n  --- mgtv ---")
            try:
                dramas = crawler._discover_mgtv_dramas()
                if dramas:
                    d = dramas[0]
                    url = f"https://m.mgtv.com/b/{d['part_id']}/{d['vid']}.html"
                    print(f"  访问: {url}")
                    value = crawler._extract_mgtv_playcount(browser, url)
                    print(f"  播放量: {value}")
                    if value > 0:
                        print(f"  ✓ mgtv播放量提取成功")
                    else:
                        print(f"  ✗ mgtv未提取到播放量")
                        _diagnose_page(browser, url, 'mgtv')
                else:
                    print(f"  !! mgtv未发现任何剧")
            except Exception as e:
                print(f"  ✗ mgtv失败: {e}")


def _diagnose_page(browser, url, name):
    """当热度提取失败时，打印页面诊断信息帮助定位问题"""
    import re
    try:
        mobile = name in ('tencent', 'mgtv')
        html = browser.get_html(url, mobile=mobile, timeout=20000)
        if not html:
            print(f"  [诊断] 页面返回空内容")
            return
        print(f"  [诊断] 页面HTML长度: {len(html)} 字符")
        # 搜索页面中包含"热度"或"播放"的片段
        for keyword in ['热度', '播放', 'heat', 'hot']:
            matches = [(m.start(), m.group()) for m in re.finditer(
                rf'.{{0,30}}{keyword}.{{0,30}}', html, re.IGNORECASE)]
            if matches:
                print(f"  [诊断] 找到 \"{keyword}\" {len(matches)} 处，示例:")
                for pos, snippet in matches[:3]:
                    clean = re.sub(r'<[^>]+>', '', snippet).strip()
                    if clean:
                        print(f"    位置{pos}: ...{clean}...")
            else:
                print(f"  [诊断] 页面中未找到 \"{keyword}\"")
        # 如果页面很短，可能是被重定向或反爬
        if len(html) < 2000:
            print(f"  [诊断] 页面内容过短，可能是反爬页面，前500字符:")
            print(f"    {html[:500]}")
    except Exception as e:
        print(f"  [诊断] 诊断页面失败: {e}")


def run_full_crawl():
    """运行完整采集流程并写入数据库"""
    print("\n" + "=" * 60)
    print("运行完整采集流程（写入数据库）")
    print("=" * 60)

    try:
        from app import create_app
        app = create_app()

        with app.app_context():
            from crawlers.base_crawler import BaseCrawler
            from crawlers.airing_crawler import AiringCrawler

            BaseCrawler.clear_drama_cache()
            crawler = AiringCrawler()
            total = crawler.crawl()

            print(f"\n{'=' * 60}")
            print(f"采集完成！共保存 {total} 条热度/播放数据")
            print(f"{'=' * 60}")
    except Exception as e:
        print(f"\n采集失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--save', action='store_true', help='完整采集并写入数据库')
    parser.add_argument('--platform', help='只测试单个平台(tencent/iqiyi/youku/mgtv)')
    parser.add_argument('--skip-discovery', action='store_true', help='跳过列表API测试')
    args = parser.parse_args()

    print("热剧榜 — 爬虫测试工具 v4 (Playwright)")
    print(f"Python {sys.version.split()[0]}")

    if args.save:
        run_full_crawl()
    else:
        print("\n测试模式：只检测连通性，不写数据库")
        print("  --save      完整采集写入数据库")
        print("  --platform  只测试单个平台\n")

        if not check_playwright():
            sys.exit(1)

        if not args.skip_discovery:
            test_discovery()

        test_heat_extraction(platform=args.platform)

        print("\n" + "=" * 60)
        print("测试完成")
        print("如测试通过，运行: ./venv/bin/python test_crawl.py --save")
        print("=" * 60)
