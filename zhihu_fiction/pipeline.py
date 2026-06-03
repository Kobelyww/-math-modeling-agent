"""End-to-end autonomous fiction pipeline with scheduling."""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Protocol

from .config import APP_ROOT
from .scraper import scrape_zhihu_hot

RUN_DIR = APP_ROOT / "output" / ".pipeline"
SCHEDULE_FILE = RUN_DIR / "schedule.json"


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
    ) -> None:
        self.coordinator = coordinator
        self.reviewer = reviewer
        self.llm = llm
        self.publisher = publisher
        self._scraper = scraper
        self._selector = topic_selector
        self.quality_threshold = quality_threshold
        self.max_rewrites = max_rewrites

        self._schedule_thread: threading.Thread | None = None
        self._schedule_stop = threading.Event()

        RUN_DIR.mkdir(parents=True, exist_ok=True)

    def run(self, topic: str | None = None, genre: str | None = None,
            chapters: int = 1) -> RunResult:
        """Execute one full pipeline run. chapters>1 enables multi-chapter mode."""
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        result = RunResult(
            run_id=run_id,
            trigger="manual" if topic else "scheduled",
            topic=topic or "",
            genre=genre or "",
            timestamp=datetime.now().isoformat(),
        )
        start_time = time.time()

        # Stage 1: Scrape
        t0 = time.time()
        hot_items: list[dict] = []
        try:
            hot_items = self._scraper()
            result.stages["scrape"] = StageRecord(
                status="ok",
                duration_s=round(time.time() - t0, 1),
                extra={"items": len(hot_items)},
            )
        except Exception as exc:
            result.stages["scrape"] = StageRecord(
                status="failed",
                duration_s=round(time.time() - t0, 1),
                extra={"error": str(exc)},
            )
            result.total_duration_s = round(time.time() - start_time, 1)
            result.error = f"scrape failed: {exc}"
            self._append_run(result)
            return result

        # Stage 2: Select topic
        if not topic:
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
            except Exception as exc:
                topic = hot_items[0]["title"]
                result.topic = topic
                result.stages["select_topic"] = StageRecord(
                    status="fallback",
                    duration_s=round(time.time() - t0, 1),
                    extra={"selected": topic, "error": str(exc)},
                )
        else:
            result.stages["select_topic"] = StageRecord(
                status="ok", duration_s=0, extra={"selected": topic}
            )

        # Stage 3: Create (Coordinator + Review loop)
        t0 = time.time()
        hot_summary = self._format_hot_summary(hot_items)

        try:
            from .orchestrator import run_coordinator

            all_chapters: list[str] = []
            existing = ""
            total_chapters = chapters if (chapters and chapters > 1) else 1

            for ch_idx in range(1, total_chapters + 1):
                existing = "\n\n".join(all_chapters) if all_chapters else ""
                wf_result = run_coordinator(
                    self.llm, self.coordinator,
                    topic=topic, hot_trends=hot_summary, genre=genre,
                    chapter_index=ch_idx, total_chapters=total_chapters,
                    existing_story=existing,
                )
                all_chapters.append(wf_result.final_story)

            # Combine all chapters
            if not all_chapters:
                wf_result = run_coordinator(
                    self.llm, self.coordinator,
                    topic=topic, hot_trends=hot_summary, genre=genre,
                )
                all_chapters = [wf_result.final_story]

            # Quality gate: review + targeted retry
            review_rounds = 0
            review = {"total_score": 0.0, "full_report": ""}

            for round_num in range(self.max_rewrites + 1):
                review = self.reviewer.review(wf_result.final_story, topic)
                score = review["total_score"]
                review_rounds += 1

                if score >= self.quality_threshold:
                    break  # 达标，通过

                if round_num < self.max_rewrites:
                    # 不达标：只重写 draft + polish，不重新跑全流程
                    feedback = (
                        f"【评审分数】{score:.1f}/10 (门槛 {self.quality_threshold})\n\n"
                        f"【评审意见】\n{review['full_report']}\n\n"
                        f"请根据评审意见针对性修改小说。"
                    )
                    wf_result = run_coordinator(
                        self.llm, self.coordinator,
                        topic=topic, hot_trends=hot_summary, genre=genre,
                        revision_feedback=feedback,
                        chapter_index=ch_idx, total_chapters=total_chapters,
                        existing_story=existing,
                    )

            result.stages["create"] = StageRecord(
                status="ok",
                duration_s=round(time.time() - t0, 1),
                extra={"words": len(wf_result.final_story)},
            )
            result.stages["review"] = StageRecord(
                status="ok",
                duration_s=0,
                extra={"score": review["total_score"], "rounds": review_rounds},
            )

            # Save story to output directory (all chapters)
            full_story = "\n\n".join(all_chapters)
            story_path = self._save_story(
                run_id=run_id, topic=topic, genre=result.genre,
                story=full_story, synthesis=wf_result.synthesis,
            )
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
                title=wf_result.topic,
                content=wf_result.final_story,
                tags=[],
                genre=wf_result.genre,
            )
            result.stages["publish"] = StageRecord(
                status="ok" if pub_result.get("success") else "failed",
                duration_s=round(time.time() - t0, 1),
                extra={"url": pub_result.get("url", ""), "message": pub_result.get("message", "")},
            )
            result.published_url = pub_result.get("url", "")
        except Exception as exc:
            result.stages["publish"] = StageRecord(
                status="failed",
                duration_s=round(time.time() - t0, 1),
                extra={"error": str(exc)},
            )

        result.total_duration_s = round(time.time() - start_time, 1)
        self._append_run(result)
        return result

    def run_scheduled(self, interval_minutes: int = 360) -> threading.Event:
        """Start background scheduled runs."""
        self._schedule_stop.clear()

        def _loop():
            while not self._schedule_stop.is_set():
                try:
                    self.run(topic=None)
                except Exception as exc:
                    print(f"[pipeline] scheduled run failed: {exc}")

                deadline = time.time() + interval_minutes * 60
                while time.time() < deadline and not self._schedule_stop.is_set():
                    time.sleep(10)

        self._schedule_thread = threading.Thread(target=_loop, daemon=True)
        self._schedule_thread.start()

        SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
        SCHEDULE_FILE.write_text(json.dumps({
            "active": True,
            "interval_minutes": interval_minutes,
            "started_at": datetime.now().isoformat(),
        }, ensure_ascii=False, indent=2))

        return self._schedule_stop

    def stop_scheduled(self) -> None:
        """Stop the background schedule."""
        self._schedule_stop.set()
        if SCHEDULE_FILE.exists():
            data = json.loads(SCHEDULE_FILE.read_text())
            data["active"] = False
            data["stopped_at"] = datetime.now().isoformat()
            SCHEDULE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def schedule_status(self) -> dict | None:
        """Get current schedule status."""
        if not SCHEDULE_FILE.exists():
            return None
        return json.loads(SCHEDULE_FILE.read_text())

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
                         chapter_count: int) -> RunResult:
        """Continue an existing story with one more chapter. Returns quickly (no scrape)."""
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        result = RunResult(run_id=run_id, trigger="manual", topic=topic, genre=genre,
                           timestamp=datetime.now().isoformat())
        start = time.time()
        from .orchestrator import run_coordinator
        wf_result = run_coordinator(
            self.llm, self.coordinator,
            topic=topic, genre=genre,
            chapter_index=chapter_count + 1, total_chapters=0,
            existing_story=existing_story,
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
        runs_file = RUN_DIR / "runs.jsonl"
        try:
            with open(runs_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(result.to_json(), ensure_ascii=False) + "\n")
        except Exception:
            pass