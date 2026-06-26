"""Guards the single-source version wiring.

``ftrio.__version__`` must be derived from the installed package metadata (whose
source of truth is ``pyproject.toml``), not a hardcoded literal that could drift.
"""

from __future__ import annotations

from importlib.metadata import version as installed_version

import ftrio


def test_version_is_exposed_and_non_empty():
    assert isinstance(ftrio.__version__, str)
    assert ftrio.__version__


def test_version_matches_installed_package_metadata():
    # If someone replaces the derived __version__ with a hardcoded literal, this
    # breaks the moment pyproject.toml is bumped without editing the literal.
    assert ftrio.__version__ == installed_version("ftrio")


def test_version_is_not_the_uninstalled_fallback():
    # The fallback is only for running from a source tree with no install; the test
    # suite always runs against an installed package, so it must never appear here.
    assert ftrio.__version__ != "0.0.0+unknown"
