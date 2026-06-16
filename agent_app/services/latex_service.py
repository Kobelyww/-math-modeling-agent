from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


class LatexService:
    def _failure(self, tex_path: Path, diagnostics: str) -> dict[str, Any]:
        log_path = tex_path.with_suffix(".log")
        return {
            "compiled": False,
            "pdf_path": "",
            "log_path": str(log_path) if log_path.exists() else "",
            "diagnostics": diagnostics,
        }

    def compile(self, tex_path: Path) -> dict[str, Any]:
        tex_path = Path(tex_path)
        if shutil.which("pdflatex") is None:
            return self._failure(tex_path, "pdflatex not found. Install TeX Live or MacTeX to compile PDF.")

        try:
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(tex_path.parent), str(tex_path)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(tex_path.parent),
            )
        except subprocess.TimeoutExpired as exc:
            return self._failure(tex_path, f"pdflatex timed out after {exc.timeout}s.")
        except FileNotFoundError:
            return self._failure(tex_path, "pdflatex not found. Install TeX Live or MacTeX to compile PDF.")
        except OSError as exc:
            return self._failure(tex_path, f"pdflatex failed: {exc}")

        pdf_path = tex_path.with_suffix(".pdf")
        log_path = tex_path.with_suffix(".log")
        return {
            "compiled": pdf_path.exists() and result.returncode == 0,
            "pdf_path": str(pdf_path) if pdf_path.exists() else "",
            "log_path": str(log_path) if log_path.exists() else "",
            "diagnostics": result.stderr or result.stdout[-2000:],
        }
