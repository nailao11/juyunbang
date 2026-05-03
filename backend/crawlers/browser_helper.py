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

    def capture_first_json_response(self, url, url_keyword, mobile=False, timeout=30000,
                                    close_selectors=None, extra_headers=None,
                                    wait_after_ms=4000, scroll=False):
        """
        访问 url 并监听响应；命中第一个 url 包含 url_keyword 且能解析为 JSON 的响应即返回。

        返回 (data_or_None, debug_dict)
            debug_dict: {'final_url': matched_url|navigation_url, 'errors': [...]}
        """
        debug = {'final_url': url, 'errors': []}
        captured = {'data': None, 'matched_url': None}

        try:
            with self._page(mobile=mobile, extra_headers=extra_headers) as page:
                def on_response(resp):
                    if captured['data'] is not None:
                        return
                    try:
                        if url_keyword and url_keyword in resp.url:
                            try:
                                data = resp.json()
                            except Exception as e:
                                debug['errors'].append(f"json parse: {e}")
                                return
                            captured['data'] = data
                            captured['matched_url'] = resp.url
                    except Exception as e:
                        debug['errors'].append(f"on_response: {e}")

                page.on('response', on_response)

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

            if captured['matched_url']:
                debug['final_url'] = captured['matched_url']
            return captured['data'], debug

        except Exception as e:
            debug['errors'].append(str(e))
            return None, debug
