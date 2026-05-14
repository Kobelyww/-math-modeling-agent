from __future__ import annotations

import ast
import operator
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

from .config import APP_ROOT
from .literature import fetch_paper_to_kb, search_arxiv, search_crossref, search_semantic_scholar

NOTES_DIR = APP_ROOT / "notes"
OUTPUT_DIR = APP_ROOT / "output"
PYTHON_TIMEOUT = 30  # seconds

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Only basic numeric expressions are supported.")


def _safe_note_path(title: str) -> Path:
    safe = "".join(c for c in title.strip() if c.isalnum() or c in ("-", "_", " "))
    safe = safe.strip().replace(" ", "_")
    if not safe:
        raise ValueError("Note title cannot be empty.")
    return NOTES_DIR / f"{safe}.md"


# ===================== original tools =====================


@tool
def calculator(expression: str) -> str:
    """Calculate a basic arithmetic expression, e.g. '18 * (7 + 3)'."""
    try:
        parsed = ast.parse(expression, mode="eval")
        return str(_safe_eval(parsed))
    except Exception as exc:
        return f"Calculation failed: {exc}"


@tool
def current_time() -> str:
    """Return the current local date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def save_note(title: str, content: str) -> str:
    """Save a markdown note into the local notes directory."""
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = _safe_note_path(title)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return f"Saved note: {path.name}"


@tool
def read_note(title: str) -> str:
    """Read a note by title from the local notes directory."""
    path = _safe_note_path(title)
    if not path.exists():
        return f"Note not found: {path.name}"
    return path.read_text(encoding="utf-8")


@tool
def list_notes() -> str:
    """List all saved notes."""
    if not NOTES_DIR.exists():
        return "No notes saved yet."
    notes = sorted(p.stem for p in NOTES_DIR.glob("*.md"))
    return "\n".join(notes) if notes else "No notes saved yet."


# ===================== Python / data tools =====================


_SAFETY_PREAMBLE = """# --- safety preamble (auto-injected) ---
import sys as __sys
import os as __os
import builtins as __builtins
import resource as __resource

# 内存限制：512 MB
_MEM_LIMIT = 512 * 1024 * 1024
try:
    __resource.setrlimit(__resource.RLIMIT_AS, (_MEM_LIMIT, _MEM_LIMIT))
except (ValueError, AttributeError):
    pass

# 限制危险操作
__dangerous = {"os.system", "subprocess.call", "subprocess.run", "subprocess.Popen",
               "eval", "exec", "__import__", "compile", "open"}
__originals = {}
for __name in __dangerous:
    if hasattr(__builtins, __name):
        __originals[__name] = getattr(__builtins, __name)
        setattr(__builtins, __name,
                lambda *a, __n=__name, **kw: (_ for _ in ()).throw(
                    PermissionError(f"Operation blocked for safety: {__n}")))

# 限制文件读写范围
__orig_open = __builtins.open
__allowed_dir = __os.path.abspath(".")
def __safe_open(file, mode="r", *args, **kwargs):
    __abspath = __os.path.abspath(file)
    if "w" in mode and not __abspath.startswith(__allowed_dir):
        raise PermissionError(f"Write outside sandbox blocked: {file}")
    return __orig_open(file, mode, *args, **kwargs)
__builtins.open = __safe_open
# --- end safety preamble ---

"""


@tool
def python_exec(code: str) -> str:
    """Execute Python code in a sandbox and return the output.
    Use this to run calculations, test algorithms, generate plots, or
    verify a code snippet. Prints to stdout/stderr are captured.

    Safety: Docker container isolation (--network=none, --memory=512m,
    --read-only, non-root user) when Docker available. Falls back to
    subprocess with safety preamble (memory limit + blocked builtins).
    """
    from .sandbox import safe_execute

    result = safe_execute(code, timeout=PYTHON_TIMEOUT)

    if result.timed_out:
        return f"Execution timed out after {PYTHON_TIMEOUT}s."
    if not result.success and result.error:
        return f"Execution failed: {result.error}"

    out = result.stdout
    if result.stderr:
        out += f"\n[stderr]\n{result.stderr}"
    return out[:4000] if out.strip() else "(no output)"


@tool
def read_csv_info(filepath: str) -> str:
    """Read a CSV file and return its shape, column names, dtypes,
    first 5 rows, and basic statistics. Use this for quick data exploration."""
    try:
        import pandas as pd
    except ImportError:
        return "pandas is not installed. Run: pip install pandas"

    path = Path(filepath).expanduser()
    if not path.exists():
        return f"File not found: {filepath}"
    try:
        df = pd.read_csv(path)
        lines = [
            f"Shape: {df.shape[0]} rows × {df.shape[1]} cols",
            f"Columns: {list(df.columns)}",
            f"Dtypes:\n{df.dtypes.to_string()}",
            f"\nFirst 5 rows:\n{df.head().to_string()}",
            f"\nBasic statistics:\n{df.describe(include='all').to_string()}",
        ]
        return "\n".join(lines)[:4000]
    except Exception as exc:
        return f"Failed to read CSV: {exc}"


@tool
def pip_install(package: str) -> str:
    """Install a Python package via pip. Use when the code needs a library
    that may not be installed yet, e.g. 'numpy pandas matplotlib'."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", *package.split()],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return f"Successfully installed: {package}\n{result.stdout[-500:]}"
        return f"Install failed:\n{result.stderr[:1000]}"
    except subprocess.TimeoutExpired:
        return "Install timed out."
    except Exception as exc:
        return f"Install failed: {exc}"


# ===================== LaTeX / TeX tools =====================


_LATEX_TEMPLATE = r"""\documentclass[12pt,a4paper]{ctexart}

% ---------- packages ----------
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{hyperref}
\usepackage{geometry}
\geometry{left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm}

% ---------- title ----------
\title{数学建模论文}
\author{队伍名称}
\date{\today}

\begin{document}

\maketitle

\begin{abstract}
在此处撰写摘要（800-1000字），包含：
\begin{enumerate}
    \item 问题背景简介
    \item 每个问题的建模方法与关键数值结果
    \item 主要创新点
    \item 关键词
\end{enumerate}
\end{abstract}

\section{问题重述与分析}
\subsection{问题背景}
\subsection{问题分析}

\section{模型假设与符号说明}
\subsection{基本假设}
\subsection{符号说明}
\begin{table}[htbp]
\centering
\caption{符号说明表}
\begin{tabular}{cll}
\toprule
符号 & 含义 & 单位 \\
\midrule
$x$ & 决策变量 & -- \\
\midrule
\end{tabular}
\end{table}

\section{模型的建立与求解}
\subsection{问题一：}
\subsubsection{模型建立}
\subsubsection{模型求解}
\subsubsection{结果分析}

\section{模型检验与灵敏度分析}
\subsection{模型检验}
\subsection{灵敏度分析}

\section{模型评价与改进}
\subsection{模型优点}
\subsection{模型缺点}
\subsection{改进方向}

\section{参考文献}
\begin{thebibliography}{99}
\bibitem{ref1} 作者，题目，期刊/出版社，年份.
\end{thebibliography}

\section{附录}
附录内容（代码、数据表格等）。

\end{document}
"""


@tool
def latex_template() -> str:
    """Return a LaTeX paper template for mathematical modeling competitions.
    The template follows the standard structure: abstract, problem restatement,
    model assumptions, model building & solving, sensitivity analysis, and
    conclusions."""
    return _LATEX_TEMPLATE


@tool
def latex_compile(content: str, filename: str = "paper") -> str:
    """Compile a LaTeX document to PDF. Provide the complete .tex content
    and an optional filename (without extension). Requires texlive/MacTeX
    to be installed. Returns the path to the generated PDF or an error message."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tex_path = OUTPUT_DIR / f"{filename}.tex"
    tex_path.write_text(content, encoding="utf-8")

    try:
        # first pass
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory",
             str(OUTPUT_DIR), str(tex_path)],
            capture_output=True, text=True, timeout=60,
            cwd=str(OUTPUT_DIR),
        )
        # second pass (for toc / cross-refs)
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory",
             str(OUTPUT_DIR), str(tex_path)],
            capture_output=True, text=True, timeout=60,
            cwd=str(OUTPUT_DIR),
        )

        pdf_path = OUTPUT_DIR / f"{filename}.pdf"
        if pdf_path.exists():
            return f"Compilation successful. PDF at: {pdf_path}"
        # try to extract error
        log_path = OUTPUT_DIR / f"{filename}.log"
        if log_path.exists():
            log_text = log_path.read_text(errors="ignore")
            for line in log_text.splitlines():
                if line.startswith("!"):
                    return f"LaTeX error: {line.strip()}\nFull log: {log_path}"
        return f"Compilation failed. Log: {OUTPUT_DIR / f'{filename}.log'}"
    except FileNotFoundError:
        return "pdflatex not found. Install TeX Live (texlive) or MacTeX."
    except subprocess.TimeoutExpired:
        return "Compilation timed out."
    except Exception as exc:
        return f"Compilation failed: {exc}"


@tool
def latex_render_math(latex_expr: str) -> str:
    """Render a single LaTeX math expression as a standalone equation.
    Returns the rendered PDF path or an error. Useful for checking the output
    of a formula before inserting it into the full paper."""
    doc = rf"""\documentclass[12pt]{{standalone}}
\usepackage{{amsmath,amssymb}}
\usepackage{{xcolor}}
\begin{{document}}
$\displaystyle {latex_expr}$
\end{{document}}
"""
    return latex_compile.func(doc, filename="_math_preview")


# ===================== Nature Skills tools =====================


@tool
def nature_viz_template(template_name: str) -> str:
    """Return a Nature journal style matplotlib template code for MCM/ICM papers.
    Available templates: standard_line, 3d_grid, stacked_plots, hysteresis,
    performance_3d_bar, performance_radar, performance_lollipop, regression.

    Example: nature_viz_template('standard_line')
    """
    from .nature_skills import get_viz_template

    mapping = {
        "standard_line": "01_standard_line_plot",
        "3d_grid": "02_nature_3d_grid_refactored",
        "stacked_plots": "03_stacked_plots_highlight",
        "hysteresis": "04_hysteresis_loops_nature",
        "3d_bar": "05_performance_3d_bar",
        "radar": "06_performance_radar",
        "lollipop": "07_performance_lollipop",
        "regression": "08_complex_regression_analysis",
    }
    file_name = mapping.get(template_name, template_name)
    code = get_viz_template(file_name)
    if code:
        return code[:4000]
    available = ", ".join(mapping.keys())
    return f"Template '{template_name}' not found. Available: {available}"


@tool
def model_reference() -> str:
    """Return the mathematical model selection reference guide.
    Covers optimization, prediction, evaluation, dynamic systems, and graph/network models.
    Use when unsure which model type to apply to a problem.
    """
    from .nature_skills import get_model_reference

    return get_model_reference()[:4000]


@tool
def writing_rules() -> str:
    """Return MCM/ICM academic writing standards: structure, de-AI-fication rules,
    abstract requirements, formatting, and citation format.
    Use when writing or revising competition papers.
    """
    from .nature_skills import get_writing_rules

    return get_writing_rules()[:4000]


# ===================== tool list =====================

TOOLS = [
    calculator,
    current_time,
    save_note,
    read_note,
    list_notes,
    python_exec,
    read_csv_info,
    pip_install,
    latex_template,
    latex_compile,
    latex_render_math,
    search_arxiv,
    search_semantic_scholar,
    search_crossref,
    fetch_paper_to_kb,
    nature_viz_template,
    model_reference,
    writing_rules,
]
