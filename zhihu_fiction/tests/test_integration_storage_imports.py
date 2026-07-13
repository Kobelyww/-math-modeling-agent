from __future__ import annotations


def test_integration_modules_expose_existing_external_adapters() -> None:
    from zhihu_fiction import automator as legacy_automator
    from zhihu_fiction import automator_zhihu as legacy_zhihu
    from zhihu_fiction.drama import video as legacy_video
    from zhihu_fiction.integrations import bailian_video, browser_automation, zhihu_browser

    assert browser_automation.Automator is legacy_automator.Automator
    assert browser_automation.AutomatorError is legacy_automator.AutomatorError
    assert browser_automation.LoginTimeout is legacy_automator.LoginTimeout

    assert zhihu_browser.ZhihuPublisher is legacy_zhihu.ZhihuPublisher
    assert zhihu_browser.PublishError is legacy_zhihu.PublishError
    assert zhihu_browser.LoginRequired is legacy_zhihu.LoginRequired

    assert bailian_video.BailianVideoProvider is legacy_video.BailianVideoProvider
    assert bailian_video.BailianVideoConfig is legacy_video.BailianVideoConfig
    assert bailian_video.VideoJob is legacy_video.VideoJob
    assert bailian_video.VideoJobStore is legacy_video.VideoJobStore
    assert bailian_video.create_video_provider is legacy_video.create_video_provider
    assert bailian_video.load_bailian_video_config is legacy_video.load_bailian_video_config


def test_storage_modules_expose_existing_storage_adapters() -> None:
    from zhihu_fiction import pipeline_storage as legacy_pipeline_storage
    from zhihu_fiction.app.services import object_storage as legacy_object_storage
    from zhihu_fiction.storage import object_storage, pipeline_storage

    assert pipeline_storage.PipelineStorage is legacy_pipeline_storage.PipelineStorage
    assert pipeline_storage.PipelineStorage.__module__ == "zhihu_fiction.storage.pipeline_storage"

    assert object_storage.LocalObjectStorage is legacy_object_storage.LocalObjectStorage
    assert object_storage.MinioObjectStorage is legacy_object_storage.MinioObjectStorage
    assert object_storage.create_object_storage is legacy_object_storage.create_object_storage
    assert object_storage.LocalObjectStorage.__module__ == "zhihu_fiction.storage.object_storage"
    assert object_storage.MinioObjectStorage.__module__ == "zhihu_fiction.storage.object_storage"
    assert object_storage.create_object_storage.__module__ == "zhihu_fiction.storage.object_storage"
