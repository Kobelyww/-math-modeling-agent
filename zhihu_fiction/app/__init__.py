"""FastAPI application package for Zhihu Fiction Studio."""

__all__ = ["AppDependencies", "AppState", "create_app"]


def __getattr__(name: str):
    if name == "AppDependencies":
        from .dependencies import AppDependencies

        return AppDependencies
    if name == "create_app":
        from .factory import create_app

        return create_app
    if name == "AppState":
        from .state import AppState

        return AppState
    raise AttributeError(f"module 'zhihu_fiction.app' has no attribute {name!r}")
