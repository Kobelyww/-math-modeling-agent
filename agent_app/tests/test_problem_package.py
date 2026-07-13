import json

from agent_app.domain.models import RunSpec
from agent_app.services.artifact_service import ArtifactService
from agent_app.services.problem_package import build_problem_package
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


def test_build_problem_package_writes_structured_tables(tmp_path):
    artifacts = ArtifactService(tmp_path)
    question = "问题1：抽样检测。表1 企业在生产中遇到的情况 情况 零配件1 次品率 1 10%。"
    tables = [
        {
            "title": "表1 企业在生产中遇到的情况",
            "page": 2,
            "method": "mimo_vision",
            "confidence": 0.82,
            "headers": ["情况", "零配件1次品率"],
            "rows": [["1", "10%"]],
        }
    ]

    package = build_problem_package(artifacts, question=question, tables=tables, figures=[])

    assert package["problem_spec_path"].endswith("problem_spec.json")
    tables_json = json.loads((tmp_path / "tables.json").read_text(encoding="utf-8"))
    assert tables_json["tables"][0]["title"] == "表1 企业在生产中遇到的情况"
    assert tables_json["tables"][0]["source"]["page"] == 2
    assert tables_json["tables"][0]["source"]["method"] == "mimo_vision"
    source_map = json.loads((tmp_path / "source_map.json").read_text(encoding="utf-8"))
    assert source_map["extraction_status"]["tables"] == {"status": "provided", "count": 1}
    assert source_map["sources"][1]["source_id"] == "table_1"


def test_ingest_inputs_creates_problem_package_without_changing_question_markdown(tmp_path):
    store = RunStore(output_root=tmp_path / "runs")
    question = "建立模型并完成论文。"
    state = store.create_run(RunSpec(question=question))
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    result = tools["ingest_inputs"].invoke(
        {
            "run_id": state.run_id,
            "question": question,
            "data_files": [],
            "reference_files": [],
        }
    )

    run_dir = store.run_dir(state.run_id)
    assert result["problem_package"]["problem_spec_path"].endswith("problem_spec.json")
    assert result["problem_package_paths"] == list(result["problem_package"].values())
    assert (run_dir / "problem_spec.json").exists()
    assert (run_dir / "tables.json").exists()
    assert (run_dir / "figures.json").exists()
    assert (run_dir / "source_map.json").exists()
    source_map = json.loads((run_dir / "source_map.json").read_text(encoding="utf-8"))
    assert source_map["extraction_status"]["tables"] == {"status": "not_attempted", "count": 0}
    assert source_map["extraction_status"]["figures"] == {"status": "not_attempted", "count": 0}
    assert (run_dir / "question.md").read_text(encoding="utf-8") == question + "\n"
