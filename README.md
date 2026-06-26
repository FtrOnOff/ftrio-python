# FtrIO (Python)

Feature toggles for Python, ported faithfully from the .NET
[FtrIO](https://github.com/FtrOnOff/FtrIO) library. Decorate a method, add a key
to `appsettings.json`, and the method runs only when the toggle is on. Richer
decisions, percentage rollouts, A/B buckets, deployment slots, user and attribute
targeting, per-user overrides, are layered in through a strategy chain.

The core depends on the standard library only.

## Installation

```console
pip install ftrio
```

The core has no third-party dependencies. The Azure App Configuration provider
needs an optional extra:

```console
pip install "ftrio[azure]"
```

(Contributors working on FtrIO itself want the editable dev install instead; see
[Development](#development).)

## Quickstart

1. Decorate a method. The toggle key defaults to the method's own name.

   ```python
   from ftrio import toggle

   @toggle
   def send_welcome_email(user):
       ...  # runs only when the "send_welcome_email" toggle is on
   ```

2. Add a matching key to `appsettings.json` in your working directory:

   ```json
   {
       "Toggles": {
           "send_welcome_email": true
       }
   }
   ```

3. Call it normally. When the toggle is off, the call returns `None` without
   running the body (an async `@toggle_async` returns an awaitable resolving to
   `None`, so `await` is always safe).

If there is no `appsettings.json` on disk at all, every toggle reads on, a fresh
app stays fully functional before any config exists. A present file with a
missing key raises `ToggleDoesNotExistError`; a present key with an
uninterpretable value raises `ToggleParsedOutOfRangeError`.

## The builder pipeline

Plain `true`/`false` is the baseline. For richer decisions, build a parser and
install it as the ambient parser used by the decorators:

```python
from ftrio import ToggleParserProvider

ToggleParserProvider.configure_builder(lambda builder: builder
    .with_context_strategies(context_accessor)  # user targeting + attributes + A/B
    .with_percentage_rollout()                   # "20%"
    .with_blue_green()                           # "blue" / "green" from appsettings.json
    .with_overrides())                           # per-user TogglesOverrides, checked first
```

Strategies are tried in registration order; the first whose `can_handle` accepts
the raw value owns the decision. `BooleanStrategy` is always appended last, so
plain booleans keep working under any chain. Toggle value grammars:

| Value | Strategy | Meaning |
|---|---|---|
| `true` / `false` / `1` / `0` | Boolean | plain on/off |
| `20%` | PercentageRollout | on for ~20% of calls (random per call) |
| `blue` / `green` | BlueGreen | on when it names the active deployment slot |
| `users:alice,bob` | UserTargeting | on for the listed user ids |
| `attribute:plan equals premium` | AttributeRule | on when the rule matches the user's attribute |
| `ab:50` or `ab:50:salt` | ABTest | deterministic per-user 50% bucket |

A/B bucketing is stable: the same user, key (and salt) always bucket identically,
and identically to the .NET implementation (SHA-256, first four bytes as a
little-endian signed int, absolute value modulo 100).

Per-user overrides (`TogglesOverrides`) win unconditionally, before any strategy:

```json
{
    "Toggles": { "NewCheckout": "ab:50" },
    "TogglesOverrides": { "NewCheckout": { "alice": true } }
}
```

## Providers and the buffer model

External sources feed a `ToggleProviderBuffer`, which flushes staged values to
`appsettings.json` atomically on an interval. `appsettings.json` stays the on-disk
source of truth, so reads survive a provider going offline (fail-safe).

```python
from ftrio import ToggleProviderBuffer
from ftrio.providers import HttpToggleParser

buffer = ToggleProviderBuffer()
HttpToggleParser("https://flags.example.com/toggles", buffer)  # polls, stages, flushes
```

Available providers: `HttpToggleParser` (standard library), `EnvironmentVariableToggleParser`
(standalone or buffer mode), and `AzureAppConfigToggleParser` (needs the
`ftrio[azure]` extra). Each exposes `close()` and context-manager support.

`CompositeToggleParser` chains parsers with first-wins fallthrough, e.g. env-var
overrides, then a remote provider, then `appsettings.json` as the durable fallback.

## The `ftrio lint` CLI

The .NET library ships a Roslyn analyzer (diagnostic `FTRIO001`) that fails the
build when a `[Toggle]`-decorated method has no matching key in `appsettings.json`.
The Python equivalent is a CLI you can run in CI:

```console
$ ftrio lint path/to/project
path/to/project/mod.py:8: FTRIO001: Function 'MissingOne' is decorated with @toggle but has no entry in the Toggles section of appsettings.json

1 toggle(s) missing from appsettings.json.
```

It walks the tree with `ast`, resolves each `@toggle` / `@toggle_async` key, and
exits non-zero on findings so it can gate a pipeline.

Non-project directories (`.venv`, `.git`, `build`, `dist`, `__pycache__`, and the
usual tool caches) are skipped by default, so it never descends into installed
dependencies. Skip additional paths with `--exclude` (repeatable, and also accepts
a comma-separated list); patterns are globs matched against each path component and
the relative path:

```console
$ ftrio lint . --exclude tests --exclude "*_generated.py"
$ ftrio lint . --exclude tests,scripts
```

Use `--no-default-excludes` to scan everything, and `-v/--verbose` to see what is
being scanned. Test fixtures that create their config dynamically are a common case
for `--exclude tests`.

## Configuration

`appsettings.json` keeps the .NET section names (`Toggles`, `TogglesOverrides`,
`FtrIO`) for cross-language and wire compatibility, the HTTP provider returns this
exact shape. Notable `FtrIO` settings: `ReloadOnChange` (re-read on each lookup so
live edits apply without a restart), `FlushInterval`, `Environment` (overlays
`appsettings.{Environment}.json`), and `BlueGreen:CurrentSlot` / `KnownSlots`.

The active environment resolves from `FtrIO:Environment`, then
`ASPNETCORE_ENVIRONMENT`, then `DOTNET_ENVIRONMENT` (with `FTRIO_ENVIRONMENT` as an
additive Python-native alias).

## Playground

```console
$ python -m playground
```

Cycles four users every two seconds and prints each toggle's ON/OFF state,
honouring live edits to `playground/appsettings.json`.

## Development

```console
$ pip install -e ".[dev]"
$ pytest --cov=ftrio
$ ruff check ftrio
$ mypy ftrio
```

See [PORTING_NOTES.md](https://github.com/FtrOnOff/ftrio-python/blob/main/PORTING_NOTES.md)
for every deviation from a literal 1:1 port of the .NET source.

## Releasing and changelog

Releases are published to PyPI from a GitHub Release via Trusted Publishing; the
step-by-step checklist is in
[RELEASING.md](https://github.com/FtrOnOff/ftrio-python/blob/main/RELEASING.md).
Notable changes are recorded in
[CHANGELOG.md](https://github.com/FtrOnOff/ftrio-python/blob/main/CHANGELOG.md).
