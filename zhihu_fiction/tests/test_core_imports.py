from __future__ import annotations


def test_core_modules_expose_existing_public_api() -> None:
    from zhihu_fiction import base as legacy_base
    from zhihu_fiction import config as legacy_config
    from zhihu_fiction import llm as legacy_llm
    from zhihu_fiction import tools as legacy_tools
    from zhihu_fiction.core import base, config, llm, tools

    assert config.APP_ROOT == legacy_config.APP_ROOT
    assert config.Settings is legacy_config.Settings
    assert config.AgentConfig is legacy_config.AgentConfig
    assert config.load_settings is legacy_config.load_settings
    assert config.APP_ROOT.name == "zhihu_fiction"
    assert config.Settings.__module__ == "zhihu_fiction.core.config"
    assert config.AgentConfig.__module__ == "zhihu_fiction.core.config"
    assert config.load_settings.__module__ == "zhihu_fiction.core.config"

    assert llm.create_llm is legacy_llm.create_llm
    assert llm.create_llm.__module__ == "zhihu_fiction.core.llm"

    assert base.normalize_content is legacy_base.normalize_content
    assert base.extract_story_body is legacy_base.extract_story_body
    assert base.normalize_content.__module__ == "zhihu_fiction.core.base"
    assert base.extract_story_body.__module__ == "zhihu_fiction.core.base"

    assert tools.TOOLS is legacy_tools.TOOLS
    assert tools.save_article is legacy_tools.save_article
    assert tools.save_article.func.__module__ == "zhihu_fiction.fiction.tools"
