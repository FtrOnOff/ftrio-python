# Porting Notes

Every place this Python port deviates from a literal 1:1 translation of the .NET
[FtrIO](https://github.com/FtrOnOff/FtrIO) source, with a one-line justification.
Where a faithful 1:1 port was technically impossible, the closest Pythonic
substitute is documented here.

## Interface rename table

C# uses an `I` prefix for interfaces; Python does not, and dropping it naively
collides the interface with its implementation. Resolved as follows:

| C# | Python | Kind |
|---|---|---|
| `IToggleParser` | `ToggleParser` | ABC (default `get_override` returns `None`) |
| `ToggleParser` (concrete) | `AppSettingsToggleParser` | concrete; the rename says what it reads |
| `IToggleDecisionStrategy` | `ToggleDecisionStrategy` | ABC |
| `IToggleValueProvider` | `ToggleValueProvider` | ABC |
| `IToggleBuffer` | `ToggleBuffer` | ABC |
| `IFtrIOContextAccessor` | `FtrIOContextAccessor` | `typing.Protocol` (structural; FtrIO calls it on consumer objects) |
| `IFeatureToggle<T>` | collapsed into `FeatureToggle` | Python duck-types; no separate interface |
| `FeatureToggle<T>` | `FeatureToggle` | concrete; the generic is dropped, returns are dynamically typed |

Method names map by case only (`GetToggleStatus` -> `get_toggle_status`, etc.).

## `[Toggle]` / `[ToggleAsync]` attributes -> `@toggle` / `@toggle_async` decorators

The .NET attributes double as AspectInjector aspects: the gating check is woven
into the decorated method's IL at compile time. Python has no IL-weaving
equivalent, so the faithful substitute is a decorator that performs the same check
at call time. Behaviour preserved: the key defaults to the function's own name;
when off, `@toggle` returns `None` and `@toggle_async` returns an awaitable that
resolves to `None`.

The async wrapper is deliberately a plain function (not `async def`) that returns
an awaitable, so the gating check runs synchronously at call time. This matches
the .NET woven `Around` advice, which runs before the async state machine starts:
a missing key or unparseable value raises at the call site, not as a faulted
awaitable. The decorated wrapper is tagged with `_ftrio_toggle_key`, the Python
stand-in for `GetCustomAttribute<Toggle>()`, so `FeatureToggle` can detect it.

## Analyzer -> `ftrio lint` CLI

The .NET `ToggleConfigAnalyzer` is a Roslyn `DiagnosticAnalyzer` (diagnostic
`FTRIO001`) that runs inside the compiler. Python has no in-compiler analyzer, so
the intent is ported as a build-time CLI: `ftrio lint [path]` walks the project
with the `ast` module, resolves each `@toggle` / `@toggle_async` key, loads
`appsettings.json`, and reports any decorated function whose key is missing from
the `Toggles` section. It exits non-zero on findings (the analyzer's
`DiagnosticSeverity.Error` intent) so CI can gate on it. The message wording
preserves the analyzer's intent. This is build-time-via-CLI rather than
in-compiler, and is the closest faithful substitute.

## `Microsoft.Extensions.Configuration` -> `config.py`

The .NET source reads `appsettings.json` through `IConfiguration` with a bootstrap
pass (read FtrIO settings) then a live pass (read toggles with environment overlay
and reload-on-change). We replicate the *behaviour*, not the library, in pure
standard-library code:

- Colon-delimited key access over a flattened view of the JSON, mirroring the
  `IConfiguration` indexer.
- JSON booleans stringify to `"true"`/`"false"` so the string-based strategy and
  boolean parsing keep working unchanged. (.NET would stringify to `"True"`/`"False"`;
  every downstream comparison is case-insensitive, so this matches behaviourally
  and the spec specifies the lower-case form.)
- Environment overlay and reload-on-change re-read semantics preserved.

The `appsettings.json` filename and the section names (`Toggles`,
`TogglesOverrides`, `FtrIO`) are kept unchanged. This format is part of FtrIO's
cross-language and wire-compatibility story (the HTTP provider returns this exact
shape), so it was not renamed to something Python-native.

The .NET environment variable names `ASPNETCORE_ENVIRONMENT` and
`DOTNET_ENVIRONMENT` are retained verbatim for cross-runtime parity.
`FTRIO_ENVIRONMENT` is accepted additionally as a Python-native alias; it is
additive and lowest precedence.

## Constructor overloads -> keyword arguments and classmethods

Python has no method overloading, so the .NET constructor matrices become a single
keyword-driven constructor plus small classmethods:

- `StrategyToggleParser`: one constructor taking `*strategies` plus keyword
  `context_accessor` / `base_path` / `provider`, with `with_context_accessor(...)`
  and `with_provider(...)` classmethods covering the named shapes the .NET
  overloads expressed.
- `EnvironmentVariableToggleParser`: the prefix-only and buffer overloads become a
  single constructor with a keyword `buffer` argument (`EnvironmentVariableToggleParser("MYAPP_")`
  for standalone, `EnvironmentVariableToggleParser(buffer=spy)` for buffer mode).
- `BlueGreenStrategy`: explicit-slot vs config-driven construction is selected by a
  `config_driven` flag / `base_path` keyword, with a `from_config(...)` classmethod
  for clarity. The parameterless `.NET` `new BlueGreenStrategy()` maps to the
  config-driven default.

`ToggleParserBuilder.with_overrides()` preserves the .NET error behaviour: called
without an accessor and none was previously registered, it raises (here
`ValueError`, the Pythonic equivalent of `InvalidOperationException`) with the same
guidance.

## `IDisposable` -> `close()` and context managers

Types that hold a timer or background thread (`ToggleProviderBuffer`,
`EnvironmentVariableToggleParser`, `HttpToggleParser`, `AzureAppConfigToggleParser`)
replace `Dispose()` with a `close()` method plus `__enter__`/`__exit__` so they can
be used with `with`. `ToggleProviderBuffer.close()` performs a final flush, exactly
like the .NET `Dispose()`.

## Concurrency primitives

`ToggleProviderBuffer` ports the .NET concurrency design with Python primitives:

- `System.Threading.Timer` (recurring) -> a private `RepeatingTimer` daemon thread
  (`ftrio/_periodic.py`), shared by the buffer and the polling providers.
- `ConcurrentDictionary` staging -> a plain dict guarded by a staging lock.
- `Monitor.TryEnter` skip-if-busy flush -> `threading.Lock.acquire(blocking=False)`.
- `File.Replace` / `File.Move` atomic write -> `os.replace` (atomic on POSIX and
  Windows, and overwrites whether or not the target exists, so the two .NET paths
  collapse into one).
- Failed-write re-stage uses `dict.setdefault`, the equivalent of
  `ConcurrentDictionary.TryAdd` (preserve any newer value).

## A/B `int.MinValue` edge case

The bucket algorithm computes `abs(BitConverter.ToInt32(hash, 0)) % 100`. In .NET,
`Math.Abs(int.MinValue)` throws `OverflowException`; in Python, `abs(-2147483648)`
returns `2147483648`. The two implementations therefore diverge for the roughly
1-in-4-billion input whose first four hash bytes equal `int.MinValue`. This is
noted but not specially handled, per the spec; the six pinned cross-language
vectors all agree, and parity on that single input would only matter if a real
deployment required it.

## Additive (not in the .NET source)

- `ToggleParserProvider.reset()`: clears the ambient parser so the next access
  re-creates the default. Added so tests can isolate the process-global ambient
  state between cases. Not part of the .NET API.
- `ftrio/_periodic.RepeatingTimer`: a private helper (leading underscore, not
  exported) so the buffer and polling providers share one correct timer
  implementation rather than each duplicating thread management.
- `BlueGreenStrategy.from_config()` and `StrategyToggleParser.with_context_accessor()`
  / `.with_provider()` classmethods: named construction entry points that stand in
  for the .NET overload set (see above).
- `logging` integration (OEP-2 alignment): the library uses the standard
  `logging` module for verbosity rather than the .NET source's silent
  fail-safe swallows. Each module owns a `logging.getLogger(__name__)`; the
  buffer warns on a failed flush and the polling providers log their fail-safe
  paths at debug. The `ftrio` package attaches a `NullHandler`, so it emits
  nothing by default while letting the host application redirect FtrIO logs to a
  file and set levels per component. The `ftrio lint` CLI exposes `-v/--verbose`
  to turn that debug output on. This satisfies OEP-2's logging requirement
  without changing the fail-safe runtime behaviour.

## Toggle keys follow the language's method-naming convention

The toggle key derives from the decorated method's own name. That contract holds
in any language; the *casing* of the key simply follows the language's method
naming convention. C# methods are PascalCase, so the .NET source's toggle keys are
PascalCase (`Toggles:TestingTrue`). Python methods are snake_case, so this port's
toggle keys are snake_case (`Toggles:testing_true`). The PascalCase in the .NET
appsettings.json was therefore a C# artifact, not part of the cross-language wire
contract: the contract is the JSON *shape* (the `Toggles` / `TogglesOverrides` /
`FtrIO` sections and the value grammars like `50%`, `ab:50`, `blue`), not the
literal spelling of application-defined keys.

Accordingly, the playground and the `@toggle`-decorated test fixtures use
snake_case method names with matching snake_case keys in their appsettings.json.
The explicit-string test keys that are passed as literal arguments rather than
derived from a method name (`FakeTrue`, `ButtonToggle`, `StrategyPercentageAlwaysOn`,
etc.) are JSON string values, not Python identifiers, so they are left as the .NET
test-data mirror. The pinned A/B determinism vectors (`TestingABTest`,
`TestingABTestSalted`) are likewise kept verbatim: they are cross-language hash
inputs proving byte-for-byte parity with .NET, not Python method names.

## Style guide conformance (OEP-2 / Google Python Style Guide)

OEP-2 recommends Google's Python Style Guide. PEP 8 naming is enforced by `ruff`'s
`pep8-naming` (`N`) ruleset: classes are PascalCase, functions/methods (including
the playground and decorated test fixtures) are snake_case, enum members and
module constants are UPPER_SNAKE.

Exception classes use the Python-canonical `*Error` suffix
(`ToggleDoesNotExistError`, `ToggleParsedOutOfRangeError`,
`ToggleAttributeMissingError`) rather than the .NET `*Exception` spelling. This is
a deliberate choice to be idiomatic for Python programmers (and it satisfies
`N818` without an override): the .NET source named them `*Exception` because that
is the .NET convention, and the faithful equivalent of "follow the platform's
exception-naming convention" in Python is the `Error` suffix. The class *meaning*
is preserved; only the suffix follows the language, the same principle applied to
snake_case toggle keys.

One documented override remains: `N802` is ignored for the fake HTTP test server's
`do_GET`, whose name is fixed by the standard-library `http.server` API. One
further intentional divergence from Google style: it favours sectioned docstrings
(`Args:` / `Returns:` / `Raises:`), whereas the build spec required docstrings that
explain *why*, mirroring each `<summary>` in the .NET source; the "why"-first prose
docstrings were kept as the spec mandated.

## Components intentionally not ported verbatim

- AspectInjector IL weaving (no Python equivalent; see decorators above).
- The Roslyn analyzer assembly (replaced by the `ftrio lint` CLI; see above).

