"""Docker 安全沙箱——容器隔离执行 Python 代码。

隔离级别：
- Filesystem: read-only root + tmpfs /tmp + 只挂载工作目录可写
- Network: --network=none（完全断网）
- Memory: 512MB 硬限制
- CPU: 单核限制
- Process: 非 root 用户运行
- Timeout: 30s 硬超时
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..config import APP_ROOT

SANDBOX_DIR = APP_ROOT / "sandbox"
OUTPUT_DIR = APP_ROOT / "output"
IMAGE_NAME = "agent-app-sandbox:latest"
PYTHON_TIMEOUT = 30

_DOCKER_INFRASTRUCTURE_ERRORS = (
    "docker api",
    "docker daemon",
    "docker not available",
    "cannot connect",
    "permission denied while trying to connect",
    "error response from daemon",
    "no such image",
    "pull access denied",
    "container create failed",
    "oci runtime create failed",
    "failed to create task",
)


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
        if shutil.which("docker") is None:
            return False
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            return False
        return result.returncode == 0

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
        logger.error("[Sandbox] Image build failed: %s", result.stderr[:500])
        return False

    def run(self, code: str, timeout: int | None = None, cwd: Path | None = None) -> SandboxResult:
        """在 Docker 容器中执行 Python 代码。"""
        if not self.available:
            return SandboxResult(success=False, stdout="", stderr="Docker not available", exit_code=-1)

        work_dir = Path(cwd or OUTPUT_DIR).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            with tempfile.TemporaryDirectory(prefix="agent_sandbox_") as tmp_dir:
                code_path = Path(tmp_dir) / "code.py"
                code_path.write_text(code, encoding="utf-8")

                cmd = [
                    "docker", "run", "--rm",
                    f"--memory={self.config.memory}",
                    f"--cpus={self.config.cpus}",
                    f"--network={self.config.network}",
                    "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
                    "-v", f"{work_dir}:/workspace/output:rw",
                    "-v", f"{code_path}:/workspace/code.py:ro",
                    "-w", "/workspace/output",
                    self.config.image,
                    "python", "/workspace/code.py",
                ]
                if self.config.read_only:
                    cmd.insert(3, "--read-only")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout or self.config.timeout,
                    cwd=str(work_dir),
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
            effective_timeout = timeout or self.config.timeout
            return SandboxResult(success=False, stdout="", stderr="", exit_code=-1, timed_out=True, error=f"Timed out after {effective_timeout}s")
        except Exception as exc:
            return SandboxResult(success=False, stdout="", stderr=str(exc), exit_code=-1, error=str(exc))


def _is_docker_infrastructure_failure(result: SandboxResult) -> bool:
    if result.timed_out or result.exit_code not in (-1, 125):
        return False
    message = f"{result.stderr}\n{result.error}".lower()
    return any(marker in message for marker in _DOCKER_INFRASTRUCTURE_ERRORS)


def _fallback_preamble(work_dir: Path) -> str:
    return f'''# --- safety preamble (auto-injected) ---
def __agent_install_safety():
    import builtins
    import resource
    import sys
    from pathlib import Path

    # 内存限制：512 MB
    mem_limit = 512 * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
    except (ValueError, AttributeError):
        pass

    def blocked_operation(*args, __operation="operation", **kwargs):
        raise PermissionError(f"Operation blocked for safety: {{__operation}}")

    dangerous = {{"eval", "exec", "__import__", "compile"}}
    for name in dangerous:
        if hasattr(builtins, name):
            setattr(
                builtins,
                name,
                lambda *args, __name=name, **kwargs: blocked_operation(
                    *args, __operation=__name, **kwargs
                ),
            )

    # Host fallback is not Docker isolation. Use an audit hook rather than a
    # Python open wrapper, so user code cannot recover raw file APIs from
    # open.__closure__ or wrapper attributes.
    allowed_dir = Path({str(work_dir)!r}).resolve()

    def audit_file_access(event, args):
        if event != "open":
            return
        file = args[0] if args else None
        if isinstance(file, int):
            raise PermissionError("File descriptor access blocked for safety")
        if file is None:
            return
        resolved = Path(file).resolve()
        try:
            resolved.relative_to(allowed_dir)
        except ValueError:
            raise PermissionError(f"File access outside sandbox blocked: {{file}}")

    sys.addaudithook(audit_file_access)

__agent_install_safety()
del __agent_install_safety
# --- end safety preamble ---

'''


def _fallback_exec(code: str, timeout: int = PYTHON_TIMEOUT, cwd: Path | None = None) -> SandboxResult:
    """Unsafe trusted/dev host fallback. Not a security boundary for untrusted code."""
    work_dir = Path(cwd or OUTPUT_DIR).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = work_dir / "_tmp_exec.py"
    tmp_path.write_text(_fallback_preamble(work_dir) + code, encoding="utf-8")

    try:
        result = subprocess.run(
            [sys.executable, str(tmp_path)],
            capture_output=True, text=True, timeout=timeout, cwd=str(work_dir),
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


def _host_fallback_disabled_result() -> SandboxResult:
    return SandboxResult(
        success=False,
        stdout="",
        stderr="Docker sandbox unavailable; unsafe host fallback disabled",
        exit_code=-1,
        error="Docker sandbox unavailable; unsafe host fallback disabled",
    )


def safe_execute(
    code: str,
    timeout: int = PYTHON_TIMEOUT,
    cwd: Path | None = None,
    allow_unsafe_host_fallback: bool = False,
) -> SandboxResult:
    """Execute in Docker; host execution requires explicit unsafe opt-in."""
    sandbox = DockerSandbox()
    if sandbox.available:
        try:
            result = sandbox.run(code, timeout, cwd=cwd)
            if not _is_docker_infrastructure_failure(result):
                return result
        except Exception:
            pass
    if allow_unsafe_host_fallback:
        return _fallback_exec(code, timeout, cwd=cwd)
    return _host_fallback_disabled_result()
