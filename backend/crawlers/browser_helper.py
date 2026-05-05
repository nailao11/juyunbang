"""
Playwright 无头浏览器助手

封装 sync Playwright，统一上下文管理，屏蔽图片/媒体/字体加快加载。
所有需要浏览器渲染的采集都应只通过本类的方法调用，业务函数不要再额外
sync_playwright().start()，否则容易触发 "Sync API inside the asyncio loop" 错误。

提供能力：
    get_html(...)                    渲染后 HTML 全文（兜底使用）
    get_text_by_selector(...)        指定选择器文本
    get_rendered_text(...)           整页 body inner_text，腾讯/优酷/芒果使用
    capture_first_json_response(...) 监听 XHR/fetch 响应，命中关键字即返回 JSON，爱奇艺使用
"""

from contextlib import contextmanager
from loguru import logger


PC_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
         'AppleWebKit/537.36 (KHTML, like Gecko) '
         'Chrome/120.0.0.0 Safari/537.36')

MOBILE_UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) '
             'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 '
             'Mobile/15E148 Safari/604.1')


class BrowserHelper:
    """
    Playwright 浏览器封装。

    用法:
        with BrowserHelper() as browser:
            text = browser.get_rendered_text(url, mobile=True)
            data, meta = browser.capture_first_json_response(url, 'mesh.if.iqiyi.com/...')
    """

    def __init__(self, headless=True):
        self.headless = headless
        self._playwright = None
        self._browser = None

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright未安装。请执行:\n"
                "  ./venv/bin/pip install -r requirements.txt\n"
                "  ./venv/bin/playwright install chromium\n"
                "  ./venv/bin/playwright install-deps chromium"
            )

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-gpu',
            ]
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

    @contextmanager
    def _page(self, mobile=False, extra_headers=None):
        """创建临时页面上下文，屏蔽图片/媒体/字体减压"""
        viewport = {'width': 390, 'height': 844} if mobile else {'width': 1280, 'height': 800}
        ua = MOBILE_UA if mobile else PC_UA

        context = self._browser.new_context(
            user_agent=ua,
            viewport=viewport,
            is_mobile=mobile,
            device_scale_factor=2 if mobile else 1,
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            extra_http_headers=extra_headers or {},
        )

        def block_resources(route):
            if route.request.resource_type in ('image', 'media', 'font'):
                route.abort()
            else:
                route.continue_()

        context.route('**/*', block_resources)

        page = context.new_page()
        try:
            yield page
        finally:
            try:
                page.close()
                context.close()
            except Exception:
                pass

    def _close_popups(self, page, close_selectors):
        if not close_selectors:
            return
        for sel in close_selectors:
            try:
                el = page.query_selector(sel)
                if el:
                    el.click(timeout=2000)
            except Exception:
                pass

    def get_html(self, url, mobile=False, wait_for=None, timeout=20000,
                 close_selectors=None, extra_headers=None):
        """访问URL并返回渲染后的HTML，作为正则兜底使用。"""
        try:
            with self._page(mobile=mobile, extra_headers=extra_headers) as page:
                page.goto(url, wait_until='domcontentloaded', timeout=timeout)
                self._close_popups(page, close_selectors)
                if wait_for:
                    try:
                        page.wait_for_selector(wait_for, timeout=timeout, state='visible')
                    except Exception:
                        pass
                try:
                    page.wait_for_timeout(800)
                except Exception:
                    pass
                return page.content()
        except Exception as e:
            logger.warning(f"[Browser] get_html {url} 失败: {e}")
            return None

    def get_text_by_selector(self, url, selector, mobile=False,
                             timeout=20000, close_selectors=None):
        """访问URL并返回指定CSS选择器的text内容"""
        try:
            with self._page(mobile=mobile) as page:
                page.goto(url, wait_until='domcontentloaded', timeout=timeout)
                self._close_popups(page, close_selectors)
                try:
                    el = page.wait_for_selector(selector, timeout=timeout, state='visible')
                    return el.text_content() if el else None
                except Exception:
                    return None
        except Exception as e:
            logger.warning(f"[Browser] 取{selector}失败 {url}: {e}")
            return None

    def get_rendered_text(self, url, mobile=False, timeout=20000,
                          close_selectors=None, extra_headers=None,
                          wait_after_ms=1200, scroll=False):
        """渲染页面后取 body innerText（已过滤脚本/样式），腾讯/芒果/优酷正文匹配使用。"""
        try:
            with self._page(mobile=mobile, extra_headers=extra_headers) as page:
                page.goto(url, wait_until='domcontentloaded', timeout=timeout)
                self._close_popups(page, close_selectors)
                if scroll:
                    try:
                        page.evaluate('window.scrollTo(0, document.body.scrollHeight/2)')
                    except Exception:
                        pass
                try:
                    page.wait_for_timeout(wait_after_ms)
                except Exception:
                    pass
                try:
                    return page.locator('body').inner_text()
                except Exception:
                    try:
                        return page.evaluate('document.body && document.body.innerText || ""')
                    except Exception:
                        return ''
        except Exception as e:
            logger.warning(f"[Browser] get_rendered_text {url} 失败: {e}")
            return ''

    def capture_first_json_response(self, url, url_keyword=None, url_keywords=None,
                                    mobile=False, timeout=30000,
                                    close_selectors=None, extra_headers=None,
                                    wait_after_ms=4000, scroll=False,
                                    collect_keyword=None):
        """
        访问 url 并监听响应；命中**任一** url_keyword(s) 且能解析为 JSON 的响应即返回。

        参数:
            url_keyword:    单个匹配关键字（兼容旧调用）
            url_keywords:   关键字列表（任一匹配即命中）
            collect_keyword: 字符串或列表；只要响应 URL 包含该关键字就收集到
                             debug.candidate_urls（即使没命中 url_keyword 也收集）
                             — 用于诊断"我到底应该匹配哪个端点"

        返回 (data_or_None, debug_dict)
            debug_dict: {
                'final_url': matched_url|navigation_url,
                'errors': [...],
                'candidate_urls': [...],   # 命中 collect_keyword 的所有响应 URL（最多 30 条）
            }
        """
        keywords = []
        if url_keyword:
            keywords.append(url_keyword)
        if url_keywords:
            keywords.extend([k for k in url_keywords if k])

        if collect_keyword is None:
            collect_kw = []
        elif isinstance(collect_keyword, str):
            collect_kw = [collect_keyword]
        else:
            collect_kw = list(collect_keyword)

        debug = {'final_url': url, 'errors': [], 'candidate_urls': []}
        captured = {'data': None, 'matched_url': None}

        try:
            with self._page(mobile=mobile, extra_headers=extra_headers) as page:
                def on_response(resp):
                    rurl = resp.url

                    # 1) 收集候选 URL（用于诊断，最多 30 条）
                    if collect_kw and len(debug['candidate_urls']) < 30:
                        if any(ck in rurl for ck in collect_kw):
                            if rurl not in debug['candidate_urls']:
                                debug['candidate_urls'].append(rurl)

                    # 2) 命中匹配关键字 → 解析 JSON
                    if captured['data'] is not None:
                        return
                    if not keywords:
                        return
                    if not any(kw in rurl for kw in keywords):
                        return

                    try:
                        data = resp.json()
                    except Exception as e:
                        debug['errors'].append(f"json parse fail @ {rurl[:80]}: {e}")
                        return

                    captured['data'] = data
                    captured['matched_url'] = rurl

                page.on('response', on_response)

                page.goto(url, wait_until='domcontentloaded', timeout=timeout)
                self._close_popups(page, close_selectors)

                if scroll:
                    try:
                        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        page.wait_for_timeout(400)
                        page.evaluate('window.scrollTo(0, document.body.scrollHeight/2)')
                    except Exception:
                        pass

                try:
                    page.wait_for_timeout(wait_after_ms)
                except Exception:
                    pass

            if captured['matched_url']:
                debug['final_url'] = captured['matched_url']
            return captured['data'], debug

        except Exception as e:
            debug['errors'].append(str(e))
            return None, debug
