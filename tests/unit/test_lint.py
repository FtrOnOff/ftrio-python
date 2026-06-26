"""Port of ToggleAnalyzerTests.cs: ``ftrio lint`` flags unconfigured toggles."""

from __future__ import annotations

from pathlib import Path

from ftrio.cli import DIAGNOSTIC_ID, lint_path, main

_TOGGLE_SOURCE_WITH_MATCHING_KEY = """
from ftrio import toggle


@toggle
def my_method():
    pass
"""

_TOGGLE_SOURCE_MISSING_FROM_CONFIG = """
from ftrio import toggle


@toggle
def my_method():
    pass
"""

_METHOD_WITHOUT_TOGGLE = """
def my_method():
    pass
"""

_MULTIPLE_TOGGLES = """
from ftrio import toggle


@toggle
def present_method():
    pass


@toggle
def missing_method():
    pass
"""


def _write_project(tmp_path: Path, source: str, appsettings: str | None) -> Path:
    (tmp_path / "module.py").write_text(source, encoding="utf-8")
    if appsettings is not None:
        (tmp_path / "appsettings.json").write_text(appsettings, encoding="utf-8")
    return tmp_path


def test_toggle_method_with_matching_config_key_reports_no_diagnostic(tmp_path):
    project = _write_project(
        tmp_path, _TOGGLE_SOURCE_WITH_MATCHING_KEY, '{"Toggles": {"my_method": true}}'
    )
    assert lint_path(project) == []


def test_toggle_method_missing_from_config_reports_finding(tmp_path):
    project = _write_project(tmp_path, _TOGGLE_SOURCE_MISSING_FROM_CONFIG, '{"Toggles": {}}')
    findings = lint_path(project)
    assert len(findings) == 1
    assert findings[0].function_name == "my_method"


def test_method_without_toggle_reports_no_diagnostic_even_if_missing(tmp_path):
    project = _write_project(tmp_path, _METHOD_WITHOUT_TOGGLE, '{"Toggles": {}}')
    assert lint_path(project) == []


def test_no_appsettings_registered_reports_no_diagnostic(tmp_path):
    project = _write_project(tmp_path, _TOGGLE_SOURCE_MISSING_FROM_CONFIG, appsettings=None)
    assert lint_path(project) == []


def test_multiple_toggle_methods_reports_only_missing_ones(tmp_path):
    project = _write_project(
        tmp_path, _MULTIPLE_TOGGLES, '{"Toggles": {"present_method": true}}'
    )
    findings = lint_path(project)
    assert len(findings) == 1
    assert findings[0].function_name == "missing_method"
    assert "missing_method" in findings[0].format_message()


def test_explicit_key_decorator_is_resolved(tmp_path):
    source = """
from ftrio import toggle


@toggle("ConfiguredKey")
def some_function():
    pass
"""
    project = _write_project(tmp_path, source, '{"Toggles": {"ConfiguredKey": true}}')
    assert lint_path(project) == []


def test_explicit_key_decorator_missing_is_flagged(tmp_path):
    source = """
from ftrio import toggle


@toggle("MissingKey")
def some_function():
    pass
"""
    project = _write_project(tmp_path, source, '{"Toggles": {}}')
    findings = lint_path(project)
    assert len(findings) == 1
    assert findings[0].toggle_key == "MissingKey"


def test_cli_main_exits_non_zero_on_findings(tmp_path, capsys):
    _write_project(tmp_path, _TOGGLE_SOURCE_MISSING_FROM_CONFIG, '{"Toggles": {}}')
    exit_code = main(["lint", str(tmp_path)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert DIAGNOSTIC_ID in captured.out


def test_cli_main_exits_zero_when_all_present(tmp_path, capsys):
    _write_project(
        tmp_path, _TOGGLE_SOURCE_WITH_MATCHING_KEY, '{"Toggles": {"my_method": true}}'
    )
    exit_code = main(["lint", str(tmp_path)])
    assert exit_code == 0


# ── Exclusions ───────────────────────────────────────────────────────────────


def test_lint_path_excludes_named_directory(tmp_path):
    (tmp_path / "appsettings.json").write_text('{"Toggles": {}}', encoding="utf-8")
    excluded_dir = tmp_path / "tests"
    excluded_dir.mkdir()
    (excluded_dir / "fixtures.py").write_text(
        _TOGGLE_SOURCE_MISSING_FROM_CONFIG, encoding="utf-8"
    )
    # Without an exclude the decorated-but-unconfigured fixture is flagged...
    assert len(lint_path(tmp_path)) == 1
    # ...and excluding the directory suppresses it.
    assert lint_path(tmp_path, exclude_patterns=["tests"]) == []


def test_lint_path_excludes_file_glob(tmp_path):
    (tmp_path / "appsettings.json").write_text('{"Toggles": {}}', encoding="utf-8")
    (tmp_path / "keep.py").write_text(_TOGGLE_SOURCE_MISSING_FROM_CONFIG, encoding="utf-8")
    (tmp_path / "skip_async.py").write_text(
        _TOGGLE_SOURCE_MISSING_FROM_CONFIG, encoding="utf-8"
    )
    findings = lint_path(tmp_path, exclude_patterns=["*_async.py"])
    flagged_files = {Path(finding.file_path).name for finding in findings}
    assert flagged_files == {"keep.py"}


def test_lint_path_excludes_nested_directory_path(tmp_path):
    (tmp_path / "appsettings.json").write_text('{"Toggles": {}}', encoding="utf-8")
    nested = tmp_path / "tests" / "integration"
    nested.mkdir(parents=True)
    (nested / "mod.py").write_text(_TOGGLE_SOURCE_MISSING_FROM_CONFIG, encoding="utf-8")
    assert lint_path(tmp_path, exclude_patterns=["tests/integration"]) == []


def test_cli_default_excludes_skip_virtualenv(tmp_path, capsys):
    # A decorated-but-unconfigured function inside a .venv-like directory must not
    # be flagged: dependencies live there and are not project code.
    (tmp_path / "appsettings.json").write_text('{"Toggles": {}}', encoding="utf-8")
    venv_package = tmp_path / ".venv" / "lib" / "site-packages" / "thirdparty"
    venv_package.mkdir(parents=True)
    (venv_package / "mod.py").write_text(_TOGGLE_SOURCE_MISSING_FROM_CONFIG, encoding="utf-8")
    exit_code = main(["lint", str(tmp_path)])
    assert exit_code == 0


def test_cli_exclude_flag_suppresses_directory(tmp_path, capsys):
    (tmp_path / "appsettings.json").write_text('{"Toggles": {}}', encoding="utf-8")
    excluded_dir = tmp_path / "tests"
    excluded_dir.mkdir()
    (excluded_dir / "fixtures.py").write_text(
        _TOGGLE_SOURCE_MISSING_FROM_CONFIG, encoding="utf-8"
    )
    assert main(["lint", str(tmp_path)]) == 1  # flagged without exclude
    assert main(["lint", str(tmp_path), "--exclude", "tests"]) == 0  # suppressed


def test_cli_exclude_flag_accepts_comma_separated_list(tmp_path):
    (tmp_path / "appsettings.json").write_text('{"Toggles": {}}', encoding="utf-8")
    for directory_name in ("tests", "scratch"):
        directory = tmp_path / directory_name
        directory.mkdir()
        (directory / "mod.py").write_text(
            _TOGGLE_SOURCE_MISSING_FROM_CONFIG, encoding="utf-8"
        )
    assert main(["lint", str(tmp_path), "--exclude", "tests,scratch"]) == 0
