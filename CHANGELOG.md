# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2026-07-08

A patch release completing case-insensitive key handling across every
configuration source, so keys resolve the same on every platform.

### Fixed

- **Config keys are now matched case-insensitively.**
  `AppSettingsConfiguration.get_value` resolves colon-path keys regardless of
  case (e.g. `Toggles:newcheckout` finds `Toggles:NewCheckout`), mirroring
  `Microsoft.Extensions.Configuration`'s `OrdinalIgnoreCase` comparer. An exact
  match is still preferred as a fast path.
- **Environment-variable buffer mode now works on Windows.**
  `EnvironmentVariableToggleParser` matched its prefix case-sensitively, but
  Windows uppercases env-var names at the OS boundary
  (`FTRIO__Toggles__BufA` becomes `FTRIO__TOGGLES__BUFA`), so buffer mode staged
  nothing there. The prefix is now matched case-insensitively; the extracted key
  keeps the OS-provided case, which is harmless because toggle keys are compared
  case-insensitively throughout. Standalone mode was already correct and is
  unchanged.

### Internal

- Added a hidden `conformance-resolve` CLI command (help suppressed, not
  user-facing) that reads one resolution case as JSON on stdin and prints the
  outcome as JSON, letting the cross-language `ftrio-conformance` matrix exercise
  the port's real resolution logic.

### Notes

No API or behavioural changes for correctly-cased keys; existing configurations
continue to work unchanged. This is the environment/OS counterpart to the
JSON-side config fix, making key handling consistently case-insensitive across
every source on every platform.

## [1.0.0] - 2026-06-26

Initial release: a faithful Python port of the .NET
[FtrIO](https://github.com/FtrOnOff/FtrIO) feature-toggle library.

### Added

- **Decorators**: `@toggle` and `@toggle_async` gate a function by its own name;
  off-path returns `None` (sync) or an awaitable resolving to `None` (async).
- **Explicit API**: `FeatureToggle` with `execute_method_if_toggle_on` /
  `execute_method_if_toggle_on_async` and `get_toggle_state`.
- **Strategies**: `BooleanStrategy` (always-appended fallback),
  `PercentageRolloutStrategy`, `UserTargetingStrategy`, `AttributeRuleStrategy`
  (seven operators), `ABTestStrategy` (deterministic per-user bucketing, with the
  bucket hash matching the .NET implementation byte-for-byte), and
  `BlueGreenStrategy`.
- **Parsers**: `AppSettingsToggleParser`, `StrategyToggleParser` (first-match
  strategy selection, override precedence), `EnvironmentVariableToggleParser`
  (standalone and buffer modes), and `CompositeToggleParser` (first-wins
  fallthrough).
- **Buffer + providers**: `ToggleProviderBuffer` (atomic, coalescing flush to
  appsettings.json), `HttpToggleParser` (stdlib `urllib`), and
  `AzureAppConfigToggleParser` (optional `ftrio[azure]` extra).
- **Configuration**: `appsettings.json` loading with colon-path access, the
  environment overlay, and reload-on-change, replicating the .NET
  `IConfiguration` behaviour using only the standard library.
- **Per-user overrides**: `TogglesOverrides` resolved via `OverrideResolver`,
  checked before any strategy.
- **`ftrio lint` CLI**: static-analysis substitute for the Roslyn analyzer
  (`FTRIO001`), with `--exclude` glob patterns, sensible default excludes
  (`.venv`, `.git`, build output, caches), `--no-default-excludes`, and
  `-v/--verbose`.
- **Logging**: standard-library `logging` throughout, silent by default via a
  package `NullHandler`, redirectable and level-controllable per component.
- **Playground**: `python -m playground` live demo honouring reload-on-change.
- **Tooling**: PEP 8 enforced via `ruff` (including `pep8-naming`), `mypy` clean
  on the public surface, and a `pytest` suite covering every behaviour the .NET
  NUnit suite proves.
- **Packaging**: `pyproject.toml` with stdlib-only core, `ftrio[azure]` and
  `ftrio[dev]` extras, and the `ftrio` console entry point.

### Notes

This is a port-first release. Toggle keys follow the host language's
method-naming convention (snake_case keys derived from snake_case method names),
and exception classes use the Python-canonical `*Error` suffix. See
[PORTING_NOTES.md](PORTING_NOTES.md) for every deviation from a literal 1:1 port.

[Unreleased]: https://github.com/FtrOnOff/ftrio-python/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/FtrOnOff/ftrio-python/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/FtrOnOff/ftrio-python/releases/tag/v1.0.0
