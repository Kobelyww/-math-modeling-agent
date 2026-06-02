"""Fully automated Zhihu article publisher via Playwright.

Provides ZhihuPublisher with interactive login, session persistence,
multi-selector content filling, automatic publish button clicking,
and result verification.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .config import APP_ROOT

AUTH_DIR = APP_ROOT / "data" / "auth"
DEBUG_DIR = APP_ROOT / "data" / "debug"
SESSION_PATH = AUTH_DIR / "zhihu_session.json"
WRITE_URL = "https://zhuanlan.zhihu.com/write"


class PublishError(Exception):
    """Recoverable error during publishing -- selector failure, timeout, etc."""

    pass


class LoginRequired(PublishError):
    """Session expired or not logged in; interactive login is required."""

    pass


class ZhihuPublisher:
    """Fully automated Zhihu article publisher.

    Uses Playwright to simulate browser operations. Supports session
    persistence, multi-selector fallback strategies, and debug screenshots.

    Typical usage::

        publisher = ZhihuPublisher()
        publisher.ensure_login()
        result = publisher.publish("My Title", "Article content here...", tags=["tag1"])
        publisher.cleanup()
    """

    def __init__(self, headless: bool = False, slow_mo: int = 200) -> None:
        self._headless = headless
        self._slow_mo = slow_mo
        self._playwright = None
        self._browser = None
        AUTH_DIR.mkdir(parents=True, exist_ok=True)
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    def _ensure_browser(self):
        """Lazily initialise Playwright and launch a Chromium browser."""
        if self._browser is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise PublishError(
                "playwright is not installed. Run: pip install playwright && "
                "playwright install chromium"
            )
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self._headless,
            slow_mo=self._slow_mo,
        )

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login_interactive(self, timeout_seconds: int = 180) -> bool:
        """Open a browser window and wait for the user to log in manually.

        Once a successful login is detected the session is persisted to
        *SESSION_PATH* for future use.

        Returns:
            True if login was detected within the timeout, False otherwise.
        """
        self._ensure_browser()
        context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.new_page()
        page.goto("https://www.zhihu.com/signin", wait_until="domcontentloaded")

        print("\n  [Zhihu] Browser opened -- please log in manually.")
        print("  [Zhihu] Login URL: https://www.zhihu.com/signin")
        print(f"  [Zhihu] Waiting for login... ({timeout_seconds}s timeout)")

        start = time.time()
        logged_in = False

        while time.time() - start < timeout_seconds:
            try:
                page.wait_for_timeout(500)
                current_url = page.url

                # Direct navigation to zhuanlan write page means already logged in
                if "zhuanlan.zhihu.com" in current_url and "write" in current_url:
                    page.wait_for_timeout(2000)
                    logged_in = True
                    break

                # Redirected away from signin page means login succeeded
                if current_url.startswith("https://www.zhihu.com/") and "signin" not in current_url:
                    page.wait_for_timeout(2000)
                    # Confirm by navigating to the write page
                    page.goto(WRITE_URL, wait_until="domcontentloaded", timeout=10000)
                    page.wait_for_timeout(2000)
                    if "write" in page.url or "zhuanlan" in page.url:
                        logged_in = True
                        break

                time.sleep(0.5)
            except Exception:
                time.sleep(1)

        if logged_in:
            context.storage_state(path=str(SESSION_PATH))
            print(f"  [Zhihu] Login successful! Session saved to {SESSION_PATH}")
            page.close()
            context.close()
            return True

        print("  [Zhihu] Login timed out. Please try again.")
        page.close()
        context.close()
        return False

    def is_logged_in(self) -> bool:
        """Check whether the saved session file is still valid.

        Opens the write page with the saved session and checks that it is
        not redirected to the login page.
        """
        if not SESSION_PATH.exists():
            return False

        try:
            self._ensure_browser()
            context = self._browser.new_context(
                storage_state=str(SESSION_PATH),
                locale="zh-CN",
            )
            page = context.new_page()
            page.goto(WRITE_URL, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)

            current_url = page.url
            logged_in = "write" in current_url or "zhuanlan" in current_url

            # Redirect to signin/login means the session is stale
            if "signin" in current_url or "login" in current_url:
                logged_in = False

            context.close()
            return logged_in
        except Exception:
            return False

    def ensure_login(self) -> bool:
        """Ensure the user is logged in.

        Prefers a saved session; falls back to interactive login if the
        saved session is missing or expired.
        """
        if self.is_logged_in():
            print("  [Zhihu] Already logged in (session valid)")
            return True
        print("  [Zhihu] Login required")
        return self.login_interactive()

    # ------------------------------------------------------------------
    # Publish flow
    # ------------------------------------------------------------------

    def publish(
        self,
        title: str,
        content: str,
        tags: list[str] | None = None,
        genre: str = "",
    ) -> dict:
        """Execute the full Zhihu article publish flow.

        Steps:
            1. Verify login state.
            2. Open a browser context with the saved session.
            3. Navigate to the write page.
            4. Fill in the title.
            5. Fill in the article body.
            6. Add tags (optional).
            7. Click the publish button.
            8. Handle the confirmation dialog.
            9. Wait for the article URL and verify success.
            10. Capture a success screenshot.

        Args:
            title: Article title.
            content: Article body (plain text).
            tags: Optional list of tags to attach.
            genre: Article category (reserved for future use).

        Returns:
            A dict::

                {"success": bool, "url": str, "message": str}

        Raises:
            LoginRequired: Session expired.
            PublishError: An unrecoverable error during publishing.
        """
        if not self.is_logged_in():
            raise LoginRequired(
                "Zhihu session has expired. Call ensure_login() first."
            )

        self._ensure_browser()
        context = self._browser.new_context(
            storage_state=str(SESSION_PATH),
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.new_page()

        try:
            # Step 1 -- navigate to the write page
            print("\n  [Zhihu] Opening the write page...")
            page.goto(WRITE_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Double-check we were not redirected to the login page
            if "signin" in page.url or "login" in page.url:
                raise LoginRequired(
                    "Session expired -- redirected to the login page."
                )

            # Step 2 -- fill title
            self._fill_title(page, title)

            # Step 3 -- fill content
            self._fill_content(page, content)

            # Step 4 -- add tags
            if tags:
                self._add_tags(page, tags)

            # Step 5 -- click publish
            self._click_publish(page)

            # Step 6 -- confirm dialog if present
            self._confirm_publish(page)

            # Step 7 -- wait for article URL
            article_url = self._wait_for_article(page, timeout=30)

            # Screenshot on success
            self._save_debug_screenshot(page, "publish_success.png")

            return {
                "success": True,
                "url": article_url,
                "message": f"Article \"{title}\" published successfully!",
            }

        except LoginRequired:
            raise
        except PublishError:
            self._save_debug_screenshot(
                page, f"publish_error_{int(time.time())}.png"
            )
            raise
        except Exception as exc:
            self._save_debug_screenshot(
                page, f"publish_error_{int(time.time())}.png"
            )
            raise PublishError(
                f"Unexpected error during publishing: {exc}"
            ) from exc
        finally:
            page.close()
            context.close()

    # ------------------------------------------------------------------
    # Step helpers
    # ------------------------------------------------------------------

    def _fill_title(self, page, title: str) -> None:
        """Fill the article title using a multi-selector fallback strategy.

        Order:
            1. textarea[placeholder*='标题']
            2. input[placeholder*='标题']
            3. h1[contenteditable='true']
            4. .WriteIndex-titleInput textarea
        """
        selectors = [
            "textarea[placeholder*='标题']",
            "input[placeholder*='标题']",
            "h1[contenteditable='true']",
            ".WriteIndex-titleInput textarea",
        ]

        for selector in selectors:
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=3000):
                    el.click()
                    el.fill("")
                    el.type(title, delay=20)
                    print(
                        f"  [Zhihu] Title filled (selector: {selector})"
                    )
                    return
            except Exception:
                continue

        raise PublishError(
            "Could not locate the title input. Tried selectors: "
            f"{', '.join(selectors)}"
        )

    def _fill_content(self, page, content: str) -> None:
        """Fill the article body using a multi-selector + JS fallback strategy.

        Order:
            1. .public-DraftEditor-content
            2. div[contenteditable='true']
            3. [role='textbox']

        After selecting the element, tries JavaScript ``execCommand('insertText')``
        first, then falls back to Playwright's ``type()``.
        """
        selectors = [
            ".public-DraftEditor-content",
            "div[contenteditable='true']",
            "[role='textbox']",
        ]

        for selector in selectors:
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=3000):
                    el.click()

                    try:
                        el.evaluate(
                            """(el, text) => {
                                el.focus();
                                document.execCommand('selectAll', false, null);
                                document.execCommand('insertText', false, text);
                            }""",
                            content,
                        )
                    except Exception:
                        el.type(content, delay=5)

                    print(
                        f"  [Zhihu] Content filled ({len(content)} chars) "
                        f"(selector: {selector})"
                    )
                    return
            except Exception:
                continue

        raise PublishError(
            "Could not locate the content editor. Tried selectors: "
            f"{', '.join(selectors)}"
        )

    def _add_tags(self, page, tags: list[str]) -> None:
        """Type tags into the tag input, pressing Enter after each one."""
        tag_selectors = [
            "input[placeholder*='标签']",
            ".TagInput input",
            "[data-testid='article-tags'] input",
        ]

        tag_input = None
        for selector in tag_selectors:
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=3000):
                    tag_input = el
                    break
            except Exception:
                continue

        if tag_input is None:
            print("  [Zhihu] Tag input not found, skipping tags")
            return

        tag_input.click()
        for tag in tags:
            tag_input.type(tag, delay=15)
            page.wait_for_timeout(400)
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)

        print(f"  [Zhihu] Tags added: {', '.join(tags)}")

    def _click_publish(self, page) -> None:
        """Locate and click the publish button.

        Strategy:
            1. ``button:text-is('发布')``
            2. ``button:text-is('发表')``
            3. ``button:has-text('发布')``
            4. Fallback: iterate all buttons for exact text "发布"
        """
        publish_selectors = [
            "button:text-is('发布')",
            "button:text-is('发表')",
            "button:has-text('发布')",
        ]

        for selector in publish_selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=5000):
                    btn.click()
                    print(
                        f"  [Zhihu] Publish button clicked (selector: {selector})"
                    )
                    return
            except Exception:
                continue

        # Ultimate fallback -- iterate every button for exact text match
        try:
            buttons = page.locator("button")
            count = buttons.count()
            for i in range(count):
                try:
                    text = buttons.nth(i).inner_text()
                    if text.strip() == "发布":
                        buttons.nth(i).click()
                        print("  [Zhihu] Publish button clicked (fallback iteration)")
                        return
                except Exception:
                    continue
        except Exception:
            pass

        raise PublishError(
            "Could not locate the publish button. Tried all selector strategies."
        )

    def _confirm_publish(self, page) -> None:
        """Handle the optional confirmation dialog after clicking publish.

        Strategy:
            1. ``.Modal button:has-text('确认发布')``
            2. ``button:has-text('确认发布')``
            3. ``[role='dialog'] button:has-text('确认')``
            4. ``button:has-text('确定')``
            5. ``button:has-text('确认')``

        If no dialog appears within a short wait, this is not considered
        an error.
        """
        confirm_selectors = [
            ".Modal button:has-text('确认发布')",
            "button:has-text('确认发布')",
            "[role='dialog'] button:has-text('确认')",
            "button:has-text('确定')",
            "button:has-text('确认')",
        ]

        page.wait_for_timeout(1000)

        for selector in confirm_selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    print(
                        f"  [Zhihu] Publish confirmed (selector: {selector})"
                    )
                    return
            except Exception:
                continue

        print("  [Zhihu] No confirmation dialog needed")

    def _wait_for_article(self, page, timeout: int = 30) -> str:
        """Wait for the page URL to contain ``/p/`` after publishing.

        Returns:
            The article URL.

        Raises:
            PublishError: If the URL does not change within *timeout* seconds.
        """
        start = time.time()
        while time.time() - start < timeout:
            current_url = page.url
            if "/p/" in current_url:
                print(f"  [Zhihu] Published! Article URL: {current_url}")
                return current_url
            page.wait_for_timeout(500)

        self._save_debug_screenshot(page, "publish_timeout.png")
        raise PublishError(
            f"No article URL detected within {timeout}s. Current URL: {page.url}"
        )

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------

    def _save_debug_screenshot(self, page, filename: str) -> None:
        """Save a full-page screenshot to *DEBUG_DIR* for post-mortem analysis."""
        try:
            screenshot_path = DEBUG_DIR / filename
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"  [Zhihu] Debug screenshot saved: {screenshot_path}")
        except Exception as exc:
            print(f"  [Zhihu] Failed to save screenshot: {exc}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Close the browser and stop the Playwright instance."""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._browser = None
        self._playwright = None