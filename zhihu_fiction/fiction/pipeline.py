"""End-to-end autonomous fiction pipeline with scheduling."""
from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from zhihu_fiction.core.config import APP_ROOT
from zhihu_fiction.fiction.scraper import scrape_zhihu_hot
from zhihu_fiction.ip_memory.repository import IPMemoryRepository
from zhihu_fiction.storage.pipeline_storage import PipelineStorage

RUN_DIR = APP_ROOT / "output" / ".pipeline"
SCHEDULE_FILE = RUN_DIR / "schedule.json"
CHECKPOINT_DIR = RUN_DIR / "checkpoints"
logger = logging.getLogger(__name__)


# ============================================================
# Protocols
# ============================================================

class ScraperProtocol(Protocol):
    def __call__(self, limit: int = 50) -> list[dict]: ...


class TopicSelectorProtocol(Protocol):
    def __call__(self, hot_items: list[dict], llm) -> dict: ...


class PublisherProtocol(Protocol):
    def publish(self, title: str, content: str, tags: list[str], genre: str) -> dict: ...


# ============================================================
# Default topic selector
# ============================================================

TOPIC_SELECTOR_PROMPT = """你是知乎小说选题决策专家。从以下热榜话题中选出最适合创作爆款小说的1个话题。

热榜列表：
{hot_list}

请选出最具爆款潜力的1个话题，按以下格式输出：
选题：<话题标题>
题材：<题材类型，如悬疑/言情/职场/科幻等>
理由：<一句话说明为什么选这个（30字内）>"""


def select_topic(hot_items: list[dict], llm) -> dict:
    """Analyze hot list and select the best topic for fiction creation."""
    hot_list_text = "\n".join(
        f"{i + 1}. [{item.get('hot_score', 0):.0f}] {item['title']}"
        for i, item in enumerate(hot_items[:20])
    )
    prompt = TOPIC_SELECTOR_PROMPT.format(hot_list=hot_list_text)
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "".join(
            str(item.get("text", item)) if isinstance(item, dict) else str(item)
            for item in content
        )

    topic_match = re.search(r"选题[：:]\s*(.+?)(?:\n|$)", content)
    genre_match = re.search(r"题材[：:]\s*(.+?)(?:\n|$)", content)

    topic = topic_match.group(1).strip() if topic_match else hot_items[0]["title"]
    genre = genre_match.group(1).strip() if genre_match else "未指定"

    return {"topic": topic, "genre": genre, "raw_analysis": content}


# ============================================================
# Stage result and run result
# ============================================================

@dataclass
class StageRecord:
    status: str  # ok | skipped | failed | fallback
    duration_s: float
    extra: dict = field(default_factory=dict)


@dataclass
class RunResult:
    run_id: str
    trigger: str  # scheduled | manual
    topic: str
    genre: str
    stages: dict[str, StageRecord] = field(default_factory=dict)
    total_duration_s: float = 0.0
    published_url: str = ""
    error: str = ""
    timestamp: str = ""

    def to_json(self) -> dict:
        return {
            "run_id": self.run_id,
            "trigger": self.trigger,
            "topic": self.topic,
            "genre": self.genre,
            "stages": {
                name: {"status": s.status, "duration_s": s.duration_s, **s.extra}
                for name, s in self.stages.items()
            },
            "total_duration_s": self.total_duration_s,
            "published_url": self.published_url,
            "error": self.error,
            "timestamp": self.timestamp,
        }


# ============================================================
# Content Moderation
# ============================================================

MODERATE_PROMPT = """你是内容安全审查专家。检查以下文本是否包含违规内容：

违规类型：
1. 政治敏感 — 涉及具体政治事件、人物、体制攻击
2. 暴力血腥 — 过度描写暴力细节
3. 色情低俗 — 露骨性描写
4. 违法引导 — 教唆犯罪、诈骗
5. 平台违规 — 造谣、人身攻击、引战

如果文本安全，直接原样返回。
如果发现问题，请输出安全润色后的版本：保留核心创意和故事框架，但用中性、安全的表述替换违规部分。
只输出润色后的文本，不要解释修改了什么。"""


def moderate_content(llm, text: str) -> str:
    """Screen and polish text for content safety. Returns safe version."""
    if not text or len(text) < 5:
        return text
    response = llm.invoke([
        SystemMessage(content=MODERATE_PROMPT),
        HumanMessage(content=f"请审查以下文本：\n\n{text}"),
    ])
    from zhihu_fiction.core.base import normalize_content
    return normalize_content(response.content)


# ============================================================
# Pipeline
# ============================================================

class Pipeline:
    """Content-type agnostic autonomous fiction pipeline."""

    def __init__(
        self,
        coordinator,
        reviewer,
        llm,
        publisher,
        scraper=scrape_zhihu_hot,
        topic_selector=select_topic,
        quality_threshold: float = 6.0,
        max_rewrites: int = 2,
        skills_store=None,
        ip_memory_repo: IPMemoryRepository | None = None,
    ) -> None:
        self.coordinator = coordinator
        self.reviewer = reviewer
        self.llm = llm
        self.publisher = publisher
        self._scraper = scraper
        self._selector = topic_selector
        self.quality_threshold = quality_threshold
        self.max_rewrites = max_rewrites
        self._skills_store = skills_store

        self._schedule_thread: threading.Thread | None = None
        self._schedule_stop = threading.Event()
        self._storage = PipelineStorage(RUN_DIR)
        self._ip_memory_repo = ip_memory_repo or IPMemoryRepository(APP_ROOT / "data" / "ip_memory")

        self._storage.ensure()

    def run(self, topic: str | None = None, genre: str | None = None,
            chapters: int = 1, stream_callback: Callable | None = None,
            on_progress: Callable | None = None,
            _resume_state: dict | None = None) -> RunResult:
        """Execute one full pipeline run. chapters>1 enables multi-chapter mode.

        Args:
            stream_callback: SSE event callback forwarded to run_coordinator.
            on_progress: stage progress callback(stage, status, message, progress, **extra).
            _resume_state: internal — resume from a previously saved checkpoint.
        """
        checkpoint_run_id = _resume_state.get("run_id") if _resume_state else None
        run_id = checkpoint_run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        result = RunResult(
            run_id=run_id,
            trigger="manual" if topic else "scheduled",
            topic=topic or "",
            genre=genre or "",
            timestamp=datetime.now().isoformat(),
        )
        start_time = time.time()

        emit = on_progress or (lambda *a, **kw: None)

        # Stage 1: Scrape
        emit("scrape", "running", "正在抓取知乎热榜...", 10)
        t0 = time.time()
        hot_items: list[dict] = []
        try:
            hot_items = self._scraper()
            result.stages["scrape"] = StageRecord(
                status="ok",
                duration_s=round(time.time() - t0, 1),
                extra={"items": len(hot_items)},
            )
            emit("scrape", "completed", f"抓取到 {len(hot_items)} 条热榜", 20, items=len(hot_items))
        except Exception as exc:
            result.stages["scrape"] = StageRecord(
                status="failed",
                duration_s=round(time.time() - t0, 1),
                extra={"error": str(exc)},
            )
            emit("scrape", "failed", str(exc), -1)
            result.total_duration_s = round(time.time() - start_time, 1)
            result.error = f"scrape failed: {exc}"
            self._append_run(result)
            return result

        # Stage 2: Select topic
        if not topic:
            emit("select_topic", "running", "正在分析选题...", 25)
            t0 = time.time()
            try:
                selection = self._selector(hot_items, self.llm)
                topic = selection["topic"]
                genre = selection.get("genre", genre)
                result.topic = topic
                result.genre = genre or "未指定"
                result.stages["select_topic"] = StageRecord(
                    status="ok",
                    duration_s=round(time.time() - t0, 1),
                    extra={"selected": topic, "genre": genre or ""},
                )
                emit("select_topic", "completed", f"选定: {topic}", 30,
                     selected=topic, genre=genre or "")
            except Exception as exc:
                topic = hot_items[0]["title"]
                result.topic = topic
                result.stages["select_topic"] = StageRecord(
                    status="fallback",
                    duration_s=round(time.time() - t0, 1),
                    extra={"selected": topic, "error": str(exc)},
                )
                emit("select_topic", "failed", str(exc), -1)
        else:
            result.stages["select_topic"] = StageRecord(
                status="ok", duration_s=0, extra={"selected": topic}
            )

        # Stage 2.5: Moderate topic (screen for sensitive content)
        t0_mod = time.time()
        original_topic = topic
        topic = moderate_content(self.llm, topic)
        if topic != original_topic:
            logger = __import__("logging").getLogger(__name__)
            logger.info("Topic moderated: %s → %s", original_topic[:50], topic[:50])
        result.stages["moderate"] = StageRecord(
            status="ok",
            duration_s=round(time.time() - t0_mod, 1),
            extra={"topic_moderated": topic != original_topic},
        )

        # Checkpoint: topic selected, ready for creation
        self._save_checkpoint(run_id, topic=topic, genre=result.genre,
                              chapters=total_chapters if 'total_chapters' in dir() else 1,
                              stage="pre_create", hot_items=hot_items)

        # Stage 3: Create (Coordinator + Review loop)
        emit("create", "running", "正在创作 (DeepAgent 协调中)...", 35)
        t0 = time.time()
        hot_summary = self._format_hot_summary(hot_items)

        try:
            from zhihu_fiction.fiction.orchestrator import run_coordinator

            all_chapters: list[str] = []
            ip_memory_warnings: list[str] = []
            existing = ""
            total_chapters = chapters if (chapters and chapters > 1) else 1

            for ch_idx in range(1, total_chapters + 1):
                existing = "\n\n".join(all_chapters) if all_chapters else ""
                _, memory_context = self._load_ip_memory_context(run_id)
                wf_result = run_coordinator(
                    self.llm, self.coordinator,
                    topic=topic, hot_trends=hot_summary, genre=genre,
                    chapter_index=ch_idx, total_chapters=total_chapters,
                    existing_story=existing,
                    memory_context=memory_context,
                    stream_callback=stream_callback,
                )
                all_chapters.append(wf_result.final_story)
                try:
                    self._extract_ip_memory_snapshot(
                        run_id=run_id,
                        topic=topic,
                        genre=result.genre,
                        full_story="\n\n".join(all_chapters),
                        story_ref=f"{run_id}:chapter:{ch_idx}",
                        patch_note=f"pipeline chapter {ch_idx} extraction",
                    )
                except Exception as exc:
                    warning = f"chapter {ch_idx}: {exc}"
                    ip_memory_warnings.append(warning)
                    logger.warning(
                        "failed to extract IP memory after chapter %s for %s: %s",
                        ch_idx,
                        run_id,
                        exc,
                    )

            # Combine all chapters
            if not all_chapters:
                _, memory_context = self._load_ip_memory_context(run_id)
                wf_result = run_coordinator(
                    self.llm, self.coordinator,
                    topic=topic, hot_trends=hot_summary, genre=genre,
                    memory_context=memory_context,
                    stream_callback=stream_callback,
                )
                all_chapters = [wf_result.final_story]

            full_story = "\n\n".join(all_chapters)

            # Quality gate: review full combined story
            review_rounds = 0
            review = {"total_score": 0.0, "full_report": ""}

            for round_num in range(self.max_rewrites + 1):
                review = self.reviewer.review(full_story, topic)
                score = review["total_score"]
                review_rounds += 1

                if score >= self.quality_threshold:
                    break

                if round_num < self.max_rewrites:
                    _, memory_context = self._load_ip_memory_context(run_id)
                    feedback = (
                        f"【评审分数】{score:.1f}/10 (门槛 {self.quality_threshold})\n\n"
                        f"【评审意见】\n{review['full_report']}\n\n"
                        f"请根据评审意见针对性修改小说。"
                    )
                    wf_result = run_coordinator(
                        self.llm, self.coordinator,
                        topic=topic, hot_trends=hot_summary, genre=genre,
                        revision_feedback=feedback,
                        total_chapters=total_chapters,
                        existing_story="" if total_chapters <= 1 else full_story,
                        memory_context=memory_context,
                        stream_callback=stream_callback,
                    )
                    full_story = wf_result.final_story

            result.stages["create"] = StageRecord(
                status="ok",
                duration_s=round(time.time() - t0, 1),
                extra={
                    "words": len(full_story),
                    **({"ip_memory_warnings": ip_memory_warnings} if ip_memory_warnings else {}),
                },
            )
            result.stages["review"] = StageRecord(
                status="ok",
                duration_s=0,
                extra={"score": review["total_score"], "rounds": review_rounds,
                       "chapters": total_chapters},
            )
            emit("create", "completed", f"创作完成，{len(full_story)} 字", 80, words=len(full_story))

            story_path = self._save_story(
                run_id=run_id, topic=topic, genre=result.genre,
                story=full_story, synthesis=wf_result.synthesis,
            )
            self._extract_and_save_ip_memory(
                result=result,
                topic=topic,
                genre=result.genre,
                full_story=full_story,
                story_path=story_path,
            )
            # Checkpoint: story created, ready for publish
            self._save_checkpoint(run_id, topic=topic, genre=result.genre,
                                  chapters=total_chapters, stage="pre_publish",
                                  story_path=str(story_path),
                                  score=review["total_score"])
            result.published_url = str(story_path)

            # Skip publish if quality too low
            if review["total_score"] < self.quality_threshold:
                result.stages["publish"] = StageRecord(
                    status="skipped",
                    duration_s=0,
                    extra={"reason": f"score {review['total_score']:.1f} < threshold {self.quality_threshold}"},
                )
                result.total_duration_s = round(time.time() - start_time, 1)
                self._append_run(result)
                return result

        except Exception as exc:
            emit("create", "failed", str(exc), -1)
            result.stages["create"] = StageRecord(
                status="failed",
                duration_s=round(time.time() - t0, 1),
                extra={"error": str(exc)},
            )
            result.total_duration_s = round(time.time() - start_time, 1)
            result.error = f"create failed: {exc}"
            self._append_run(result)
            return result

        # Stage 4: Publish
        t0 = time.time()
        try:
            pub_result = self.publisher.publish(
                title=topic,
                content=full_story,
                tags=[],
                genre=result.genre,
            )
            result.stages["publish"] = StageRecord(
                status="ok" if pub_result.get("success") else "failed",
                duration_s=round(time.time() - t0, 1),
                extra={"url": pub_result.get("url", ""), "message": pub_result.get("message", "")},
            )
            result.published_url = pub_result.get("url", "")

            # Closed-loop learning: feed successful story back into skill cards
            if pub_result.get("success") and self._skills_store is not None:
                try:
                    from zhihu_fiction.core.config import load_settings
                    from zhihu_fiction.fiction.distiller import Distiller
                    d = Distiller(load_settings())
                    d.learn_from_story(
                        title=topic, genre=result.genre,
                        story_text=full_story, skills_store=self._skills_store,
                    )
                    result.stages["learn"] = StageRecord(status="ok", duration_s=0,
                                                         extra={"genre": result.genre})
                except Exception as exc:
                    result.stages["learn"] = StageRecord(status="failed", duration_s=0,
                                                         extra={"error": str(exc)})
        except Exception as exc:
            result.stages["publish"] = StageRecord(
                status="failed",
                duration_s=round(time.time() - t0, 1),
                extra={"error": str(exc)},
            )

        result.total_duration_s = round(time.time() - start_time, 1)
        self._append_run(result)
        self._clear_checkpoint(run_id)
        return result

    def _load_ip_memory_context(self, run_id: str):
        try:
            from zhihu_fiction.ip_memory.rendering import render_memory_context

            prior_memory = self._ip_memory_repo.load(run_id)
            if prior_memory is None:
                return None, ""
            return prior_memory, render_memory_context(prior_memory)
        except Exception as exc:
            logger.warning("failed to load IP memory for %s: %s", run_id, exc)
            return None, ""

    def _extract_and_save_ip_memory(
        self,
        *,
        result: RunResult,
        topic: str,
        genre: str,
        full_story: str,
        story_path: Path,
    ) -> None:
        t0 = time.time()
        try:
            saved = self._extract_ip_memory_snapshot(
                run_id=result.run_id,
                topic=topic,
                genre=genre,
                full_story=full_story,
                story_ref=str(story_path),
                patch_note=f"pipeline_extract:{story_path}",
            )
            result.stages["ip_memory"] = StageRecord(
                status="ok",
                duration_s=round(time.time() - t0, 1),
                extra={
                    "project_id": result.run_id,
                    "story_ref": str(story_path),
                    "snapshot_hash": self._ip_memory_repo.snapshot_hash(saved),
                    "characters": len(saved.characters),
                    "world_facts": len(saved.world_facts),
                    "foreshadowing": len(saved.foreshadowing),
                    "asset_bindings": len(saved.asset_bindings),
                },
            )
        except Exception as exc:
            result.stages["ip_memory"] = StageRecord(
                status="failed",
                duration_s=round(time.time() - t0, 1),
                extra={"error": str(exc)},
            )

    def _extract_ip_memory_snapshot(
        self,
        *,
        run_id: str,
        topic: str,
        genre: str,
        full_story: str,
        story_ref: str,
        patch_note: str,
    ):
        from zhihu_fiction.ip_memory.extraction import extract_ip_memory_from_story

        prior_memory = self._ip_memory_repo.load(run_id)
        memory = extract_ip_memory_from_story(
            project_id=run_id,
            title=topic,
            genre=genre,
            story_text=full_story,
            story_ref=story_ref,
            prior=prior_memory,
        )
        return self._ip_memory_repo.save(memory, patch_note=patch_note)

    def run_scheduled(self, interval_minutes: int = 360) -> threading.Event:
        """Start background scheduled runs."""
        self._schedule_stop.clear()

        def _loop():
            while not self._schedule_stop.is_set():
                try:
                    self.run(topic=None)
                except Exception as exc:
                    logger.exception("scheduled run failed: %s", exc)

                deadline = time.time() + interval_minutes * 60
                while time.time() < deadline and not self._schedule_stop.is_set():
                    time.sleep(10)

        self._schedule_thread = threading.Thread(target=_loop, daemon=True)
        self._schedule_thread.start()

        self._storage.save_schedule({
            "active": True,
            "interval_minutes": interval_minutes,
            "started_at": datetime.now().isoformat(),
        })

        return self._schedule_stop

    def stop_scheduled(self) -> None:
        """Stop the background schedule."""
        self._schedule_stop.set()
        if SCHEDULE_FILE.exists():
            self._storage.update_schedule({
                "active": False,
                "stopped_at": datetime.now().isoformat(),
            })

    def schedule_status(self) -> dict | None:
        """Get current schedule status."""
        return self._storage.read_schedule()

    def _format_hot_summary(self, hot_items: list[dict]) -> str:
        lines: list[str] = []
        for i, item in enumerate(hot_items[:15]):
            score = item.get("hot_score", 0)
            title = item.get("title", "")
            excerpt = item.get("excerpt", "")[:80]
            lines.append(f"{i + 1}. [{score:.0f}] {title}")
            if excerpt:
                lines.append(f"   摘要: {excerpt}")
        return "\n".join(lines)

    def continue_chapter(self, topic: str, genre: str, existing_story: str,
                         chapter_count: int, stream_callback: Callable | None = None) -> RunResult:
        """Continue an existing story with one more chapter. Returns quickly (no scrape)."""
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        result = RunResult(run_id=run_id, trigger="manual", topic=topic, genre=genre,
                           timestamp=datetime.now().isoformat())
        start = time.time()
        from zhihu_fiction.fiction.orchestrator import run_coordinator
        wf_result = run_coordinator(
            self.llm, self.coordinator,
            topic=topic, genre=genre,
            chapter_index=chapter_count + 1, total_chapters=0,
            existing_story=existing_story,
            stream_callback=stream_callback,
        )
        new_chapter = wf_result.final_story
        full_story = existing_story + "\n\n" + new_chapter
        story_path = self._save_story(run_id=run_id, topic=topic, genre=genre,
                                       story=full_story, synthesis=wf_result.synthesis)
        result.stages["create"] = StageRecord(status="ok", duration_s=round(time.time()-start, 1),
                                               extra={"words": len(new_chapter)})
        result.published_url = str(story_path)
        result.total_duration_s = round(time.time() - start, 1)
        self._append_run(result)
        return result

    def _save_story(self, run_id: str, topic: str, genre: str, story: str, synthesis: str) -> Path:
        """Save the generated story to output directory."""
        safe_topic = "".join(c for c in topic if c.isalnum() or c in ("-", "_", " "))[:40]
        safe_topic = safe_topic.strip().replace(" ", "_")
        story_dir = APP_ROOT / "output" / f"{safe_topic}_{run_id}"
        story_dir.mkdir(parents=True, exist_ok=True)

        story_file = story_dir / "小说正文.md"
        story_file.write_text(
            f"# {topic}\n\n"
            f"> 题材：{genre}\n\n"
            f"{story}\n\n"
            f"---\n\n"
            f"# 发布方案\n\n"
            f"{synthesis}",
            encoding="utf-8",
        )
        return story_file

    def _append_run(self, result: RunResult) -> None:
        try:
            self._storage.append_run(result)
        except OSError:
            logger.exception("failed to append pipeline run: %s", result.run_id)

    # ---- checkpoint / resume ----

    def _checkpoint_path(self, run_id: str) -> Path:
        return self._storage.checkpoint_path(run_id)

    def _save_checkpoint(self, run_id: str, **state) -> None:
        """Persist pipeline state so a crashed run can resume."""
        try:
            self._storage.save_checkpoint(run_id, **state)
        except OSError:
            logger.exception("failed to save pipeline checkpoint: %s", run_id)

    def _load_checkpoint(self, run_id: str) -> dict | None:
        """Load a previous checkpoint, or None if it doesn't exist."""
        return self._storage.load_checkpoint(run_id)

    def _clear_checkpoint(self, run_id: str) -> None:
        """Remove checkpoint after successful completion."""
        try:
            self._storage.clear_checkpoint(run_id)
        except OSError:
            logger.exception("failed to clear pipeline checkpoint: %s", run_id)

    def list_checkpoints(self) -> list[dict]:
        """List all saved checkpoints."""
        return self._storage.list_checkpoints()

    def resume_checkpoint(self, run_id: str) -> RunResult | None:
        """Resume a run from a saved checkpoint."""
        state = self._load_checkpoint(run_id)
        if state is None:
            return None
        topic = state.get("topic", "")
        genre = state.get("genre", "")
        print(f"[resume] Restoring checkpoint {run_id}: topic={topic[:40]}, genre={genre}")
        return self.run(topic=topic, genre=genre,
                        chapters=state.get("chapters", 1),
                        _resume_state=state)
