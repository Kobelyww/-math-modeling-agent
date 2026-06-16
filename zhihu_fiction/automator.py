"""Playwright 浏览器自动化发布器。

支持交互式登录：用户在弹出的浏览器窗口中手动登录，
登录状态持久化到 data/auth/，后续运行无需重复登录。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .config import APP_ROOT

logger = logging.getLogger(__name__)

AUTH_DIR = APP_ROOT / "data" / "auth"

PLATFORM_CONFIGS = {
    "zhihu": {
        "name": "知乎盐选",
        "login_url": "https://www.zhihu.com/signin",
        "publish_url": "https://zhuanlan.zhihu.com/write",
        "logged_in_indicator": "写文章",
    },
    "qidian": {
        "name": "起点中文网",
        "login_url": "https://writer.qq.com",
        "publish_url": "https://writer.qq.com",
        "logged_in_indicator": "作家专区",
    },
    "fanqie": {
        "name": "番茄小说",
        "login_url": "https://novelist.toutiao.com",
        "publish_url": "https://novelist.toutiao.com",
        "logged_in_indicator": "作品管理",
    },
}


class AutomatorError(Exception):
    pass


class LoginTimeout(AutomatorError):
    pass


class Automator:
    def __init__(self, headless: bool = False, slow_mo: int = 300) -> None:
        self._headless = headless
        self._slow_mo = slow_mo
        self._playwright = None
        self._browser = None
        self._contexts: dict[str, object] = {}
        AUTH_DIR.mkdir(parents=True, exist_ok=True)

    def _ensure_playwright(self):
        if self._playwright is None:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                raise AutomatorError(
                    "playwright 未安装。请运行: pip install playwright && playwright install chromium"
                )
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=self._headless,
                slow_mo=self._slow_mo,
            )

    def _session_path(self, platform: str) -> Path:
        return AUTH_DIR / f"{platform}_session.json"

    def _is_logged_in(self, platform: str) -> bool:
        cfg = PLATFORM_CONFIGS[platform]
        session_path = self._session_path(platform)

        if not session_path.exists():
            return False

        try:
            self._ensure_playwright()
            context = self._browser.new_context(storage_state=str(session_path))
            page = context.new_page()
            resp = page.goto(cfg["publish_url"], wait_until="domcontentloaded", timeout=20000)
            if resp is None:
                context.close()
                return False

            page.wait_for_timeout(2000)
            content = page.content()
            logged_in = cfg["logged_in_indicator"] in content

            try:
                page.wait_for_url(f"**/login**", timeout=3000)
                logged_in = False
            except Exception:
                pass

            context.close()
            return logged_in
        except Exception as exc:
            logger.warning("Login check failed for %s: %s", platform, exc)
            return False

    def login_interactive(self, platform: str, timeout_seconds: int = 180) -> bool:
        """打开浏览器让用户手动登录，登录成功后自动保存 session。

        Returns:
            True 表示登录成功，False 表示超时或用户放弃。
        """
        self._ensure_playwright()

        cfg = PLATFORM_CONFIGS[platform]
        context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.new_page()
        page.goto(cfg["login_url"], wait_until="domcontentloaded")

        print(f"\n  [{cfg['name']}] 浏览器已打开，请在浏览器中完成登录。")
        print(f"  [{cfg['name']}] 登录网址: {cfg['login_url']}")
        print(f"  [{cfg['name']}] 等待登录完成...（{timeout_seconds}秒超时）")

        start = time.time()
        logged_in = False

        while time.time() - start < timeout_seconds:
            try:
                current_url = page.url
                page.wait_for_timeout(500)

                if cfg["logged_in_indicator"] in page.content():
                    page.wait_for_timeout(3000)
                    if cfg["logged_in_indicator"] in page.content():
                        logged_in = True
                        break

                time.sleep(0.5)
            except Exception:
                time.sleep(1)
                continue

        if logged_in:
            session_path = self._session_path(platform)
            context.storage_state(path=str(session_path))
            print(f"  [{cfg['name']}] 登录成功！Session 已保存至 {session_path}")
            page.close()
            context.close()
            return True
        else:
            if "login" not in page.url.lower() and cfg["logged_in_indicator"] in page.content():
                session_path = self._session_path(platform)
                context.storage_state(path=str(session_path))
                print(f"  [{cfg['name']}] 登录状态已保存")
                page.close()
                context.close()
                return True

            print(f"  [{cfg['name']}] 登录超时，请重试。")
            page.close()
            context.close()
            return False

    def ensure_login(self, platform: str) -> bool:
        """确保已登录。如果已有有效 session 则直接返回，否则触发交互式登录。"""
        if self._is_logged_in(platform):
            print(f"  [{PLATFORM_CONFIGS[platform]['name']}] 已登录（session 有效）")
            return True
        print(f"  [{PLATFORM_CONFIGS[platform]['name']}] 需要登录")
        return self.login_interactive(platform)

    def auto_publish_zhihu(self, title: str, content: str, tags: list[str]) -> bool:
        """自动发布到知乎专栏。委托给更成熟的 ZhihuPublisher。"""
        from .automator_zhihu import ZhihuPublisher, LoginRequired, PublishError

        publisher = ZhihuPublisher(headless=self._headless, slow_mo=self._slow_mo)
        try:
            if not publisher.is_logged_in():
                if not publisher.login_interactive():
                    print("  [知乎] 登录失败，发布取消")
                    return False

            result = publisher.publish(title=title, content=content, tags=tags or [])
            return result.get("success", False)

        except LoginRequired:
            print("  [知乎] Session 过期，需要重新登录")
            if publisher.login_interactive():
                try:
                    result = publisher.publish(title=title, content=content, tags=tags or [])
                    return result.get("success", False)
                except Exception as exc:
                    print(f"  [知乎] 重试发布失败: {exc}")
                    return False
            return False
        except PublishError as exc:
            print(f"  [知乎] 发布失败: {exc}")
            return False
        finally:
            publisher.cleanup()

    def auto_publish_qidian(
        self, title: str, content: str, metadata: dict, chapters: list
    ) -> bool:
        """自动发布到起点中文网。

        起点发布流程较复杂：创建新书 → 填写元数据 → 创建分卷 → 逐章发布。
        由于步骤多且 UI 变化频繁，当前采用半自动方式：
        打开创作后台，逐步骤引导用户确认。
        """
        self._ensure_playwright()
        cfg = PLATFORM_CONFIGS["qidian"]
        session_path = self._session_path("qidian")

        if not self._is_logged_in("qidian"):
            raise AutomatorError("起点未登录，请先调用 ensure_login('qidian')")

        context = self._browser.new_context(
            storage_state=str(session_path),
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.new_page()

        try:
            print(f"\n  [起点] 正在打开作家专区...")
            page.goto(cfg["publish_url"], wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            book_name = metadata.get("book_title", title)
            synopsis = metadata.get("synopsis", "")
            category = metadata.get("category", "都市")
            tags = metadata.get("tags", [])

            print(f"\n  [起点] ====== 请在浏览器中完成以下操作 ======")
            print(f"  [起点] 1. 点击「创建新书」")
            print(f"  [起点] 2. 填入以下信息：")
            print(f"         书名: {book_name}")
            print(f"         分类: {category}")
            print(f"         标签: {', '.join(tags)}")
            print(f"         简介: {synopsis[:100]}...")
            print(f"  [起点] 3. 创建成功后，创建分卷并添加章节")
            print(f"  [起点] 4. 按顺序粘贴下方章节内容")

            if chapters:
                print(f"  [起点] 共 {len(chapters)} 章待发布")
                for ch in chapters[:5]:
                    print(f"         - {ch.title} ({len(ch.content)}字)")
                if len(chapters) > 5:
                    print(f"         ... 还有 {len(chapters) - 5} 章")

            print(f"\n  [起点] 等待操作完成...（最长 180 秒）")
            page.wait_for_timeout(180000)
            print(f"  [起点] 发布流程结束")
            return True

        except Exception as exc:
            print(f"  [起点] 自动化失败: {exc}")
            return False
        finally:
            page.close()
            context.close()

    def auto_publish_fanqie(
        self, title: str, content: str, metadata: dict, chapters: list
    ) -> bool:
        """自动发布到番茄小说。

        番茄作家后台 novelist.toutiao.com，流程类似起点但更简单。
        同样采用半自动引导方式。
        """
        self._ensure_playwright()
        cfg = PLATFORM_CONFIGS["fanqie"]
        session_path = self._session_path("fanqie")

        if not self._is_logged_in("fanqie"):
            raise AutomatorError("番茄未登录，请先调用 ensure_login('fanqie')")

        context = self._browser.new_context(
            storage_state=str(session_path),
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.new_page()

        try:
            print(f"\n  [番茄] 正在打开作家助手...")
            page.goto(cfg["publish_url"], wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            book_name = metadata.get("book_title", title)
            synopsis = metadata.get("synopsis", "")
            category = metadata.get("category", "都市")
            tags = metadata.get("tags", [])

            print(f"\n  [番茄] ====== 请在浏览器中完成以下操作 ======")
            print(f"  [番茄] 1. 点击「创建作品」")
            print(f"  [番茄] 2. 填入以下信息：")
            print(f"         书名: {book_name}")
            print(f"         分类: {category}")
            print(f"         标签: {', '.join(tags)}")
            print(f"         简介: {synopsis[:100]}...")
            print(f"  [番茄] 3. 创建成功后，在「章节管理」中添加章节")
            print(f"  [番茄] 4. 按顺序粘贴下方章节内容")

            if chapters:
                print(f"  [番茄] 共 {len(chapters)} 章待发布")

            print(f"\n  [番茄] 等待操作完成...（最长 180 秒）")
            page.wait_for_timeout(180000)
            print(f"  [番茄] 发布流程结束")
            return True

        except Exception as exc:
            print(f"  [番茄] 自动化失败: {exc}")
            return False
        finally:
            page.close()
            context.close()

    def publish_all(
        self,
        title: str,
        content: str,
        genre: str,
        metadata_map: dict,
        chapters_map: dict | None = None,
        platforms: list[str] | None = None,
    ) -> dict[str, bool]:
        """批量自动发布到多个平台。"""
        platforms = platforms or ["zhihu", "qidian", "fanqie"]
        results: dict[str, bool] = {}

        chapters_map = chapters_map or {}

        for platform in platforms:
            try:
                meta = metadata_map.get(platform, {})
                chapters = chapters_map.get(platform, [])

                if platform == "zhihu":
                    # ZhihuPublisher handles login internally
                    tags = meta.get("tags", []) if isinstance(meta, dict) else getattr(meta, "tags", [])
                    results["zhihu"] = self.auto_publish_zhihu(title, content, tags)
                    continue

                if not self.ensure_login(platform):
                    results[platform] = False
                    continue

            except AutomatorError as exc:
                print(f"  {platform}: {exc}")
                results[platform] = False
                continue

            try:
                if platform == "qidian":
                    qd_meta = meta if isinstance(meta, dict) else {
                        "book_title": getattr(meta, "book_title", title),
                        "synopsis": getattr(meta, "synopsis", ""),
                        "category": getattr(meta, "category", genre),
                        "tags": getattr(meta, "tags", []),
                    }
                    results["qidian"] = self.auto_publish_qidian(title, content, qd_meta, chapters)
                elif platform == "fanqie":
                    fq_meta = meta if isinstance(meta, dict) else {
                        "book_title": getattr(meta, "book_title", title),
                        "synopsis": getattr(meta, "synopsis", ""),
                        "category": getattr(meta, "category", genre),
                        "tags": getattr(meta, "tags", []),
                    }
                    results["fanqie"] = self.auto_publish_fanqie(title, content, fq_meta, chapters)
            except Exception as exc:
                print(f"  [{platform}] 发布失败: {exc}")
                results[platform] = False

        return results

    def cleanup(self) -> None:
        """关闭浏览器和 Playwright 实例。"""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
