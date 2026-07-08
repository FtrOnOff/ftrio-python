"""``ftrio lint``: static analysis substitute for the Roslyn analyzer.

The .NET source ships a ``DiagnosticAnalyzer`` (FTRIO001) that runs inside the
compiler and flags any ``[Toggle]``-decorated method whose key is missing from
the ``Toggles`` section of appsettings.json. Python has no in-compiler analyzer,
so the faithful substitute is a build-time CLI: it walks the project with the
``ast`` module, finds ``@toggle`` / ``@toggle_async`` functions, resolves each
key, and reports any that are missing from appsettings.json. It exits non-zero on
findings so CI can gate on it, mirroring the analyzer's ``Error`` severity.

See PORTING_NOTES.md for why this is build-time-via-CLI rather than in-compiler.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import logging
import os
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

DIAGNOSTIC_ID = "FTRIO001"
_TOGGLE_DECORATOR_NAMES = ("toggle", "toggle_async")
_logger = logging.getLogger("ftrio.lint")

# Non-project directories that should never be scanned: virtualenvs (where
# third-party packages live), version control, build output, and tool caches.
# This mirrors the default-exclude behaviour of linters like ruff and flake8 so
# that ``ftrio lint .`` does not descend into ``.venv`` and analyse dependencies.
_DEFAULT_EXCLUDES: tuple[str, ...] = (
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".nox",
    "build",
    "dist",
    "*.egg-info",
    "node_modules",
)


@dataclass(frozen=True)
class ToggleFinding:
    """A single decorated function whose key is absent from configuration."""

    function_name: str
    toggle_key: str
    file_path: str
    line_number: int

    def format_message(self) -> str:
        """Render the diagnostic, preserving the .NET message wording intent."""
        return (
            f"{self.file_path}:{self.line_number}: {DIAGNOSTIC_ID}: "
            f"Function '{self.function_name}' is decorated with @toggle but has no "
            f"entry in the Toggles section of appsettings.json"
        )


def _decorator_toggle_key(
    decorator: ast.expr, function_name: str
) -> str | None:
    """Return the toggle key if ``decorator`` is a toggle decorator, else ``None``.

    Handles ``@toggle``, ``@toggle_async``, ``@toggle("Key")``, and the
    module-qualified forms (``@ftrio.toggle`` etc.). A bare decorator resolves to
    the function's own name, matching the runtime key-defaulting behaviour.
    """
    # Bare decorator: @toggle or @ftrio.toggle
    if isinstance(decorator, ast.Name) and decorator.id in _TOGGLE_DECORATOR_NAMES:
        return function_name
    if isinstance(decorator, ast.Attribute) and decorator.attr in _TOGGLE_DECORATOR_NAMES:
        return function_name

    # Called decorator: @toggle("Key") or @toggle()
    if isinstance(decorator, ast.Call):
        callee = decorator.func
        callee_name = (
            callee.id
            if isinstance(callee, ast.Name)
            else callee.attr
            if isinstance(callee, ast.Attribute)
            else None
        )
        if callee_name not in _TOGGLE_DECORATOR_NAMES:
            return None
        if decorator.args and isinstance(decorator.args[0], ast.Constant):
            constant_value = decorator.args[0].value
            if isinstance(constant_value, str):
                return constant_value
        return function_name

    return None


def find_decorated_toggle_keys(source_path: Path) -> list[tuple[str, str, int]]:
    """Return ``(function_name, toggle_key, line_number)`` for each decorated function."""
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return []

    results: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            toggle_key = _decorator_toggle_key(decorator, node.name)
            if toggle_key is not None:
                results.append((node.name, toggle_key, node.lineno))
                break
    return results


def load_configured_toggle_keys(appsettings_path: Path) -> set[str]:
    """Return the set of keys in the ``Toggles`` section of appsettings.json."""
    if not appsettings_path.is_file():
        return set()
    try:
        document = json.loads(appsettings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    toggles_section = document.get("Toggles")
    if not isinstance(toggles_section, dict):
        return set()
    return set(toggles_section.keys())


def lint_path(
    project_path: Path, exclude_patterns: Iterable[str] = ()
) -> list[ToggleFinding]:
    """Walk ``project_path`` and return findings for unconfigured toggle keys.

    ``exclude_patterns`` are glob patterns (matched against each path component and
    against the path relative to ``project_path``) naming files or directories to
    skip. Mirrors the analyzer's skip-when-no-config behaviour: if no
    appsettings.json is found, the runtime treats everything as on, so no findings
    are produced.
    """
    patterns = tuple(exclude_patterns)
    appsettings_path = _locate_appsettings(project_path, patterns)
    if appsettings_path is None:
        # No appsettings.json registered: the runtime treats everything as on,
        # so there is nothing to flag (matches the analyzer's early return).
        return []

    configured_keys = load_configured_toggle_keys(appsettings_path)

    findings: list[ToggleFinding] = []
    for python_file in _iter_python_files(project_path, patterns):
        for function_name, toggle_key, line_number in find_decorated_toggle_keys(python_file):
            if toggle_key not in configured_keys:
                findings.append(
                    ToggleFinding(
                        function_name=function_name,
                        toggle_key=toggle_key,
                        file_path=str(python_file),
                        line_number=line_number,
                    )
                )
    return findings


def _is_excluded(path: Path, root: Path, patterns: tuple[str, ...]) -> bool:
    """Return whether ``path`` matches any exclude pattern.

    A pattern matches if it globs the path relative to ``root`` (POSIX form) or any
    single component of that relative path. So ``tests`` excludes the whole ``tests``
    directory, ``*_async.py`` excludes by filename, and ``tests/integration`` excludes
    that nested directory.
    """
    if not patterns:
        return False
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        relative = path.as_posix()
    components = relative.split("/")
    for pattern in patterns:
        if fnmatch.fnmatch(relative, pattern):
            return True
        if any(fnmatch.fnmatch(component, pattern) for component in components):
            return True
    return False


def _locate_appsettings(project_path: Path, patterns: tuple[str, ...] = ()) -> Path | None:
    """Find the nearest ``appsettings.json`` for the linted path, skipping excludes."""
    if project_path.is_file():
        candidate = project_path.parent / "appsettings.json"
        return candidate if candidate.is_file() else None

    direct = project_path / "appsettings.json"
    if direct.is_file():
        return direct
    for candidate in sorted(project_path.rglob("appsettings.json")):
        if not _is_excluded(candidate, project_path, patterns):
            return candidate
    return None


def _iter_python_files(
    project_path: Path, patterns: tuple[str, ...] = ()
) -> Iterator[Path]:
    """Yield Python source files under ``project_path``, pruning excluded directories.

    Directories matching an exclude pattern are pruned during the walk (so a large
    ``.venv`` is never descended into), and files matching a pattern are skipped.
    """
    if project_path.is_file():
        if project_path.suffix == ".py" and not _is_excluded(
            project_path, project_path, patterns
        ):
            yield project_path
        return

    for directory_path, directory_names, file_names in os.walk(project_path):
        current_directory = Path(directory_path)
        # Prune excluded directories in place so os.walk does not descend into them.
        directory_names[:] = [
            directory_name
            for directory_name in directory_names
            if not _is_excluded(current_directory / directory_name, project_path, patterns)
        ]
        for file_name in sorted(file_names):
            if not file_name.endswith(".py"):
                continue
            file_path = current_directory / file_name
            if not _is_excluded(file_path, project_path, patterns):
                yield file_path


def _resolve_exclude_patterns(
    user_excludes: Iterable[str], use_default_excludes: bool
) -> tuple[str, ...]:
    """Flatten comma-separated ``--exclude`` values and add the defaults if enabled."""
    patterns: list[str] = []
    for raw_value in user_excludes:
        patterns.extend(part.strip() for part in raw_value.split(",") if part.strip())
    if use_default_excludes:
        patterns.extend(_DEFAULT_EXCLUDES)
    return tuple(patterns)


def _conformance_resolve() -> int:
    """Read one conformance resolution case as JSON on stdin, print the outcome as JSON.

    The counterpart of the Rust CLI's ``conformance-resolve``: it lets the language-agnostic driver
    exercise the port's real resolution logic across languages. Output is ``{"result": true}`` /
    ``{"result": false}`` for a decision, or ``{"error": "DoesNotExist"}`` (etc.) for a named error.
    """
    import os
    import tempfile

    from .builder import ToggleParserBuilder
    from .context import FtrIOContextAccessor
    from .exceptions import (
        ToggleAttributeMissingError,
        ToggleDoesNotExistError,
        ToggleParsedOutOfRangeError,
    )

    class _CaseContext(FtrIOContextAccessor):
        def __init__(self, user_id, attributes):
            self._user_id = user_id
            self._attributes = attributes or {}

        def get_user_id(self):
            return self._user_id

        def get_attribute(self, attribute_name):
            return self._attributes.get(attribute_name)

    try:
        case = json.loads(sys.stdin.read())
    except json.JSONDecodeError as error:
        print(f"conformance-resolve: invalid JSON on stdin: {error}", file=sys.stderr)
        return 2

    context = case.get("context") or {}
    accessor = _CaseContext(context.get("userId"), context.get("attributes"))

    previous_cwd = os.getcwd()
    with tempfile.TemporaryDirectory(prefix="ftrio_cr_") as directory:
        if case.get("config") is not None:
            (Path(directory) / "appsettings.json").write_text(
                json.dumps(case["config"], indent=2), encoding="utf-8"
            )
        os.chdir(directory)
        try:
            parser = (
                ToggleParserBuilder()
                .with_percentage_rollout()
                .with_blue_green()
                .with_context_strategies(accessor)
                .with_overrides()
                .build()
            )
            try:
                outcome = {"result": parser.get_toggle_status(case["toggleKey"])}
            except ToggleDoesNotExistError:
                outcome = {"error": "DoesNotExist"}
            except ToggleParsedOutOfRangeError:
                outcome = {"error": "ParsedOutOfRange"}
            except ToggleAttributeMissingError:
                outcome = {"error": "AttributeMissing"}
        finally:
            os.chdir(previous_cwd)

    print(json.dumps(outcome))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a non-zero exit code when findings exist."""
    parser = argparse.ArgumentParser(
        prog="ftrio",
        description="FtrIO static analysis: verify every @toggle key is configured.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    lint_parser = subparsers.add_parser(
        "lint", help="Check that every @toggle-decorated function has a Toggles key."
    )
    lint_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="File or directory to lint (defaults to the current directory).",
    )
    lint_parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help=(
            "Glob pattern of files or directories to skip. Repeatable, and also "
            "accepts a comma-separated list. Matched against each path component "
            'and the relative path, e.g. --exclude tests --exclude "*_async.py".'
        ),
    )
    lint_parser.add_argument(
        "--no-default-excludes",
        action="store_true",
        help=(
            "Do not skip the built-in non-project directories "
            "(.venv, .git, build, dist, caches, ...). They are skipped by default."
        ),
    )
    lint_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Emit FtrIO debug logging (to stderr) describing what is being scanned.",
    )

    # Hidden hook for the ftrio-conformance cross-port matrix driver: read one resolution case as
    # JSON on stdin, print the outcome as JSON on stdout. Not a user-facing command.
    subparsers.add_parser(
        "conformance-resolve",
        help=argparse.SUPPRESS,
    )

    arguments = parser.parse_args(argv)

    if arguments.command == "conformance-resolve":
        return _conformance_resolve()

    # Verbosity is managed through the logging module: -v turns on debug output
    # for the whole FtrIO logger tree, which the operator can further redirect to
    # a file or filter per component using standard logging configuration.
    if getattr(arguments, "verbose", False):
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
        logging.getLogger("ftrio").setLevel(logging.DEBUG)

    if arguments.command == "lint":
        target_path = Path(arguments.path)
        exclude_patterns = _resolve_exclude_patterns(
            arguments.exclude, use_default_excludes=not arguments.no_default_excludes
        )
        _logger.debug(
            "Linting %s for unconfigured @toggle keys (excludes: %s).",
            target_path,
            ", ".join(exclude_patterns) or "none",
        )
        findings = lint_path(target_path, exclude_patterns)
        for finding in findings:
            print(finding.format_message())
        if findings:
            print(f"\n{len(findings)} toggle(s) missing from appsettings.json.")
            return 1
        print("All @toggle keys are present in appsettings.json.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
