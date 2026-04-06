"""
Playwright 无头浏览器助手
用于访问SPA页面、渲染JS、提取热度值等需要浏览器执行的场景。

安装:
    pip install playwright==1.40.0
    playwright install chromium

在 Debian/Ubuntu 系统上还需要安装 Chrome 依赖:
    playwright install-deps chromium
    # 或手动安装:
    # apt install -y libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 libasound2 libpango-1.0-0 libcairo2
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
            html = browser.get_html(url, mobile=True, wait_for='.heat')
            value = browser.get_text(url, selector='.heat-value')
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
                "  pip install playwright==1.40.0\n"
                "  playwright install chromium"
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
        """创建临时页面上下文"""
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

        # 屏蔽图片/媒体/字体以加速
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

    def get_html(self, url, mobile=False, wait_for=None, timeout=20000,
                 close_selectors=None, extra_headers=None):
        """
        访问URL并返回渲染后的HTML。

        参数:
            url: 目标URL
            mobile: 是否使用移动端UA
            wait_for: CSS选择器，等待该元素出现才返回
            timeout: 超时毫秒数
            close_selectors: 需要关闭的弹窗/广告选择器列表
            extra_headers: 额外HTTP头

        返回:
            HTML字符串 或 None
        """
        try:
            with self._page(mobile=mobile, extra_headers=extra_headers) as page:
                page.goto(url, wait_until='domcontentloaded', timeout=timeout)

                # 关闭弹窗/广告
                if close_selectors:
                    for sel in close_selectors:
                        try:
                            el = page.query_selector(sel)
                            if el:
                                el.click(timeout=2000)
                        except Exception:
                            pass

                # 等待目标元素
                if wait_for:
                    try:
                        page.wait_for_selector(wait_for, timeout=timeout, state='visible')
                    except Exception:
                        # 等待失败也返回已有HTML，给调用方机会用正则兜底
                        pass

                # 额外等待JS执行完成
                try:
                    page.wait_for_timeout(800)
                except Exception:
                    pass

                return page.content()

        except Exception as e:
            logger.warning(f"[Browser] 访问{url}失败: {e}")
            return None

    def get_text_by_selector(self, url, selector, mobile=False,
                             timeout=20000, close_selectors=None):
        """访问URL并返回指定CSS选择器的text内容"""
        try:
            with self._page(mobile=mobile) as page:
                page.goto(url, wait_until='domcontentloaded', timeout=timeout)

                if close_selectors:
                    for sel in close_selectors:
                        try:
                            el = page.query_selector(sel)
                            if el:
                                el.click(timeout=2000)
                        except Exception:
                            pass

                try:
                    el = page.wait_for_selector(selector, timeout=timeout, state='visible')
                    return el.text_content() if el else None
                except Exception:
                    return None
        except Exception as e:
            logger.warning(f"[Browser] 取{selector}失败 {url}: {e}")
            return None
