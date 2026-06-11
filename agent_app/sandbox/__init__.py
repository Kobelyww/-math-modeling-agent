"""Docker 安全沙箱——Hermes 风格执行环境隔离。

参考 Hermes Agent s14 terminal backends。
默认仅使用 Docker 容器隔离；宿主机执行仅作为显式不安全的受信开发降级。
"""

from .docker_sandbox import (
    DockerSandbox, SandboxConfig, SandboxResult,
    safe_execute, _fallback_exec,
)

__all__ = [
    "DockerSandbox", "SandboxConfig", "SandboxResult",
    "safe_execute", "_fallback_exec",
]
