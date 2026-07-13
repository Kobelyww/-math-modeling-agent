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

    assert llm.create_llm is legacy_llm.create_llm

    assert base.normalize_content is legacy_base.normalize_content
    assert base.extract_story_body is legacy_base.extract_story_body

    assert tools.TOOLS is legacy_tools.TOOLS
    assert tools.save_article is legacy_tools.save_article
