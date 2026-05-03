#!/usr/bin/env python3
"""
热剧榜 — 爬虫测试脚本 v5（半自动架构）

使用方法:
    cd /opt/rejubang/backend

    # 1. 检查 Playwright 环境
    ./venv/bin/python test_crawl.py --env

    # 2. 对 drama_platforms 表里的所有在播剧跑一轮完整采集（写入数据库）
    ./venv/bin/python test_crawl.py --run

    # 3. 测试单条完整页面 URL 的热度提取（不写库，不依赖数据库）
    ./venv/bin/python test_crawl.py --test-url tencent 'https://m.v.qq.com/x/m/play?cid=mzc002007tp60ap&vid=w41025my54z'
    ./venv/bin/python test_crawl.py --test-url iqiyi   'https://www.iqiyi.com/a_1euk1nkfz9l.html'
    ./venv/bin/python test_crawl.py --test-url youku   'https://v.youku.com/v_show/id_XMTgyMDM5NTEyMA==.html'
    ./venv/bin/python test_crawl.py --test-url mgtv    'https://www.mgtv.com/b/742534/25318094.html'

    # 4. 查看当前数据库里已录入的剧
    ./venv/bin/python test_crawl.py --list

说明:
    剧集清单通过 Web 后台 https://<你的API域名>/admin 录入（需 ADMIN_TOKEN）。
    本测试脚本不提供录入功能，只做验证。
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('FLASK_ENV', 'production')


def check_env():
    """检查 Playwright 是否可用"""
    print("\n[1/2] 检查 Playwright 模块...")
    try:
        from playwright.sync_api import sync_playwright
        print("  ✓ playwright 模块已安装")
    except ImportError:
        print("  ✗ playwright 未安装，执行: ./venv/bin/pip install playwright==1.40.0")
        return False

    print("\n[2/2] 检查 Chromium 能否启动...")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True, args=['--no-sandbox'])
            b.close()
        print("  ✓ chromium 可启动")
        return True
    except Exception as e:
        print(f"  ✗ chromium 启动失败: {e}")
        print("    执行: ./venv/bin/playwright install chromium")
        print("    执行: ./venv/bin/playwright install-deps chromium")
        return False


def test_single_url(platform, raw_input):
    """测试单条 URL 的提取（不入库）"""
    from app.utils.platform_url import parse_platform_input, normalize_platform
    from crawlers.browser_helper import BrowserHelper
    from crawlers.airing_crawler import AiringCrawler

    platform = normalize_platform(platform)
    if not platform:
        print(f"✗ 未知平台: {platform}"); return

    drama_id, url = parse_platform_input(platform, raw_input)
    if not url:
        print(f"✗ 无法从输入 {raw_input!r} 解析出 {platform} 的 ID")
        return

    print(f"\n平台: {platform}")
    print(f"输入: {raw_input}")
    print(f"解析: id={drama_id}  url={url}")
    print(f"启动 Playwright 提取（约 10-20 秒）...")

    crawler = AiringCrawler()
    fn_name = crawler.PLATFORM_EXTRACTORS.get(platform)
    if not fn_name:
        print(f"✗ {platform} 不支持提取"); return

    try:
        with BrowserHelper(headless=True) as browser:
            fn = getattr(crawler, fn_name)
            value = fn(browser, url)
    except Exception as e:
        print(f"✗ 提取异常: {e}")
        import traceback; traceback.print_exc()
        return

    if value and value > 0:
        label = '播放量' if platform == 'mgtv' else '热度值'
        print(f"✓ {label}: {value}")
    else:
        print(f"✗ 未提取到数值")

    debug = crawler.get_last_debug()
    if debug:
        print("  -- debug --")
        for k in ('source_type', 'match_pattern', 'matched_snippet', 'final_url'):
            v = debug.get(k)
            if v is not None:
                print(f"  {k}: {v}")
        errs = debug.get('errors') or []
        if errs:
            print(f"  errors: {' | '.join(str(e) for e in errs)}")


def run_full_crawl():
    """对 drama_platforms 表跑一轮完整采集"""
    print("\n" + "=" * 60)
    print("运行完整采集（从 drama_platforms 读取在播剧清单）")
    print("=" * 60)

    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            from crawlers.airing_crawler import AiringCrawler
            crawler = AiringCrawler()
            total = crawler.crawl()
            print(f"\n=== 完成，保存 {total} 条 ===")
    except Exception as e:
        print(f"\n采集失败: {e}")
        import traceback; traceback.print_exc()


def list_dramas():
    """列出数据库里已录入的剧"""
    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            from app.utils.db import query
            rows = query("""
                SELECT d.id, d.title, d.status, d.air_date,
                       GROUP_CONCAT(p.short_name ORDER BY p.sort_order) AS platforms,
                       (SELECT MAX(record_time) FROM heat_realtime h
                        WHERE h.drama_id = d.id) AS last_crawl
                FROM dramas d
                LEFT JOIN drama_platforms dp ON dp.drama_id = d.id
                LEFT JOIN platforms p ON p.id = dp.platform_id
                GROUP BY d.id
                ORDER BY d.status='airing' DESC, d.id DESC
                LIMIT 50
            """)
            if not rows:
                print("\n数据库无剧。请通过 /admin 录入。")
                return
            print(f"\n共 {len(rows)} 部剧（最多显示 50 部）:\n")
            print(f"{'ID':<4} {'剧名':<16} {'状态':<10} {'开播':<12} "
                  f"{'平台':<25} {'最近采集'}")
            print("-" * 90)
            for r in rows:
                print(f"{r['id']:<4} {(r['title'] or ''):<16} "
                      f"{(r['status'] or ''):<10} "
                      f"{str(r['air_date'] or '-'):<12} "
                      f"{(r['platforms'] or '-'):<25} "
                      f"{r['last_crawl'] or '未采集'}")
    except Exception as e:
        print(f"列表查询失败: {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--env', action='store_true', help='检查 Playwright 环境')
    parser.add_argument('--run', action='store_true', help='对 drama_platforms 跑一轮完整采集（写入数据库）')
    parser.add_argument('--test-url', nargs=2, metavar=('PLATFORM', 'URL_OR_ID'),
                        help='测试单条 URL 的热度提取')
    parser.add_argument('--list', action='store_true', help='列出数据库里已录入的剧')
    args = parser.parse_args()

    print("热剧榜 — 爬虫测试工具 v5")
    print(f"Python {sys.version.split()[0]}\n")

    if not any([args.env, args.run, args.test_url, args.list]):
        parser.print_help()
        print("\n典型工作流:")
        print("  1. ./venv/bin/python test_crawl.py --env")
        print("  2. 浏览器打开 https://<你的API域名>/admin 录入 2~3 部剧")
        print("  3. ./venv/bin/python test_crawl.py --run")
        print("  4. ./venv/bin/python test_crawl.py --list")
        sys.exit(0)

    if args.env:
        ok = check_env()
        sys.exit(0 if ok else 1)

    if args.test_url:
        test_single_url(args.test_url[0], args.test_url[1])

    if args.list:
        list_dramas()

    if args.run:
        run_full_crawl()
