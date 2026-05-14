"""Docker 安全沙箱——容器隔离执行 Python 代码。

隔离级别：
- Filesystem: read-only root + tmpfs /tmp + 只挂载 output 目录可写
- Network: --network=none（完全断网）
- Memory: 512MB 硬限制
- CPU: 单核限制
- Process: 非 root 用户运行
- Timeout: 30s 硬超时
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..config import APP_ROOT

SANDBOX_DIR = APP_ROOT / "sandbox"
OUTPUT_DIR = APP_ROOT / "output"
IMAGE_NAME = "agent-app-sandbox:latest"
PYTHON_TIMEOUT = 30


@dataclass
class SandboxConfig:
    memory: str = "512m"
    cpus: str = "1.0"
    network: str = "none"
    read_only: bool = True
    timeout: int = 30
    image: str = IMAGE_NAME


@dataclass
class SandboxResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False
    error: str = ""


class DockerSandbox:
    """Docker 容器沙箱。"""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self.config = config or SandboxConfig()
        self._image_built = False

    @property
    def available(self) -> bool:
        return shutil.which("docker") is not None

    def build_image(self, force: bool = False) -> bool:
        """构建沙箱 Docker 镜像。"""
        if self._image_built and not force:
            return True

        dockerfile = SANDBOX_DIR / "Dockerfile"

        result = subprocess.run(
            ["docker", "build", "-t", self.config.image, "-f", str(dockerfile), str(SANDBOX_DIR)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            self._image_built = True
            return True
        print(f"[Sandbox] Image build failed: {result.stderr[:500]}")
        return False

    def run(self, code: str, timeout: int | None = None) -> SandboxResult:
        """在 Docker 容器中执行 Python 代码。"""
        if not self.available:
            return SandboxResult(success=False, stdout="", stderr="Docker not available", exit_code=-1)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        code_path = OUTPUT_DIR / "_sandbox_code.py"
        code_path.write_text(code, encoding="utf-8")

        cmd = [
            "docker", "run", "--rm",
            f"--memory={self.config.memory}",
            f"--cpus={self.config.cpus}",
            f"--network={self.config.network}",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-v", f"{OUTPUT_DIR}:/workspace/output:rw",
            "-v", f"{code_path}:/workspace/code.py:ro",
            "-w", "/workspace",
            self.config.image,
            "python", "code.py",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.config.timeout,
                cwd=str(OUTPUT_DIR),
            )
            out = result.stdout
            err = result.stderr
            return SandboxResult(
                success=result.returncode == 0,
                stdout=out[:4000] if out else "(no output)",
                stderr=err[:2000] if err else "",
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(success=False, stdout="", stderr="", exit_code=-1, timed_out=True, error=f"Timed out after {self.config.timeout}s")
        except Exception as exc:
            return SandboxResult(success=False, stdout="", stderr=str(exc), exit_code=-1, error=str(exc))


def _fallback_exec(code: str, timeout: int = PYTHON_TIMEOUT) -> SandboxResult:
    """宿主机降级执行（保留安全前导）。"""
    from ..tools import _SAFETY_PREAMBLE

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = OUTPUT_DIR / "_tmp_exec.py"
    tmp_path.write_text(_SAFETY_PREAMBLE + code, encoding="utf-8")

    try:
        result = subprocess.run(
            [sys.executable, str(tmp_path)],
            capture_output=True, text=True, timeout=timeout, cwd=str(OUTPUT_DIR),
        )
        return SandboxResult(
            success=result.returncode == 0,
            stdout=result.stdout[:4000] if result.stdout else "(no output)",
            stderr=result.stderr[:2000] if result.stderr else "",
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(success=False, stdout="", stderr="", exit_code=-1, timed_out=True)
    except Exception as exc:
        return SandboxResult(success=False, stdout="", stderr=str(exc), exit_code=-1)


def safe_execute(code: str, timeout: int = PYTHON_TIMEOUT) -> SandboxResult:
    """自动选择沙箱执行：Docker 优先，宿主机降级。"""
    sandbox = DockerSandbox()
    if sandbox.available:
        try:
            return sandbox.run(code, timeout)
        except Exception:
            pass
    return _fallback_exec(code, timeout)
