"""知乎爆款小说多智能体创作系统 — 命令行入口

用法:
    python -m zhihu_fiction.cli          # 交互式命令模式
    python -m zhihu_fiction.cli --help   # 查看帮助
"""

from __future__ import annotations

# 支持直接执行：python cli.py
if __name__ == "__main__" and __package__ is None:
    import sys as _sys
    from pathlib import Path as _Path

    _parent = _Path(__file__).resolve().parent.parent
    if str(_parent) not in _sys.path:
        _sys.path.insert(0, str(_parent))
    __package__ = "zhihu_fiction"

import json
import sys
from pathlib import Path

from .core.config import APP_ROOT, load_settings
from .core.llm import create_llm
from .fiction.distiller import Distiller
from .fiction.orchestrator import OrchestratorCompat, WorkflowResult, create_orchestrator
from .fiction.pipeline import Pipeline
from .fiction.scraper import list_scraped_files, load_scraped_file, scrape_zhihu_hot
from .fiction.skills_store import SkillsStore
from .drama import DramaAdapter, DramaAdapterError, DramaExporter
from .drama.video import BailianVideoProvider, DramaVideoError, VideoJobStore, create_video_provider
from .exporter import DEFAULT_PLATFORMS, Exporter
from .automator_zhihu import ZhihuPublisher, LoginRequired

HELP_TEXT = """
╔══════════════════════════════════════════════════════╗
║       知乎爆款小说多智能体创作系统                    ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  工作流: 抓取数据 → 蒸馏技能 → 多Agent创作            ║
║                                                      ║
║  命令:                                                ║
║  /scrape         抓取知乎热榜（API优先）              ║
║  /search <关键词> 搜索知乎话题                        ║
║  /manual         手动录入热门文章                      ║
║  /files          列出已抓取的内容文件                  ║
║  /outputs        列出已创作的小说文件                  ║
║  /load <文件名>  加载已保存的小说（用于重新发布）      ║
║  /continue       续写下一章（需先 /load 已有小说）      ║
║  /distill        从已抓取内容蒸馏创作技能              ║
║  /distill_file <文件>  蒸馏指定文件                   ║
║  /skills         查看已掌握的创作技能                  ║
║  /skill <题材>   查看指定题材的完整技能卡              ║
║  /create <主题>  多Agent创作（全流程模式）            ║
║  /fast <主题>    快速创作（跳过评审和润色）            ║
║  /polish <主题>  精打磨模式                           ║
║  /stream <主题>  流式输出创作过程                     ║
║  /publish        导出最近创作到多平台发布包            ║
║  /publish <主题> 创作并导出多平台发布包                ║
║  /drama         将最近/已加载小说转成短剧视频Prompt包   ║
║  /drama_video [数量]  生成Prompt包并提交百炼视频任务    ║
║  /autopublish    浏览器自动化发布（需安装 playwright）  ║
║  /mode <模式>    设置创作模式 (fast/polish/full)      ║
║  /genre <题材>   设置目标题材 (如: 悬疑/言情/职场)    ║
║  /help           显示此帮助                           ║
║  /exit           退出                                 ║
║                                                      ║
║  示例:                                                ║
║  > /scrape                                            ║
║  > /distill                                           ║
║  > /create 一个穿越到古代用现代医学救人的故事          ║
║  > /genre 悬疑                                        ║
║  > /fast 密室逃脱中发现同伴是凶手                      ║
╚══════════════════════════════════════════════════════╝
""".strip()


class CLI:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.skills_store = SkillsStore()
        coordinator, reviewer, pipeline_llm = create_orchestrator(
            self.settings, skills_store=self.skills_store
        )
        self.orchestrator = OrchestratorCompat(
            coordinator=coordinator,
            reviewer=reviewer,
            llm=pipeline_llm,
            settings=self.settings,
            skills_store=self.skills_store,
        )
        self.pipeline = Pipeline(
            coordinator=coordinator,
            reviewer=reviewer,
            llm=pipeline_llm,
            publisher=ZhihuPublisher(headless=False, slow_mo=200),
        )
        self._schedule_active = False
        self.mode: str = "full"
        self.genre: str | None = None
        self.distiller = Distiller(self.settings)
        self.last_result: WorkflowResult | None = None
        self.exporter = Exporter(create_llm(self.settings, temperature=0.3))

    # ---- 抓取命令 ----

    def cmd_scrape(self) -> None:
        print("\n[抓取] 正在抓取知乎热榜...")
        items = scrape_zhihu_hot()
        if not items:
            print("抓取失败或返回空结果。")
            return

        from .fiction.scraper import save_scraped_content
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved = save_scraped_content(items, f"hot_{timestamp}")
        print(f"已抓取 {len(items)} 条热门话题 → {saved}")

        for i, item in enumerate(items[:10], 1):
            score = item.get("hot_score", 0)
            print(f"  {i}. [{score:.0f}] {item['title'][:60]}")

    def cmd_search(self, keyword: str) -> None:
        print(f"\n[搜索] 正在搜索: {keyword}...")
        from .fiction.scraper import save_scraped_content, search_zhihu_topic
        from datetime import datetime

        items = search_zhihu_topic(keyword)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved = save_scraped_content(items, f"search_{keyword}_{timestamp}")
        print(f"搜索结果 {len(items)} 条 → {saved}")
        for i, item in enumerate(items[:10], 1):
            print(f"  {i}. {item['title'][:60]}")

    def cmd_manual(self) -> None:
        print("\n[手动录入] 请输入文章信息（输入空行结束）：")
        try:
            title = input("标题: ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not title:
            print("标题不能为空。")
            return

        try:
            excerpt = input("摘要/正文片段: ").strip()
            score_str = input("点赞数/热度 (可为空): ").strip()
        except (EOFError, KeyboardInterrupt):
            return

        score = 0.0
        if score_str:
            score = _parse_manual_score(score_str)

        from .fiction.scraper import manual_entry
        saved = manual_entry(title, excerpt, hot_score=score)
        print(f"已录入并保存: {saved}")

    def cmd_files(self) -> None:
        files = list_scraped_files()
        if not files:
            print("暂无已抓取的内容文件。")
            return
        print(f"\n已抓取 {len(files)} 个文件:")
        for f in files:
            items = load_scraped_file(f)
            print(f"  {f.name} ({len(items)} 条记录)")

    # ---- 蒸馏命令 ----

    def cmd_distill(self, filename: str | None = None) -> None:
        if filename:
            path = APP_ROOT / "data" / "scraped" / filename
            if not path.exists():
                print(f"文件不存在: {filename}")
                return
            articles = load_scraped_file(path)
        else:
            files = list_scraped_files()
            if not files:
                print("没有已抓取的内容。请先运行 /scrape 或手动添加内容到 data/scraped/")
                return
            articles = []
            for f in files:
                articles.extend(load_scraped_file(f))

        if not articles:
            print("没有可蒸馏的内容。")
            return

        print(f"\n[蒸馏] 开始从 {len(articles)} 篇文章中提炼创作技能...")
        print("[蒸馏] 这可能需要几分钟，请耐心等待...\n")

        try:
            skills = self.distiller.run_full_pipeline(articles)
            self.skills_store = skills
            self.orchestrator.skills = skills

            genres = skills.list_genres()
            print(f"\n[蒸馏] 完成！已掌握 {len(genres)} 个题材的创作技能:")
            for g in genres:
                print(f"  - {g}")
        except Exception as exc:
            print(f"[蒸馏] 过程出错: {exc}")
            print("提示：请确保 DEEPSEEK_API_KEY 已正确配置")

    # ---- 技能命令 ----

    def cmd_skills(self) -> None:
        genres = self.skills_store.list_genres()
        if not genres:
            print("技能库为空。请先运行 /scrape 然后 /distill")
            return
        print(f"\n已蒸馏 {len(genres)} 个题材:")
        for g in genres:
            print(f"  - {g}")

    def cmd_skill_detail(self, genre: str) -> None:
        content = self.skills_store.get_skill(genre)
        if content is None:
            print(f"未找到 [{genre}] 题材的技能卡。")
            return
        print(f"\n{'='*60}")
        print(content)
        print(f"{'='*60}")

    # ---- 创作命令 ----

    def cmd_create(self, topic: str) -> None:
        print(f"\n{'='*60}")
        print(f"  模式: {self.mode} | 题材: {self.genre or '自动识别'}")
        print(f"  主题: {topic}")
        print(f"{'='*60}\n")

        try:
            if self.mode == "fast":
                result = self.orchestrator.solve_fast(topic, genre=self.genre)
            elif self.mode == "polish":
                result = self.orchestrator.solve_polish(topic, genre=self.genre)
            else:
                result = self.orchestrator.solve_full(topic, genre=self.genre)

            self.last_result = result
            self._print_result(result)
            self._save_result(result)
        except Exception as exc:
            print(f"\n[错误] 创作过程失败: {exc}")
            print("提示：请检查 DEEPSEEK_API_KEY 配置和网络连接")

    def cmd_stream(self, topic: str) -> None:

        def make_handler(label: str):
            first = [True]

            def handler(token: str) -> None:
                if first[0]:
                    print(f"\n{'─'*50}")
                    print(f"  [{label}] 正在生成...")
                    print(f"{'─'*50}\n")
                    first[0] = False
                sys.stdout.write(token)
                sys.stdout.flush()
            return handler

        print(f"\n流式创作模式 | 主题: {topic}\n")
        try:
            result = self.orchestrator.solve_stream(
                topic,
                genre=self.genre,
                on_topic_token=make_handler("选题分析"),
                on_outline_token=make_handler("大纲规划"),
                on_draft_token=make_handler("初稿创作"),
                on_polish_token=make_handler("润色优化"),
                on_synthesis_token=make_handler("总控整合"),
            )
            print("\n\n[流式创作完成]")
            self.last_result = result
            self._save_result(result)
        except Exception as exc:
            print(f"\n[错误] 流式创作失败: {exc}")

    def _print_result(self, result: WorkflowResult) -> None:
        """输出结果：优先展示完整小说正文，分析放在后面"""
        story = result.final_story
        print("\n" + "=" * 60)
        print(f"  选题：{result.topic} | 题材：{result.genre}")
        print("=" * 60)
        print(f"\n{story}")
        print("\n" + "-" * 60)
        print(f"\n{result.synthesis}")

    def _save_result(self, result: WorkflowResult) -> None:
        safe_topic = "".join(c for c in result.topic if c.isalnum() or c in ("-", "_", " "))[:40]
        safe_topic = safe_topic.strip().replace(" ", "_")
        output_dir = APP_ROOT / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 主文件：纯小说正文
        story_path = output_dir / f"{safe_topic}_{ts}.md"
        story_content = (
            f"# {result.topic}\n\n"
            f"> 题材：{result.genre}\n\n"
            f"{result.final_story}\n\n"
            f"---\n\n"
            f"{result.synthesis}"
        )
        story_path.write_text(story_content, encoding="utf-8")
        print(f"\n[小说已保存] {story_path}")

        # 配套文件：完整分析报告
        overview_path = output_dir / f"{safe_topic}_{ts}_分析报告.md"
        overview_path.write_text(result.format_analysis(), encoding="utf-8")
        print(f"[分析已保存] {overview_path}")

    def cmd_outputs(self) -> None:
        output_dir = APP_ROOT / "output"
        files = sorted(output_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            print("暂无已创作的小说。")
            return
        print(f"\n已创作 {len(files)} 篇小说:")
        for f in files[:20]:
            size_kb = f.stat().st_size / 1024
            print(f"  {f.name} ({size_kb:.1f} KB)")

    def cmd_load(self, filename: str) -> None:
        """从已保存的 output 文件加载创作结果，以便后续 /publish 或 /autopublish"""
        output_dir = APP_ROOT / "output"
        candidates = list(output_dir.rglob("*.md"))
        matches = [p for p in candidates if filename in p.name or filename == p.name]
        if not matches:
            matches = sorted(
                [p for p in candidates if filename.lower() in p.name.lower()],
                key=lambda p: p.stat().st_mtime, reverse=True
            )
        if not matches:
            print(f"未找到匹配的文件: {filename}")
            print(f"output 目录中的文件:")
            for p in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
                print(f"  {p.name}")
            return

        filepath = matches[0]
        print(f"加载文件: {filepath.name}")
        text = filepath.read_text(encoding="utf-8")

        from .core.base import extract_story_body

        # Parse topic / genre from the header
        topic = ""
        genre = ""
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# ") and not topic:
                topic = stripped[2:].strip()
            elif stripped.startswith("> 题材：") and not genre:
                genre = stripped[4:].strip()
            if topic and genre:
                break

        story, synthesis = extract_story_body(text)

        from .fiction.orchestrator import StageResult
        self.last_result = WorkflowResult(
            topic=topic or filepath.stem.split("_")[0],
            genre=genre or "未指定",
            topic_analysis=StageResult("选题分析智能体", ""),
            outline=StageResult("大纲规划智能体", ""),
            draft=StageResult("初稿创作智能体", ""),
            polished=story,
            review="从文件加载",
            synthesis=synthesis or "从文件加载",
        )
        print(f"已加载: {self.last_result.topic}")
        print(f"题材: {self.last_result.genre}")
        print(f"正文字数: {len(story)}")
        print(f"现在可以运行 /publish 或 /autopublish")

    def cmd_continue(self) -> None:
        """续写当前加载的小说的下一章"""
        if self.last_result is None:
            print("没有可续写的小说。请先运行 /load <文件名> 加载已有小说。")
            return

        story = self.last_result.final_story
        import re as _re
        _chapter_pattern = _re.compile(r"^#{1,4}\s*第\s*[\d一二三四五六七八九十百千]+\s*章")
        chapters = [l for l in story.split("\n") if _chapter_pattern.match(l.strip())]
        chapter_count = len(chapters)
        if chapter_count == 0:
            chapter_count = 1  # at least chapter 1

        print(f"\n当前已写 {chapter_count} 章，正在续写第 {chapter_count + 1} 章...")
        print(f"主题: {self.last_result.topic}")
        print(f"{'─'*50}")

        try:
            new_chapter = self.orchestrator.continue_story(
                existing_story=story,
                topic=self.last_result.topic,
                genre=self.last_result.genre,
                chapter_count=chapter_count,
            )

            print(f"\n>>> 第 {chapter_count + 1} 章 输出：\n")
            print(new_chapter)

            updated_story = story.rstrip() + "\n\n" + new_chapter.strip()
            self.last_result.polished = updated_story

            output_dir = APP_ROOT / "output"
            safe_topic = "".join(c for c in self.last_result.topic if c.isalnum() or c in ("-", "_", " "))[:40]
            safe_topic = safe_topic.strip().replace(" ", "_")
            matches = list(output_dir.glob(f"{safe_topic}*.md"))
            if matches:
                filepath = matches[0]
                updated = filepath.read_text(encoding="utf-8")
                sep = "\n\n---\n\n"
                parts = updated.split(sep, 1)
                if len(parts) == 2:
                    updated = updated_story + sep + parts[1]
                else:
                    updated = updated_story
                filepath.write_text(updated, encoding="utf-8")
                print(f"\n[已追加到] {filepath.name}")
            else:
                self._save_result(self.last_result)

            print(f"\n续写完成！共 {chapter_count + 1} 章，总字数 {len(updated_story)}")

        except Exception as exc:
            print(f"\n[错误] 续写失败: {exc}")

    def cmd_publish(self, topic: str | None = None) -> None:
        """导出最近创作结果或指定主题的结果为多平台发布包"""
        if topic:
            print(f"\n[创作+发布] 主题: {topic}\n")
            try:
                if self.mode == "fast":
                    result = self.orchestrator.solve_fast(topic, genre=self.genre)
                elif self.mode == "polish":
                    result = self.orchestrator.solve_polish(topic, genre=self.genre)
                else:
                    result = self.orchestrator.solve_full(topic, genre=self.genre)
                self.last_result = result
                self._save_result(result)
            except Exception as exc:
                print(f"\n[错误] 创作失败: {exc}")
                return

        if self.last_result is None:
            print("没有可发布的创作结果。请先运行 /create <主题> 创作一篇小说。")
            return

        print(f"\n[发布] 正在为「{self.last_result.topic}」生成多平台发布包...")
        print("[发布] 正在调用 AI 生成各平台元数据...")

        try:
            output_dirs = self.exporter.export(self.last_result)
            print(f"\n[发布] 完成！已在以下目录生成发布包：\n")
            for platform_key, dir_path in output_dirs.items():
                name_map = {"zhihu": "知乎盐选", "qidian": "起点中文网", "fanqie": "番茄小说"}
                print(f"  {name_map.get(platform_key, platform_key)}:")
                print(f"    {dir_path}/")
                print(f"    ├── 发布内容.md")
                print(f"    ├── 元数据.md")
                print(f"    └── 发布指引.md")
            print(f"\n请进入各平台目录，按「发布指引.md」中的步骤手动发布。")
        except Exception as exc:
            print(f"\n[错误] 发布导出失败: {exc}")

    def cmd_drama(self) -> None:
        """将最近或已加载的小说转成短剧视频 Prompt 包"""
        if self.last_result is None:
            print("没有可转换的小说。请先运行 /create <主题> 或 /load <文件名>。")
            return

        print(f"\n[短剧] 正在将「{self.last_result.topic}」转换为短剧视频 Prompt 包...")
        exporter = DramaExporter()
        try:
            llm = create_llm(self.settings, temperature=0.3)
            project = DramaAdapter(llm).adapt_result(self.last_result)
            output_dir = exporter.export(project)
            print(f"\n短剧 Prompt 包已生成：{output_dir}")
            print(f"共 {project.episode_count} 集，{project.total_shots} 个镜头")
        except DramaAdapterError as exc:
            failure_dir = exporter.export_failure(
                source_title=self.last_result.topic,
                raw_output=exc.raw_output,
                error=str(exc),
            )
            print(f"\n[错误] 短剧 Prompt 包生成失败: {exc}")
            print(f"原始输出和错误信息已保存：{failure_dir}")
            print(f"  raw_output: {failure_dir / 'raw_output.txt'}")
            print(f"  error: {failure_dir / 'error.txt'}")
        except Exception as exc:
            print(f"\n[错误] 短剧 Prompt 包生成失败: {exc}")

    def cmd_drama_video(self, limit_arg: str | None = None) -> None:
        """将最近或已加载的小说转成短剧 Prompt 包，并提交百炼视频生成任务。"""
        if self.last_result is None:
            print("没有可转换的视频源小说。请先运行 /create <主题> 或 /load <文件名>。")
            return

        shot_limit = self._parse_drama_video_limit(limit_arg)
        print(f"\n[短剧视频] 正在将「{self.last_result.topic}」转换为短剧视频任务...")
        print(f"[短剧视频] 本次最多提交 {shot_limit} 个镜头，避免一次性消耗过多额度。")

        exporter = DramaExporter()
        try:
            llm = create_llm(self.settings, temperature=0.3)
            project = DramaAdapter(llm).adapt_result(self.last_result)
            output_dir = exporter.export(project)
            provider = create_video_provider()
            store = VideoJobStore(output_dir / "video_jobs.jsonl")

            shots = [shot for episode in project.episodes for shot in episode.shots]
            submitted = []
            for shot in shots[:shot_limit]:
                job = provider.submit_shot(shot)
                store.append(job)
                submitted.append(job)
                print(f"  - {shot.id}: {job.provider_job_id} ({job.status})")

            print(f"\n已提交 {len(submitted)} 个视频生成任务。")
            print(f"短剧 Prompt 包：{output_dir}")
            print(f"任务记录：{output_dir / 'video_jobs.jsonl'}")
            print("后续可根据 provider_job_id 查询百炼任务状态并下载视频。")
        except DramaAdapterError as exc:
            failure_dir = exporter.export_failure(
                source_title=self.last_result.topic,
                raw_output=exc.raw_output,
                error=str(exc),
            )
            print(f"\n[错误] 短剧视频任务生成失败: {exc}")
            print(f"原始输出和错误信息已保存：{failure_dir}")
        except DramaVideoError as exc:
            print(f"\n[错误] 百炼视频任务提交失败: {exc}")
        except Exception as exc:
            print(f"\n[错误] 短剧视频任务生成失败: {exc}")

    @staticmethod
    def _parse_drama_video_limit(limit_arg: str | None) -> int:
        if not limit_arg:
            return 1
        try:
            limit = int(limit_arg.strip())
        except ValueError:
            return 1
        return max(1, min(limit, 20))

    def cmd_autopublish(self) -> None:
        """通过浏览器自动化直接发布到各平台"""
        if self.last_result is None:
            print("没有可发布的创作结果。请先运行 /create <主题> 创作一篇小说。")
            return

        print("\n" + "=" * 60)
        print("  浏览器自动化发布模式")
        print("=" * 60)
        print("")
        print("首次使用会自动打开浏览器窗口，请在各平台完成登录。")
        print("登录状态会保存，后续无需重复登录。")
        print("")

        try:
            results = self.exporter.auto_publish(self.last_result)
            print(f"\n[自动发布] 结果汇总:")
            name_map = {"zhihu": "知乎盐选", "qidian": "起点中文网", "fanqie": "番茄小说"}
            for platform, success in results.items():
                status = "完成 ✓" if success else "失败 ✗"
                print(f"  {name_map.get(platform, platform)}: {status}")
        except ImportError as exc:
            print(f"\n[错误] {exc}")
            print("请运行: pip install playwright && playwright install chromium")
        except Exception as exc:
            print(f"\n[错误] 自动发布失败: {exc}")

    # ---- 全自动创作 ----

    def cmd_auto(self, topic: str | None = None) -> None:
        """Run the full autonomous pipeline once."""
        print("\n" + "=" * 60)
        print("  全自动创作发布模式")
        print("=" * 60)

        if topic:
            print(f"\n指定主题: {topic}")
        else:
            print("\nAI 将从热榜中自动选择最具爆款潜力的选题")
        print(f"质量门槛: {self.pipeline.quality_threshold}/10 | 最多重写: {self.pipeline.max_rewrites} 轮")
        print()

        try:
            result = self.pipeline.run(topic=topic, genre=self.genre)
            self._print_run_result(result)
        except LoginRequired:
            print("\n[知乎] 需要登录。正在打开发布器登录窗口...")
            publisher = self.pipeline.publisher
            if publisher.login_interactive():
                print("登录成功，请再次运行 /auto")
            else:
                print("登录失败或超时。")
        except Exception as exc:
            print(f"\n[错误] 全自动流程失败: {exc}")

    def cmd_schedule(self, action: str = "status", interval: str = "") -> None:
        """Manage the background scheduler."""
        if action == "start":
            minutes = 360
            if interval:
                num = "".join(c for c in interval if c.isdigit())
                if num:
                    val = int(num)
                    if interval.endswith("m"):
                        minutes = val
                    elif interval.endswith("h"):
                        minutes = val * 60
                    else:
                        minutes = val * 60

            self.pipeline.run_scheduled(interval_minutes=minutes)
            self._schedule_active = True
            print(f"\n[调度] 已启动 — 每 {minutes} 分钟运行一次")

        elif action == "stop":
            self.pipeline.stop_scheduled()
            self._schedule_active = False
            print("\n[调度] 已停止")

        elif action == "status":
            status = self.pipeline.schedule_status()
            if status is None:
                active = self._schedule_active
                print(f"\n[调度] {'运行中' if active else '未启动'}")
            else:
                print(f"\n[调度] {'运行中' if status.get('active') else '已停止'}")
                if status.get("interval_minutes"):
                    print(f"       间隔: {status['interval_minutes']} 分钟")
                if status.get("started_at"):
                    print(f"       启动时间: {status['started_at']}")

    def _print_run_result(self, result) -> None:
        """Pretty-print a pipeline RunResult."""
        print("\n" + "=" * 60)
        print(f"  运行结果: {result.run_id}")
        print("=" * 60)
        for stage_name, stage in result.stages.items():
            icon = {"ok": "✓", "skipped": "⊘", "failed": "✗", "fallback": "⚠"}.get(stage.status, "?")
            print(f"  {icon} {stage_name}: {stage.status} ({stage.duration_s}s)")
            for k, v in stage.extra.items():
                if k != "error":
                    print(f"      {k}: {v}")
        if result.published_url:
            print(f"\n  发布地址: {result.published_url}")
        if result.error:
            print(f"\n  错误: {result.error}")
        total_min = result.total_duration_s / 60
        print(f"\n  总耗时: {result.total_duration_s:.0f}s ({total_min:.1f}min)")

    # ---- 主循环 ----

    def run(self) -> None:
        print(HELP_TEXT)
        print(f"\n当前模式: {self.mode} | 目标题材: {self.genre or '自动识别'}")
        print(f"技能库状态: {'已加载 ' + str(len(self.skills_store.list_genres())) + ' 个题材' if not self.skills_store.is_empty else '空（需先 /scrape + /distill）'}")

        while True:
            try:
                raw = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                break

            if not raw:
                continue

            parts = raw.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if cmd in {"/exit", "exit", "quit"}:
                print("再见！")
                break
            elif cmd == "/help":
                print(HELP_TEXT)
            elif cmd == "/scrape":
                self.cmd_scrape()
            elif cmd == "/search":
                if arg:
                    self.cmd_search(arg)
                else:
                    print("用法: /search <关键词>")
            elif cmd == "/manual":
                self.cmd_manual()
            elif cmd == "/files":
                self.cmd_files()
            elif cmd == "/outputs":
                self.cmd_outputs()
            elif cmd == "/load":
                if arg:
                    self.cmd_load(arg)
                else:
                    print("用法: /load <文件名或关键词>")
            elif cmd == "/continue":
                self.cmd_continue()
            elif cmd == "/distill":
                self.cmd_distill(arg if arg else None)
            elif cmd == "/distill_file":
                if arg:
                    self.cmd_distill(arg)
                else:
                    print("用法: /distill_file <文件名>")
            elif cmd == "/skills":
                self.cmd_skills()
            elif cmd == "/skill":
                if arg:
                    self.cmd_skill_detail(arg)
                else:
                    print("用法: /skill <题材名>")
            elif cmd == "/mode":
                if arg in ("fast", "polish", "full"):
                    self.mode = arg
                    print(f"已切换到 {arg} 模式。")
                else:
                    print("可选模式: fast / polish / full")
            elif cmd == "/genre":
                self.genre = arg if arg else None
                print(f"目标题材: {self.genre or '自动识别'}")
            elif cmd == "/create":
                if arg:
                    self.cmd_create(arg)
                else:
                    print("用法: /create <主题描述>")
            elif cmd == "/fast":
                if arg:
                    prev_mode = self.mode
                    self.mode = "fast"
                    self.cmd_create(arg)
                    self.mode = prev_mode
                else:
                    print("用法: /fast <主题描述>")
            elif cmd == "/polish":
                if arg:
                    prev_mode = self.mode
                    self.mode = "polish"
                    self.cmd_create(arg)
                    self.mode = prev_mode
                else:
                    print("用法: /polish <主题描述>")
            elif cmd == "/publish":
                self.cmd_publish(arg if arg else None)
            elif cmd == "/drama":
                self.cmd_drama()
            elif cmd == "/drama_video":
                self.cmd_drama_video(arg if arg else None)
            elif cmd == "/autopublish":
                self.cmd_autopublish()
            elif cmd == "/auto":
                self.cmd_auto(arg if arg else None)
            elif cmd == "/schedule":
                sched_parts = raw.split(maxsplit=2)
                sched_action = sched_parts[1] if len(sched_parts) > 1 else "status"
                sched_arg = sched_parts[2] if len(sched_parts) > 2 else ""
                self.cmd_schedule(sched_action, sched_arg)
            elif cmd == "/stream":
                if arg:
                    self.cmd_stream(arg)
                else:
                    print("用法: /stream <主题描述>")
            else:
                print(f"未知命令: {cmd}。输入 /help 查看帮助。")


def _parse_manual_score(text: str) -> float:
    """解析手动输入的分数: '1.2万' → 12000, '5000' → 5000"""
    import re
    text = text.strip().replace(",", "")
    match = re.match(r"([\d.]+)\s*万?", text)
    if not match:
        return 0.0
    num = float(match.group(1))
    return num * 10000 if "万" in text else num


def main() -> None:
    cli = CLI()
    cli.run()


if __name__ == "__main__":
    main()
