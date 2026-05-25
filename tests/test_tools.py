"""Tests for individual tools."""
from __future__ import annotations

import subprocess
import sys

import pytest

from src.tools.calculator import calculate
from src.tools.read_file import read_file
from src.tools.http_get import http_get
from src.tools.python_repl import python_repl
from src.tools.base import ToolResult


# ── Calculator tests ──────────────────────────────────────────

class TestCalculator:
    def test_basic_addition(self):
        result = calculate("2 + 3")
        assert result.success is True
        assert result.output == "5"

    def test_multiplication(self):
        result = calculate("7 * 6")
        assert result.success is True
        assert result.output == "42"

    def test_complex_expression(self):
        result = calculate("(10 + 5) * 2 / 3")
        assert result.success is True
        assert float(result.output) == pytest.approx(10.0)

    def test_exponentiation(self):
        result = calculate("2 ** 10")
        assert result.success is True
        assert result.output == "1024"

    def test_negative_numbers(self):
        result = calculate("-5 + 3")
        assert result.success is True
        assert result.output == "-2"

    def test_division_by_zero(self):
        result = calculate("10 / 0")
        assert result.success is False
        assert "zero" in result.error.lower()

    def test_rejects_function_calls(self):
        result = calculate("__import__('os').system('ls')")
        assert result.success is False

    def test_rejects_variable_names(self):
        result = calculate("x + 1")
        assert result.success is False

    def test_rejects_string_literals(self):
        result = calculate("'hello' * 3")
        assert result.success is False

    def test_large_exponent_rejected(self):
        result = calculate("2 ** 10000")
        assert result.success is False
        assert "too large" in result.error.lower() or "overflow" in result.error.lower()

    def test_floor_division(self):
        result = calculate("7 // 2")
        assert result.success is True
        assert result.output == "3"

    def test_modulo(self):
        result = calculate("10 % 3")
        assert result.success is True
        assert result.output == "1"


# ── HTTP GET tests ────────────────────────────────────────────

class TestHttpGet:
    def test_rejects_file_scheme(self):
        result = http_get("file:///etc/passwd")
        assert result.success is False
        assert "scheme" in result.error.lower()

    def test_rejects_ftp_scheme(self):
        result = http_get("ftp://example.com/file")
        assert result.success is False
        assert "scheme" in result.error.lower()

    def test_rejects_no_host(self):
        result = http_get("http://")
        assert result.success is False

    def test_rejects_empty_scheme(self):
        result = http_get("not-a-url")
        assert result.success is False


# ── Read File tests ───────────────────────────────────────────

class TestReadFile:
    def test_sandbox_escape_dotdot(self, tmp_path, monkeypatch):
        """Attempting to traverse outside sandbox should fail."""
        # Create a sandbox with a file
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        (tmp_path / "secret.txt").write_text("secret data")

        # Patch config to use our tmp sandbox
        from src.config import AppConfig, LLMConfig, AgentConfig, ToolsConfig, ReadFileToolConfig, PythonReplToolConfig
        import src.config as config_mod

        config_mod._config = AppConfig(
            tools=ToolsConfig(read_file=ReadFileToolConfig(sandbox_dir=str(sandbox)))
        )

        result = read_file("../secret.txt")
        assert result.success is False
        assert "outside" in result.error.lower() or "denied" in result.error.lower()

        # Cleanup
        config_mod._config = None

    def test_read_existing_file(self, tmp_path, monkeypatch):
        """Should read a file within the sandbox."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        (sandbox / "test.txt").write_text("hello world")

        from src.config import AppConfig, ToolsConfig, ReadFileToolConfig
        import src.config as config_mod

        config_mod._config = AppConfig(
            tools=ToolsConfig(read_file=ReadFileToolConfig(sandbox_dir=str(sandbox)))
        )

        result = read_file("test.txt")
        assert result.success is True
        assert result.output == "hello world"

        config_mod._config = None

    def test_file_not_found(self, tmp_path):
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()

        from src.config import AppConfig, ToolsConfig, ReadFileToolConfig
        import src.config as config_mod

        config_mod._config = AppConfig(
            tools=ToolsConfig(read_file=ReadFileToolConfig(sandbox_dir=str(sandbox)))
        )

        result = read_file("nonexistent.txt")
        assert result.success is False
        assert "not found" in result.error.lower()

        config_mod._config = None


# ── Python REPL tests ─────────────────────────────────────────

class TestPythonRepl:
    def test_simple_print(self):
        result = python_repl("print(2 + 2)")
        assert result.success is True
        assert "4" in result.output

    def test_syntax_error(self):
        result = python_repl("def")
        assert result.success is False
        assert result.error is not None

    def test_runtime_error(self):
        result = python_repl("1/0")
        assert result.success is False
        assert "ZeroDivision" in result.error


# ── Read Skill tests ──────────────────────────────────────────

class TestReadSkill:
    def test_read_pdf_skill(self):
        from src.tools.read_skill import read_skill
        result = read_skill("pdf")
        assert result.success is True
        assert "reportlab" in result.output
        assert "Color Palette" in result.output

    def test_read_pptx_skill(self):
        from src.tools.read_skill import read_skill
        result = read_skill("pptx")
        assert result.success is True
        assert "python-pptx" in result.output
        assert "Midnight Executive" in result.output

    def test_read_docx_skill(self):
        from src.tools.read_skill import read_skill
        result = read_skill("docx")
        assert result.success is True
        assert "python-docx" in result.output
        assert "Arial" in result.output

    def test_invalid_skill(self):
        from src.tools.read_skill import read_skill
        result = read_skill("xlsx")
        assert result.success is False
        assert "Unknown skill" in result.error

    def test_case_insensitive(self):
        from src.tools.read_skill import read_skill
        result = read_skill("PDF")
        assert result.success is True
        assert "reportlab" in result.output
