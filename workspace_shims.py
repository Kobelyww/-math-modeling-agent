"""Load the workspace compatibility shims explicitly.

Some Python distributions already provide their own `sitecustomize.py`, so the
workspace-level one is not guaranteed to auto-load. Importing this module loads
the local shim file by absolute path and caches it for the current process.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


_MODULE_NAME = "_llm_study_sitecustomize"


if _MODULE_NAME not in sys.modules:
    shim_path = Path(__file__).with_name("sitecustomize.py")
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, shim_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load workspace shims from {shim_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
