"""Docker 安全沙箱——Hermes 风格执行环境隔离。

参考 Hermes Agent s14 terminal backends。
支持 Docker 容器隔离执行，宿主机降级方案。
"""

from .docker_sandbox import (
    DockerSandbox, SandboxConfig, SandboxResult,
    safe_execute, _fallback_exec,
)

__all__ = [
    "DockerSandbox", "SandboxConfig", "SandboxResult",
    "safe_execute", "_fallback_exec",
]
