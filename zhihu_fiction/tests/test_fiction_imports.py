from __future__ import annotations


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
    assert agents.ReviewerAgent is legacy_agents.ReviewerAgent

    assert orchestrator.run_coordinator is legacy_orchestrator.run_coordinator
    assert orchestrator.WorkflowResult is legacy_orchestrator.WorkflowResult
    assert orchestrator.StageResult is legacy_orchestrator.StageResult

    assert pipeline.Pipeline is legacy_pipeline.Pipeline
    assert pipeline.RunResult is legacy_pipeline.RunResult
    assert pipeline.select_topic is legacy_pipeline.select_topic

    assert scraper.scrape_zhihu_hot is legacy_scraper.scrape_zhihu_hot
    assert scraper.search_zhihu_topic is legacy_scraper.search_zhihu_topic
    assert scraper.manual_entry is legacy_scraper.manual_entry

    assert distiller.Distiller is legacy_distiller.Distiller
    assert distiller.distill_single is legacy_distiller.distill_single
    assert distiller.distill_aggregate is legacy_distiller.distill_aggregate

    assert skills_store.SkillsStore is legacy_skills_store.SkillsStore

    assert tools.TOOLS is legacy_tools.TOOLS
    assert tools.save_article is legacy_tools.save_article
    assert tools.save_article.func.__module__ == "zhihu_fiction.fiction.tools"
    assert tools.scrape_hot.func.__module__ == "zhihu_fiction.fiction.tools"
