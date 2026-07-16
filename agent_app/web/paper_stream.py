from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agent_app.config import Settings
from agent_app.deepagent.runner import CompetitionPaperRunner
from agent_app.domain.models import RunSpec, RunStatus
from agent_app.domain.serialization import to_json_dict
from agent_app.tools.competition import make_competition_tools


PaperEventHandler = Callable[[dict[str, Any]], None]


@dataclass
class PaperChatRequest:
    question: str
    data_files: list[Path] = field(default_factory=list)
    reference_files: list[Path] = field(default_factory=list)
    messages: list[dict[str, str]] = field(default_factory=list)


def build_followup_question(request: PaperChatRequest) -> str:
    history_lines: list[str] = []
    for message in request.messages[-8:]:
        role = message.get("role", "user")
        content = message.get("content", "").strip()
        if content:
            history_lines.append(f"{role}: {content}")
    if not history_lines:
        return request.question
    return (
        "请基于以下对话上下文继续完成数学建模竞赛论文任务。\n\n"
        "## 对话上下文\n"
        + "\n".join(history_lines)
        + "\n\n## 当前用户指令\n"
        + request.question
    )


class EventDrivingCoordinator:
    STAGES = (
        ("ingest_inputs", "整理输入", "ingest_inputs"),
        ("understand_problem", "理解赛题", "analyze_problem"),
        ("audit_data", "审计数据", "audit_data"),
        ("retrieve_evidence", "检索证据", "retrieve_evidence"),
        ("plan_modeling", "规划模型", "plan_model"),
        ("run_experiments", "生成实验", "run_experiment"),
        ("draft_paper", "起草论文", "draft_competition_paper"),
        ("review_and_revise", "质量评审", "review_submission"),
        ("package_submission", "打包提交", "package_submission"),
    )

    def __init__(self, run_store, emit: PaperEventHandler) -> None:
        self.run_store = run_store
        self.emit = emit
        self.tools = {tool.name: tool for tool in make_competition_tools(run_store=run_store)}

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = payload["run_id"]
        question = payload["question"]
        data_files = payload["data_files"]
        reference_files = payload["reference_files"]

        self.emit({"type": "message", "role": "assistant", "content": "已创建论文生产任务，开始整理输入。"})
        manifest = self._stage(
            "ingest_inputs",
            "整理输入",
            "ingest_inputs",
            {
                "run_id": run_id,
                "question": question,
                "data_files": data_files,
                "reference_files": reference_files,
            },
        )
        problem = self._stage("understand_problem", "理解赛题", "analyze_problem", {"run_id": run_id, "question": question})
        audit = self._stage("audit_data", "审计数据", "audit_data", {"run_id": run_id, "file_paths": data_files})
        evidence = self._stage(
            "retrieve_evidence",
            "检索证据",
            "retrieve_evidence",
            {
                "run_id": run_id,
                "query": question,
                "reference_files": reference_files,
                "top_k": 6,
                "allow_online_search": False,
            },
        )
        plan = self._stage(
            "plan_modeling",
            "规划模型",
            "plan_model",
            {
                "run_id": run_id,
                "problem_brief": problem["problem_brief"],
                "data_audit": audit["data_audit"],
                "evidence_notes": evidence["evidence_notes"],
            },
        )
        experiment = self._stage(
            "run_experiments",
            "生成实验",
            "run_experiment",
            {
                "run_id": run_id,
                "modeling_plan": plan["modeling_plan"],
                "data_files": data_files,
            },
        )
        paper = self._stage(
            "draft_paper",
            "起草论文",
            "draft_competition_paper",
            {
                "run_id": run_id,
                "problem_brief": problem["problem_brief"],
                "data_audit": audit["data_audit"],
                "modeling_plan": plan["modeling_plan"],
                "experiment_result": experiment["experiment_result"],
                "evidence_notes": evidence["evidence_notes"],
            },
        )
        review = self._stage(
            "review_and_revise",
            "质量评审",
            "review_submission",
            {
                "run_id": run_id,
                "paper_draft": paper["paper_draft"],
                "experiment_result": experiment["experiment_result"],
                "artifacts": [
                    plan["modeling_report_path"],
                    experiment["code_path"],
                    paper["paper_tex_path"],
                ],
            },
        )
        self.emit({"type": "quality_gate", "stage": "review_and_revise", **review["quality_report"]})
        if not review["quality_report"].get("passed", False):
            required_fixes = review["quality_report"].get("required_fixes", [])
            self.emit(
                {
                    "type": "revise_required",
                    "stage": "review_and_revise",
                    "required_fixes": required_fixes,
                    "review_report_path": review.get("review_report_path"),
                }
            )
            summary = review.get("review_report_path") or "质量审查未通过，需要修改后再打包。"
            self.emit({"type": "message", "role": "assistant", "content": summary})
            return {
                "messages": [{"content": summary}],
                "inputs_manifest": manifest,
                "status": "partial",
                "quality_report": review["quality_report"],
            }

        package = self._stage("package_submission", "打包提交", "package_submission", {"run_id": run_id})

        summary = package["final_synthesis_path"]
        self.emit({"type": "message", "role": "assistant", "content": f"提交包已生成：{summary}"})
        return {"messages": [{"content": summary}], "inputs_manifest": manifest}

    def _stage(self, stage: str, label: str, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.emit({"type": "stage", "stage": stage, "label": label, "status": "running"})
        self.emit({"type": "tool", "stage": stage, "name": tool_name, "status": "running"})
        result = self.tools[tool_name].invoke(payload)
        self.emit({"type": "tool", "stage": stage, "name": tool_name, "status": "completed", "result": self._preview(result)})
        self.emit({"type": "stage", "stage": stage, "label": label, "status": "completed"})
        self._emit_artifact_paths(stage, result)
        self._emit_section_paths(stage, result)
        return result

    def _emit_artifact_paths(self, stage: str, result: dict[str, Any]) -> None:
        for key, value in result.items():
            values = value if isinstance(value, list) else [value]
            for item in values:
                if isinstance(item, str) and self._looks_like_artifact_path(item):
                    path = Path(item)
                    self.emit(
                        {
                            "type": "artifact",
                            "stage": stage,
                            "name": path.name,
                            "path": item,
                            "kind": path.suffix.lstrip(".") or "file",
                        }
                    )

    def _emit_section_paths(self, stage: str, result: dict[str, Any]) -> None:
        for item in result.get("paper_section_paths", []):
            if isinstance(item, str):
                path = Path(item)
                self.emit(
                    {
                        "type": "section",
                        "stage": stage,
                        "name": path.name,
                        "status": "completed",
                        "path": item,
                    }
                )

    @staticmethod
    def _looks_like_artifact_path(value: str) -> bool:
        return bool(Path(value).suffix) or "/" in value

    @staticmethod
    def _preview(result: dict[str, Any]) -> dict[str, Any]:
        preview: dict[str, Any] = {}
        for key, value in result.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                preview[key] = value
            elif isinstance(value, list):
                preview[key] = value[:3]
            elif isinstance(value, dict):
                preview[key] = {k: value[k] for k in list(value)[:5]}
        return preview


class PaperChatStreamer:
    def __init__(
        self,
        output_root: Path | str | None = None,
        settings: Settings | None = None,
        coordinator_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.output_root = output_root
        self.settings = settings
        self.coordinator_factory = coordinator_factory

    def run(self, spec: RunSpec, emit: PaperEventHandler) -> Any:
        emit({"type": "start", "question": spec.question})
        coordinator_factory = self.coordinator_factory
        if coordinator_factory is not None:
            emit({"type": "stage", "stage": "tool_driven_smoke", "label": "测试工具驱动流程", "status": "running"})
        else:
            emit(
                {
                    "type": "stage",
                    "stage": "deepagent_reasoning",
                    "label": "DeepAgent 推理与工具编排",
                    "status": "running",
                }
            )
            emit(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": "DeepAgent 已接管任务，正在进行论文生产编排。阶段和产物会在真实工具写入后返回。",
                }
            )
        runner = CompetitionPaperRunner(
            output_root=self.output_root,
            settings=self.settings,
            coordinator_factory=coordinator_factory,
            event_handler=emit,
        )
        result = runner.run(spec)
        emit(
            {
                "type": "stage",
                "stage": "deepagent_reasoning" if coordinator_factory is None else "tool_driven_smoke",
                "label": "DeepAgent 推理与工具编排" if coordinator_factory is None else "测试工具驱动流程",
                "status": self._stage_status_for_result(result.status),
            }
        )
        for artifact in result.artifacts:
            emit({"type": "artifact", **to_json_dict(artifact)})
        emit(
            {
                "type": "done",
                "run_id": result.run_id,
                "status": result.status.value,
                "stage": result.stage.value,
                "summary": result.summary,
                "artifacts": [to_json_dict(artifact) for artifact in result.artifacts],
                "quality_reports": [to_json_dict(report) for report in result.quality_reports],
            }
        )
        if result.status == RunStatus.FAILED:
            emit({"type": "error", "message": result.summary})
        return result

    def _stage_status_for_result(self, status: RunStatus) -> str:
        if status == RunStatus.COMPLETED:
            return "completed"
        if status == RunStatus.PARTIAL:
            return "partial"
        if status == RunStatus.FAILED:
            return "failed"
        return status.value
