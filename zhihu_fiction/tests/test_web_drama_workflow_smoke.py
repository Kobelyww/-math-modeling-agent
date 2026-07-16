"""Fast API smoke tests for the project short-drama workflow."""
from __future__ import annotations

from fastapi.testclient import TestClient

import zhihu_fiction.server as server_mod
from zhihu_fiction.app.dependencies import AppDependencies
from zhihu_fiction.app.factory import create_app
from zhihu_fiction.app.services import drama_video_runtime
from zhihu_fiction.app.state import AppState
from zhihu_fiction.ip_memory.repository import IPMemoryRepository
from zhihu_fiction.ip_memory.trace import AgentTraceStore
from zhihu_fiction.workspace.models import Project, Story
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def _valid_stage_content(stage: str) -> str:
    samples = {
        "script": """角色：林晚。
地点：运城。
限制：真相不能提前揭露。
风格：冷暖对比。
场次：第一集开场，林晚在医院走廊发现被涂改的检测报告。
对白：林晚：这份报告不该是空白，我要知道昨晚到底发生了什么。
冲突：家人劝她停止调查，污染线索却指向更大的利益链。
钩子：孩子咳出粉色泡沫。
悬念：报告最后一页出现被划掉的企业名称。""",
        "style": """风格：冷暖对比。
视觉：低饱和城市夜景。
镜头：手持纪实。
灯光：医院走廊使用冷白灯，家庭场景保留微弱暖光。
一致性：林晚始终保持白衬衫、黑色长发、疲惫但警觉的气质。
负面约束：避免夸张滤镜，避免喜剧化表演，避免过度赛博化。""",
        "plot": """集数：三集短剧结构。
第一集：异味爆发，小满送医，林晚发现官方通报缺少关键信息。
第二集：检测报告被涂改，家人因工作和房贷阻止调查。
第三集：林晚提交证据，企业被限产整改，家人关系留下裂痕。
反转：真正问题不是一次偷排，而是多年分期建设无人验收。
情绪：恐惧、愤怒、两难、克制的希望。
爽点：用证据链逼出调查组进驻。""",
        "character_refs": """角色：林晚。
外貌：32岁，黑色长发，白衬衫，眼下有疲惫感但目光警觉。
服装：医院阶段穿浅色衬衫，调查阶段加深灰外套。
气质：冷静、压抑、专业，面对家人时有明显挣扎。
参考图Prompt：竖屏短剧女主，现实主义环境律师，黑色长发，白衬衫，低饱和城市医院灯光。
一致性Prompt：保持同一面部轮廓、发型、服装色系和疲惫但坚定的表情。""",
        "storyboard": """1. 场景：医院走廊 夜晚
人物：林晚、小满
动作：林晚抱着咳嗽的小满冲向抢救室，护士从画面边缘快速经过。
对白：林晚：医生，她喘不上气了！
镜头：手持中近景快速推进，制造压迫感。
时长：6秒
视频生成Prompt：竖屏短剧，医院走廊，冷白灯，焦急奔跑，现实主义纪实风格""",
    }
    return samples[stage]


def test_project_workspace_guides_deepagent_stage_loop_from_story_to_video(monkeypatch, tmp_path):
    story_rel_path = "output/smoke_story/小说正文.md"
    story_file = tmp_path / story_rel_path
    story_file.parent.mkdir(parents=True)
    story_file.write_text(
        "# 山西异味事件短剧\n\n> 题材：现实悬疑\n\n女主被异味熏醒后追查真相。",
        encoding="utf-8",
    )
    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path / "output")

    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_smoke", title="山西异味事件短剧"))
    repo.save_story(Story(
        id="story_smoke",
        project_id="project_smoke",
        title="小说正文",
        body_path=story_rel_path,
    ))
    dependencies = AppDependencies(
        workspace_repo=repo,
        ip_memory_repo=IPMemoryRepository(tmp_path / "ip_memory"),
        agent_trace_store=AgentTraceStore(tmp_path / "agent_traces"),
    )
    state = AppState()

    counters = {"deepagent": 0, "video": 0}

    def deterministic_id(prefix: str) -> str:
        counters[prefix] += 1
        return f"{prefix}_smoke_{counters[prefix]}"

    def fake_generate_stage(_dependencies, story_path, stage, stage_drafts):
        return {
            "stage": stage,
            "label": stage,
            "model": "deepseek-v4-pro",
            "agent": "deepagent",
            "content": _valid_stage_content(stage),
            "events": [{"type": "tool_call", "name": f"draft_{stage}"}],
        }

    def fake_revise_stage(
        _dependencies,
        story_path,
        stage,
        stage_drafts,
        current_draft="",
        human_feedback="",
    ):
        return {
            "stage": stage,
            "label": stage,
            "model": "deepseek-v4-pro",
            "agent": "deepagent",
            "content": f"{current_draft} | human feedback: {human_feedback}",
            "events": [{"type": "human_feedback", "content": human_feedback}],
        }

    monkeypatch.setattr(drama_video_runtime, "new_video_run_id", deterministic_id)
    monkeypatch.setattr(drama_video_runtime, "generate_video_stage_draft", fake_generate_stage)
    monkeypatch.setattr(drama_video_runtime, "run_video_stage_deepagent", fake_revise_stage)

    client = TestClient(create_app(dependencies=dependencies, state=state))

    started = client.post(
        "/api/drama-video/deepagent/loop",
        json={
            "story_path": story_rel_path,
            "project_id": "project_smoke",
            "shot_limit": 1,
        },
    )
    assert started.status_code == 200
    run_id = started.json()["run_id"]
    assert started.json()["status"] == "awaiting_confirmation"
    assert started.json()["pending_stage"] == "script"

    workspace = client.get("/api/projects/project_smoke").json()
    assert workspace["next_action"] == {
        "kind": "confirm_stage",
        "label": "确认 script 阶段",
        "target_id": run_id,
        "stage": "script",
    }

    confirmed_script = client.post(
        "/api/drama-video/deepagent/confirm",
        json={
            "run_id": run_id,
            "stage": "script",
            "content": _valid_stage_content("script"),
        },
    )
    assert confirmed_script.status_code == 200
    assert confirmed_script.json()["status"] == "ready_for_next_stage"
    assert confirmed_script.json()["next_stage"] == "style"

    workspace = client.get("/api/projects/project_smoke").json()
    assert workspace["next_action"] == {
        "kind": "generate_stage",
        "label": "生成 style 阶段",
        "target_id": run_id,
        "stage": "style",
    }

    advanced_style = client.post("/api/drama-video/deepagent/advance", json={"run_id": run_id})
    assert advanced_style.status_code == 200
    assert advanced_style.json()["stage"] == "style"

    revised_style = client.post(
        "/api/drama-video/deepagent/revise",
        json={
            "run_id": run_id,
            "stage": "style",
            "current_draft": advanced_style.json()["content"],
            "feedback": "增强压迫感和夜景氛围",
        },
    )
    assert revised_style.status_code == 200
    assert "增强压迫感和夜景氛围" in revised_style.json()["content"]

    confirmed_style = client.post(
        "/api/drama-video/deepagent/confirm",
        json={
            "run_id": run_id,
            "stage": "style",
            "content": revised_style.json()["content"],
        },
    )
    assert confirmed_style.status_code == 200

    for stage in ["plot", "character_refs", "storyboard"]:
        advanced = client.post("/api/drama-video/deepagent/advance", json={"run_id": run_id})
        assert advanced.status_code == 200
        assert advanced.json()["stage"] == stage
        confirmed = client.post(
            "/api/drama-video/deepagent/confirm",
            json={
                "run_id": run_id,
                "stage": stage,
                "content": advanced.json()["content"],
            },
        )
        assert confirmed.status_code == 200

    final_confirmation = confirmed.json()
    assert final_confirmation["status"] == "video_started"
    assert final_confirmation["video_run_id"] == "video_smoke_1"
    assert final_confirmation["stream_url"] == "/api/drama-video/stream/video_smoke_1"

    final_workspace = client.get("/api/projects/project_smoke").json()
    session = final_workspace["drama_sessions"][0]
    assert session["id"] == run_id
    assert session["status"] == "video_started"
    assert session["confirmed_stages"] == [
        "script",
        "style",
        "plot",
        "character_refs",
        "storyboard",
    ]
    assert session["video_run_id"] == "video_smoke_1"
    assert repo.get_drama_video_run("video_smoke_1").status == "queued"

    versions = client.get(f"/api/drama-video/deepagent/{run_id}/versions").json()["versions"]
    assert [version["event"] for version in versions].count("confirmation") == 5
    assert any(
        version["event"] == "revision"
        and version["human_feedback"] == "增强压迫感和夜景氛围"
        for version in versions
    )

    trace_events = client.get(f"/api/drama-video/deepagent/{run_id}/trace").json()["events"]
    assert {event["event"] for event in trace_events} >= {
        "draft_created",
        "human_revision_requested",
        "human_confirmed",
    }
