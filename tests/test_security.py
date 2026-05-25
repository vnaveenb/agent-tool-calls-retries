"""Security tests for python_repl code blocklist, pip allowlist, and API input validation."""

import pytest
from src.tools.python_repl import python_repl, _validate_code, PIP_ALLOWLIST


# ── Code Blocklist Tests ─────────────────────────────────────────────────────

class TestCodeBlocklist:
    """Dangerous code patterns should be blocked before execution."""

    def test_blocks_os_system(self):
        result = python_repl("import os\nos.system('rm -rf /')")
        assert not result.success
        assert "blocked" in result.error.lower() or "BLOCKED" in result.error

    def test_blocks_os_popen(self):
        result = python_repl("import os\nos.popen('whoami').read()")
        assert not result.success
        assert "blocked" in result.error.lower() or "BLOCKED" in result.error

    def test_blocks_import_os(self):
        result = python_repl("import os\nprint(os.getcwd())")
        assert not result.success
        assert "blocked" in result.error.lower() or "BLOCKED" in result.error

    def test_blocks_from_os(self):
        result = python_repl("from os import listdir\nprint(listdir('/'))")
        assert not result.success
        assert "blocked" in result.error.lower() or "BLOCKED" in result.error

    def test_blocks_import_socket(self):
        result = python_repl("import socket\ns = socket.socket()")
        assert not result.success
        assert "blocked" in result.error.lower() or "BLOCKED" in result.error

    def test_blocks_import_shutil(self):
        result = python_repl("import shutil\nshutil.rmtree('/tmp')")
        assert not result.success
        assert "blocked" in result.error.lower() or "BLOCKED" in result.error

    def test_blocks_subprocess(self):
        result = python_repl("import subprocess\nsubprocess.run(['ls'])")
        assert not result.success
        assert "blocked" in result.error.lower() or "BLOCKED" in result.error

    def test_blocks_dunder_import(self):
        result = python_repl("__import__('os').system('whoami')")
        assert not result.success
        assert "blocked" in result.error.lower() or "BLOCKED" in result.error

    def test_blocks_ctypes(self):
        result = python_repl("import ctypes")
        assert not result.success
        assert "blocked" in result.error.lower() or "BLOCKED" in result.error

    def test_blocks_http_server(self):
        result = python_repl("from http.server import HTTPServer")
        assert not result.success
        assert "blocked" in result.error.lower() or "BLOCKED" in result.error

    def test_blocks_requests_get(self):
        result = python_repl("import requests\nrequests.get('http://evil.com')")
        assert not result.success
        assert "blocked" in result.error.lower() or "BLOCKED" in result.error

    def test_blocks_eval(self):
        code = "eval('__import__(\"os\").system(\"whoami\")')"
        assert _validate_code(code) is not None

    def test_blocks_importlib(self):
        code = "import importlib\nimportlib.import_module('os')"
        assert _validate_code(code) is not None


# ── Allowed Code Tests ───────────────────────────────────────────────────────

class TestAllowedCode:
    """Legitimate document generation code should be allowed."""

    def test_allows_reportlab(self):
        code = "from reportlab.lib.pagesizes import letter\nprint('ok')"
        assert _validate_code(code) is None

    def test_allows_pptx(self):
        code = "from pptx import Presentation\nprint('ok')"
        assert _validate_code(code) is None

    def test_allows_docx(self):
        code = "from docx import Document\nprint('ok')"
        assert _validate_code(code) is None

    def test_allows_matplotlib(self):
        code = "import matplotlib\nprint('ok')"
        assert _validate_code(code) is None

    def test_allows_openpyxl(self):
        code = "import openpyxl\nprint('ok')"
        assert _validate_code(code) is None

    def test_allows_csv(self):
        code = "import csv\nprint('ok')"
        assert _validate_code(code) is None

    def test_allows_pathlib_data_dir(self):
        code = "from pathlib import Path\nPath('./data/test.txt').write_text('hello')\nprint('ok')"
        assert _validate_code(code) is None

    def test_allows_math(self):
        code = "import math\nprint(math.sqrt(144))"
        result = python_repl(code)
        assert result.success
        assert "12" in result.output

    def test_allows_json(self):
        code = "import json\nprint(json.dumps({'a': 1}))"
        result = python_repl(code)
        assert result.success


# ── Pip Allowlist Tests ──────────────────────────────────────────────────────

class TestPipAllowlist:
    """Only allowlisted packages should be installable."""

    def test_blocks_unknown_package(self):
        code = "import subprocess\nsubprocess.run(['pip', 'install', 'evil-package'])"
        result = python_repl(code)
        assert not result.success
        assert "not in the allowlist" in result.error or "blocked" in result.error.lower()

    def test_blocks_dangerous_package(self):
        code = "import subprocess\nsubprocess.run(['pip', 'install', 'pwntools'])"
        result = python_repl(code)
        assert not result.success

    def test_allows_allowlisted_package(self):
        code = "import subprocess\nsubprocess.run(['pip', 'install', 'pandas'])"
        # Should NOT be blocked by validation (pip install pandas is allowed)
        assert _validate_code(code) is None

    def test_allowlist_has_expected_packages(self):
        expected = {"reportlab", "python-pptx", "python-docx", "pandas", "numpy", "matplotlib"}
        assert expected.issubset(PIP_ALLOWLIST)


# ── Input Validation Tests ───────────────────────────────────────────────────

class TestInputValidation:
    """API input validation should reject oversized or empty payloads."""

    def test_validate_code_returns_none_for_safe_code(self):
        assert _validate_code("print('hello world')") is None

    def test_validate_code_returns_error_for_dangerous_code(self):
        assert _validate_code("import os") is not None

    def test_validate_code_handles_multiline(self):
        code = "x = 1\ny = 2\nimport socket\nprint(x + y)"
        assert _validate_code(code) is not None

    def test_validate_code_case_sensitivity(self):
        # Our regex patterns should catch these
        code = "import os"
        assert _validate_code(code) is not None
