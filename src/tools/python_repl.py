from __future__ import annotations

import re
import subprocess
import sys

from .base import ToolResult
from ..config import get_config

# ── Security: Code blocklist ─────────────────────────────────────────────────
# Patterns that indicate dangerous operations. Checked BEFORE execution.

_BLOCKED_PATTERNS: list[tuple[str, str]] = [
    # OS-level command execution
    (r"\bos\s*\.\s*system\s*\(", "os.system() is blocked"),
    (r"\bos\s*\.\s*popen\s*\(", "os.popen() is blocked"),
    (r"\bos\s*\.\s*exec\w*\s*\(", "os.exec*() is blocked"),
    (r"\bos\s*\.\s*spawn\w*\s*\(", "os.spawn*() is blocked"),
    (r"\bos\s*\.\s*remove\s*\(", "os.remove() is blocked — use data dir only"),
    (r"\bos\s*\.\s*rmdir\s*\(", "os.rmdir() is blocked"),
    (r"\bos\s*\.\s*unlink\s*\(", "os.unlink() is blocked"),
    (r"\bos\s*\.\s*rename\s*\(", "os.rename() is blocked"),
    (r"\bshutil\s*\.\s*rmtree\s*\(", "shutil.rmtree() is blocked"),
    (r"\bshutil\s*\.\s*move\s*\(", "shutil.move() is blocked"),
    # Dynamic code execution
    (r"\b__import__\s*\(", "__import__() is blocked"),
    (r"\bimportlib", "importlib is blocked"),
    (r"\bcompile\s*\(", "compile() is blocked"),
    # Dangerous modules
    (r"\bimport\s+os\b", "import os is blocked — use pathlib for ./data/ paths"),
    (r"\bfrom\s+os\b", "from os is blocked"),
    (r"\bimport\s+shutil\b", "import shutil is blocked"),
    (r"\bimport\s+socket\b", "import socket is blocked"),
    (r"\bfrom\s+socket\b", "from socket is blocked"),
    (r"\bimport\s+ctypes\b", "import ctypes is blocked"),
    (r"\bimport\s+webbrowser\b", "import webbrowser is blocked"),
    (r"\bimport\s+smtplib\b", "import smtplib is blocked"),
    (r"\bimport\s+ftplib\b", "import ftplib is blocked"),
    (r"\bimport\s+telnetlib\b", "import telnetlib is blocked"),
    (r"\bhttp\.server\b", "http.server is blocked"),
    (r"\bsocketserver\b", "socketserver is blocked"),
    # Network access
    (r"\burllib\.request\b", "urllib.request is blocked"),
    (r"\brequests\.(get|post|put|delete|patch)\b", "requests library network calls are blocked"),
    (r"\bhttpx\.(get|post|put|delete|patch|Client|AsyncClient)\b", "httpx network calls are blocked"),
    # Subprocess (except pip install which is handled separately)
    (r"\bsubprocess\b", "subprocess is blocked — use pip_install allowlist instead"),
]

# ── Security: Pip install allowlist ──────────────────────────────────────────
# Only these packages may be installed at runtime.

PIP_ALLOWLIST: set[str] = {
    "reportlab", "python-pptx", "python-docx", "openpyxl",
    "matplotlib", "pandas", "numpy", "seaborn", "plotly",
    "xlsxwriter", "Pillow", "scipy", "tabulate", "jinja2",
    "wordcloud", "pdfkit", "markdown", "pygments", "sympy",
}

_PIP_INSTALL_RE = re.compile(
    r"""(?:pip\s+install|pip3\s+install|['"]pip['"],\s*['"]install['"])[\s,]+['"]?([a-zA-Z0-9_\-]+)""",
    re.IGNORECASE,
)


def _validate_code(code: str) -> str | None:
    """Check code against blocklist. Returns error message if blocked, None if OK."""
    # Check for pip install of non-allowlisted packages
    pip_matches = _PIP_INSTALL_RE.findall(code)
    for pkg in pip_matches:
        pkg_normalized = pkg.lower().replace("-", "_").replace(".", "_")
        allowlist_normalized = {p.lower().replace("-", "_").replace(".", "_") for p in PIP_ALLOWLIST}
        if pkg_normalized not in allowlist_normalized:
            return (
                f"Package '{pkg}' is not in the allowlist. "
                f"Allowed packages: {', '.join(sorted(PIP_ALLOWLIST))}"
            )
        # If it's an allowed pip install, skip the subprocess block for this code
        return None

    # Check blocked patterns
    for pattern, message in _BLOCKED_PATTERNS:
        if re.search(pattern, code):
            return f"BLOCKED: {message}"

    return None


def python_repl(code: str) -> ToolResult:
    """Execute Python code in a subprocess with a timeout.

    Returns stdout on success or stderr on failure.
    Security: code is scanned for dangerous patterns before execution.
    """
    # ── Security validation ──
    violation = _validate_code(code)
    if violation:
        return ToolResult(success=False, output="", error=violation)

    cfg = get_config()
    timeout = cfg.tools.python_repl.timeout_seconds

    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            output = result.stdout.strip() or "(no output)"
            return ToolResult(success=True, output=output)
        else:
            error_msg = result.stderr.strip() or f"Process exited with code {result.returncode}"
            return ToolResult(success=False, output="", error=error_msg)

    except subprocess.TimeoutExpired:
        return ToolResult(
            success=False,
            output="",
            error=f"Execution timed out after {timeout} seconds.",
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=f"Execution failed: {e}")
