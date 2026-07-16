#!/usr/bin/env bash
# 从 Markdown 生成 TeX/PDF（含中文 preamble 补丁）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

MD="claude_and_hermes_agent_guide.md"
TEX="claude_and_hermes_agent_guide.tex"

echo "==> Pandoc: $MD -> $TEX"
pandoc "$MD" -o "$TEX" --standalone --toc --toc-depth=3 \
  -V documentclass=ctexart \
  -V documentclass-options="11pt,a4paper,fontset=fandol" \
  -V geometry:margin=2.5cm \
  -V linestretch=1.25 \
  --syntax-highlighting=tango \
  -f markdown+smart

echo "==> Preamble patches (Python)"
python3 <<'PY'
from pathlib import Path
tex = Path("claude_and_hermes_agent_guide.tex")
t = tex.read_text(encoding="utf-8")

# documentclass fontset — pandoc may emit documentclass-options separately
if "fontset=fandol" not in t.split("\\begin{document}")[0]:
    t = t.replace(
        "\\documentclass[\n  11pt,\n]{ctexart}",
        "\\documentclass[\n  11pt,\n  a4paper,\n  fontset=fandol,\n]{ctexart}",
    )
# broken merge guard
t = t.replace(
    "][11pt,a4paper,fontset=fandol]{ctexart}",
    "[\n  11pt,\n  a4paper,\n  fontset=fandol,\n]{ctexart}",
)

# Remove PingFang override block if present
import re
t = re.sub(
    r"\\ifPDFTeX\\else\n.*?\\fi\n",
    r"\\ifPDFTeX\\else\n  % ctex fontset=fandol\n\\fi\n",
    t,
    count=1,
    flags=re.S,
)

# Packages after amssymb
needle = "\\usepackage{amsmath,amssymb}"
if needle in t and "usepackage{booktabs}" not in t.split("\\begin{document}")[0]:
    t = t.replace(
        needle,
        needle + "\n\\usepackage{booktabs}\n\\usepackage{longtable}\n\\usepackage{array}\n\\usepackage{listings}\n"
        "\\lstset{\n  basicstyle=\\ttfamily\\small,\n  breaklines=true,\n  frame=single,\n"
        "  rulecolor=\\color[RGB]{180,180,180},\n  backgroundcolor=\\color[RGB]{248,248,248},\n}",
    )

# Section numbering
t = t.replace(
    "\\setcounter{secnumdepth}{-\\maxdimen}",
    "\\setcounter{secnumdepth}{3}",
)

# Title block
old_begin = "\\author{}\n\\date{}\n\n\\begin{document}"
new_begin = """\\title{Claude Code \\& Hermes Agent\\\\技术全解与 Agent 工程师学习路线}
\\author{LLM-Study 技术文档 \\\\ \\small v1.2 · 2026-05}
\\date{}

\\begin{document}

\\maketitle
\\begin{abstract}
本文档整合 Claude Code、Hermes Agent、LangGraph 与 agent\\_app 参考实现，
含第五部分全章节实现细节手册（源码级说明、Lab 与端到端时序）。
\\end{abstract}"""
if old_begin in t:
    t = t.replace(old_begin, new_begin)

# TOC page break
t = t.replace("\\tableofcontents\n}", "\\tableofcontents\n\\newpage\n}")

# hyperref
t = t.replace(
    "pdfcreator={LaTeX via pandoc}}",
    "pdftitle={Claude Code Hermes Agent Guide}, pdfauthor={LLM-Study}, pdfcreator={LaTeX via pandoc}}",
)

# Fix duplicate longtable package line
t = t.replace("\\usepackage{longtable,booktabs,array}\n", "")

# lstset black! fix - remove if pandoc regenerates broken lstset
t = t.replace("backgroundcolor=\\color{black!3}", "backgroundcolor=\\color[RGB]{248,248,248}")

tex.write_text(t, encoding="utf-8")
print("Preamble patched.")
PY

echo "==> XeLaTeX x2"
xelatex -interaction=nonstopmode "$TEX" >/dev/null
xelatex -interaction=nonstopmode "$TEX" >/dev/null

echo "==> Done: claude_and_hermes_agent_guide.pdf ($(pdfinfo "$TEX".pdf 2>/dev/null | grep Pages | awk '{print $2}' || echo '?') pages)"
