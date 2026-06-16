from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import ExperimentResult
from agent_app.sandbox import safe_execute


class CodeExecutionService:
    def __init__(self, timeout: int = 30, allow_unsafe_host_fallback: bool = False) -> None:
        self.timeout = timeout
        self.allow_unsafe_host_fallback = allow_unsafe_host_fallback

    def write_code(self, run_dir: Path, code: str) -> Path:
        path = Path(run_dir) / "solve.py"
        path.write_text(code.rstrip() + "\n", encoding="utf-8")
        return path

    def execute_code(self, code: str, cwd: Path) -> ExperimentResult:
        result = safe_execute(
            code,
            timeout=self.timeout,
            cwd=Path(cwd),
            allow_unsafe_host_fallback=self.allow_unsafe_host_fallback,
        )
        status = "success" if result.success and not result.timed_out else "failed"
        stderr = result.stderr or result.error or ""
        if result.timed_out:
            stderr = f"Timed out after {self.timeout}s"
        return ExperimentResult(
            execution_status=status,
            stdout=result.stdout,
            stderr=stderr,
            reproducibility_notes=f"Executed with timeout={self.timeout}s",
        )
