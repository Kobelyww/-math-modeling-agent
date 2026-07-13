from __future__ import annotations

import ast
import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_ROOT_MODULES = {
    "zhihu_fiction.agents",
    "zhihu_fiction.base",
    "zhihu_fiction.config",
    "zhihu_fiction.distiller",
    "zhihu_fiction.llm",
    "zhihu_fiction.orchestrator",
    "zhihu_fiction.pipeline",
    "zhihu_fiction.pipeline_storage",
    "zhihu_fiction.scraper",
    "zhihu_fiction.skills_store",
    "zhihu_fiction.tools",
}
LEGACY_MODULE_FILES = {
    PROJECT_ROOT / "agents.py",
    PROJECT_ROOT / "base.py",
    PROJECT_ROOT / "config.py",
    PROJECT_ROOT / "distiller.py",
    PROJECT_ROOT / "llm.py",
    PROJECT_ROOT / "orchestrator.py",
    PROJECT_ROOT / "pipeline.py",
    PROJECT_ROOT / "pipeline_storage.py",
    PROJECT_ROOT / "scraper.py",
    PROJECT_ROOT / "skills_store.py",
    PROJECT_ROOT / "tools.py",
}


def test_legacy_fiction_modules_alias_real_implementation_modules() -> None:
    aliases = [
        ("zhihu_fiction.agents", "zhihu_fiction.fiction.agents"),
        ("zhihu_fiction.distiller", "zhihu_fiction.fiction.distiller"),
        ("zhihu_fiction.orchestrator", "zhihu_fiction.fiction.orchestrator"),
        ("zhihu_fiction.pipeline", "zhihu_fiction.fiction.pipeline"),
        ("zhihu_fiction.scraper", "zhihu_fiction.fiction.scraper"),
        ("zhihu_fiction.skills_store", "zhihu_fiction.fiction.skills_store"),
        ("zhihu_fiction.tools", "zhihu_fiction.fiction.tools"),
    ]

    for legacy_name, implementation_name in aliases:
        legacy_module = importlib.import_module(legacy_name)
        implementation_module = importlib.import_module(implementation_name)
        assert legacy_module is implementation_module


def _module_name_for_path(path: Path) -> str:
    relative = path.relative_to(PROJECT_ROOT.parent).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _resolve_import_from_module(path: Path, node: ast.ImportFrom) -> str | None:
    if node.module is None and node.level == 0:
        return None
    if node.level == 0:
        return node.module

    module_name = _module_name_for_path(path)
    module_parts = module_name.split(".")
    package_parts = module_parts if path.name == "__init__.py" else module_parts[:-1]
    base_len = len(package_parts) - (node.level - 1)
    if base_len < 0:
        return None
    resolved_parts = package_parts[:base_len]
    if node.module:
        resolved_parts.extend(node.module.split("."))
    return ".".join(resolved_parts)


def test_internal_code_imports_real_namespaces_not_legacy_root_modules() -> None:
    violations: list[str] = []

    for path in sorted(PROJECT_ROOT.rglob("*.py")):
        if path in LEGACY_MODULE_FILES or "tests" in path.relative_to(PROJECT_ROOT).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported_modules: list[str] = []
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                resolved = _resolve_import_from_module(path, node)
                if resolved:
                    imported_modules.append(resolved)

            for module in imported_modules:
                if module in LEGACY_ROOT_MODULES:
                    rel = path.relative_to(PROJECT_ROOT)
                    violations.append(f"{rel}:{node.lineno} imports {module}")

    assert violations == []


def test_fiction_modules_expose_existing_story_pipeline_api() -> None:
    from zhihu_fiction import agents as legacy_agents
    from zhihu_fiction import distiller as legacy_distiller
    from zhihu_fiction import orchestrator as legacy_orchestrator
    from zhihu_fiction import pipeline as legacy_pipeline
    from zhihu_fiction import scraper as legacy_scraper
    from zhihu_fiction import skills_store as legacy_skills_store
    from zhihu_fiction import tools as legacy_tools
    from zhihu_fiction.fiction import agents, distiller, orchestrator, pipeline, scraper, skills_store, tools

    assert agents.create_coordinator is legacy_agents.create_coordinator
    assert agents.create_drama_video_coordinator is legacy_agents.create_drama_video_coordinator
    assert agents.ReviewerAgent is legacy_agents.ReviewerAgent
    assert agents.create_coordinator.__module__ == "zhihu_fiction.fiction.agents"
    assert agents.create_drama_video_coordinator.__module__ == "zhihu_fiction.fiction.agents"
    assert agents.ReviewerAgent.__module__ == "zhihu_fiction.fiction.agents"
    assert agents._make_analyze_topic.__module__ == "zhihu_fiction.fiction.agents"
    assert agents._make_plan_outline.__module__ == "zhihu_fiction.fiction.agents"
    assert agents._make_write_draft.__module__ == "zhihu_fiction.fiction.agents"
    assert agents._make_polish_draft.__module__ == "zhihu_fiction.fiction.agents"
    assert agents._make_synthesize.__module__ == "zhihu_fiction.fiction.agents"

    assert orchestrator.run_coordinator is legacy_orchestrator.run_coordinator
    assert orchestrator.WorkflowResult is legacy_orchestrator.WorkflowResult
    assert orchestrator.StageResult is legacy_orchestrator.StageResult
    assert orchestrator.run_coordinator.__module__ == "zhihu_fiction.fiction.orchestrator"
    assert orchestrator.WorkflowResult.__module__ == "zhihu_fiction.fiction.orchestrator"
    assert orchestrator.StageResult.__module__ == "zhihu_fiction.fiction.orchestrator"

    assert pipeline.Pipeline is legacy_pipeline.Pipeline
    assert pipeline.RunResult is legacy_pipeline.RunResult
    assert pipeline.select_topic is legacy_pipeline.select_topic
    assert pipeline.Pipeline.__module__ == "zhihu_fiction.fiction.pipeline"
    assert pipeline.RunResult.__module__ == "zhihu_fiction.fiction.pipeline"
    assert pipeline.StageRecord.__module__ == "zhihu_fiction.fiction.pipeline"
    assert pipeline.select_topic.__module__ == "zhihu_fiction.fiction.pipeline"

    assert scraper.scrape_zhihu_hot is legacy_scraper.scrape_zhihu_hot
    assert scraper.search_zhihu_topic is legacy_scraper.search_zhihu_topic
    assert scraper.manual_entry is legacy_scraper.manual_entry
    assert scraper.scrape_zhihu_hot.__module__ == "zhihu_fiction.fiction.scraper"
    assert scraper.search_zhihu_topic.__module__ == "zhihu_fiction.fiction.scraper"
    assert scraper.manual_entry.__module__ == "zhihu_fiction.fiction.scraper"
    assert scraper.save_scraped_content.__module__ == "zhihu_fiction.fiction.scraper"
    assert scraper.load_scraped_file.__module__ == "zhihu_fiction.fiction.scraper"
    assert scraper.fetch_question_answers.__module__ == "zhihu_fiction.fiction.scraper"

    assert distiller.Distiller is legacy_distiller.Distiller
    assert distiller.distill_single is legacy_distiller.distill_single
    assert distiller.distill_aggregate is legacy_distiller.distill_aggregate
    assert distiller.Distiller.__module__ == "zhihu_fiction.fiction.distiller"
    assert distiller.distill_single.__module__ == "zhihu_fiction.fiction.distiller"
    assert distiller.distill_aggregate.__module__ == "zhihu_fiction.fiction.distiller"

    assert skills_store.SkillsStore is legacy_skills_store.SkillsStore
    assert skills_store.SkillsStore.__module__ == "zhihu_fiction.fiction.skills_store"

    assert tools.TOOLS is legacy_tools.TOOLS
    assert tools.save_article is legacy_tools.save_article
    assert tools.save_article.func.__module__ == "zhihu_fiction.fiction.tools"
    assert tools.scrape_hot.func.__module__ == "zhihu_fiction.fiction.tools"
