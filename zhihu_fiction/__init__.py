__all__ = [
    "Settings",
    "load_settings",
    "Pipeline",
    "SkillsStore",
    "Exporter",
    "ZhihuSaltPublisher",
    "QidianPublisher",
    "FanqiePublisher",
]


def __getattr__(name: str):
    if name in {"Settings", "load_settings"}:
        from .config import Settings, load_settings

        return {"Settings": Settings, "load_settings": load_settings}[name]
    if name == "Exporter":
        from .exporter import Exporter

        return Exporter
    if name == "Pipeline":
        from .pipeline import Pipeline

        return Pipeline
    if name == "SkillsStore":
        from .skills_store import SkillsStore

        return SkillsStore
    if name in {"ZhihuSaltPublisher", "QidianPublisher", "FanqiePublisher"}:
        from .publishers import FanqiePublisher, QidianPublisher, ZhihuSaltPublisher

        return {
            "ZhihuSaltPublisher": ZhihuSaltPublisher,
            "QidianPublisher": QidianPublisher,
            "FanqiePublisher": FanqiePublisher,
        }[name]
    raise AttributeError(f"module 'zhihu_fiction' has no attribute {name!r}")
