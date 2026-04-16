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
    for d in dramas[:3]:
        print(f"    {d['title']} (cid={d['cid']})")
    results['tencent'] = len(dramas)

    print("\n  --- 爱奇艺 ---")
    dramas = crawler._discover_iqiyi_dramas()
    print(f"  发现 {len(dramas)} 部候选剧")
    for d in dramas[:3]:
        print(f"    {d['title']} -> {d['url']}")
    results['iqiyi'] = len(dramas)

    print("\n  --- 芒果TV ---")
    dramas = crawler._discover_mgtv_dramas()
    print(f"  发现 {len(dramas)} 部候选剧")
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
        # 优酷需要browser作为discovery参数，单独测试
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
            except Exception as e:
                print(f"  ✗ {name}失败: {e}")

        # 优酷需要browser
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
                else:
                    print(f"  !! youku未发现任何剧")
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
                else:
                    print(f"  !! mgtv未发现任何剧")
            except Exception as e:
                print(f"  ✗ mgtv失败: {e}")


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
