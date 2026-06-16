from __future__ import annotations

from agent_app.domain.models import RunSpec
from agent_app.services.run_store import RunStore
from agent_app.services.stage_review_service import StageReviewService


def test_stage_review_service_creates_versioned_outputs_with_fingerprints(tmp_path):
    run_store = RunStore(tmp_path)
    state = run_store.create_run(RunSpec(question="建立交通流预测模型"))
    service = StageReviewService(run_store)

    review = service.create_review(
        run_id=state.run_id,
        stage="understand_problem",
        stage_label="理解赛题",
        status="awaiting_user",
        summary="识别出预测目标和数据约束。",
        review_payload={"objectives": ["预测交通流"], "constraints": ["使用本地数据"]},
        input_payload={"question": "建立交通流预测模型"},
    )

    assert review.output_id == "understand_problem_v1"
    assert review.version == 1
    assert review.status == "awaiting_user"
    assert review.input_fingerprint
    assert review.review_payload["objectives"] == ["预测交通流"]

    restored = service.list_reviews(state.run_id)
    assert [item.output_id for item in restored] == ["understand_problem_v1"]
    assert restored[0].input_fingerprint == review.input_fingerprint


def test_stage_review_service_marks_transitive_downstream_reviews_stale(tmp_path):
    run_store = RunStore(tmp_path)
    state = run_store.create_run(RunSpec(question="建立交通流预测模型"))
    service = StageReviewService(run_store)

    problem = service.create_review(
        run_id=state.run_id,
        stage="understand_problem",
        stage_label="理解赛题",
        status="approved",
        summary="问题定义 v1",
        review_payload={"summary": "v1"},
        input_payload={"question": "v1"},
    )
    audit = service.create_review(
        run_id=state.run_id,
        stage="audit_data",
        stage_label="审计数据",
        status="approved",
        summary="数据审计 v1",
        review_payload={"files": ["traffic.csv"]},
        input_payload={"problem": problem.output_id},
        depends_on=[problem.dependency_ref()],
    )
    plan = service.create_review(
        run_id=state.run_id,
        stage="plan_modeling",
        stage_label="规划模型",
        status="approved",
        summary="模型规划 v1",
        review_payload={"selected_model": "baseline"},
        input_payload={"audit": audit.output_id},
        depends_on=[audit.dependency_ref()],
    )

    invalidated = service.invalidate_downstream(
        run_id=state.run_id,
        stage="understand_problem",
        version=problem.version,
        decision_id="decision_revise_problem",
        reason="问题理解被用户修改。",
    )

    assert [item.output_id for item in invalidated] == ["audit_data_v1", "plan_modeling_v1"]
    reviews = {item.output_id: item for item in service.list_reviews(state.run_id)}
    assert reviews[problem.output_id].status == "approved"
    assert reviews[audit.output_id].status == "stale"
    assert reviews[plan.output_id].status == "stale"
    assert reviews[plan.output_id].invalidated_by["decision_id"] == "decision_revise_problem"


def test_approve_with_payload_patch_creates_new_version_and_invalidates_downstream(tmp_path):
    run_store = RunStore(tmp_path)
    state = run_store.create_run(RunSpec(question="建立交通流预测模型"))
    service = StageReviewService(run_store)

    problem = service.create_review(
        run_id=state.run_id,
        stage="understand_problem",
        stage_label="理解赛题",
        status="awaiting_user",
        summary="问题定义 v1",
        review_payload={"constraints": ["旧约束"]},
        input_payload={"question": "v1"},
    )
    service.create_review(
        run_id=state.run_id,
        stage="plan_modeling",
        stage_label="规划模型",
        status="approved",
        summary="模型规划 v1",
        review_payload={"selected_model": "baseline"},
        input_payload={"problem": problem.output_id},
        depends_on=[problem.dependency_ref()],
    )

    patched, invalidated = service.approve_with_payload_patch(
        run_id=state.run_id,
        output_id=problem.output_id,
        payload_patch={"constraints": ["新约束"]},
        decision_id="decision_patch_problem",
    )

    assert patched.output_id == "understand_problem_v2"
    assert patched.version == 2
    assert patched.status == "approved"
    assert patched.review_payload["constraints"] == ["新约束"]
    assert [item.output_id for item in invalidated] == ["plan_modeling_v1"]
