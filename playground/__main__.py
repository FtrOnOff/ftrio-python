"""PlaygroundConsole port: see ``@toggle`` gating real method calls live."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from ftrio import ToggleParserProvider, toggle

_GREEN = "\x1b[32m"
_GREY = "\x1b[90m"
_RESET = "\x1b[0m"


class SimulatedContextAccessor:
    """A context accessor whose current user is swapped each loop iteration.

    Satisfies the ``FtrIOContextAccessor`` protocol structurally; the demo calls
    ``set_context`` to rotate through users so the same toggles resolve
    differently per user.
    """

    def __init__(self) -> None:
        self._user_id: str | None = None
        self._attributes: dict[str, str] = {}

    def set_context(self, user_id: str, attributes: dict[str, str]) -> None:
        """Point the accessor at a new current user and attribute set."""
        self._user_id = user_id
        self._attributes = attributes

    def get_user_id(self) -> str | None:
        return self._user_id

    def get_attribute(self, name: str) -> str | None:
        return self._attributes.get(name)


class ToggleDemo:
    """Every method here is a real ``@toggle``-gated call.

    When a toggle is off, the decorator returns ``None`` without running the body,
    so ``_show`` prints an OFF line; when on, the body sets ``_ran`` and prints its
    own ON line. This is the Python analogue of the .NET demo's woven gating.
    """

    def __init__(self) -> None:
        self._ran = False

    def _show(self, method: Callable[[], None], key: str, strategy: str) -> None:
        self._ran = False
        method()
        if not self._ran:
            print(f"  {key:<22}  {strategy:<26}  {_GREY}OFF{_RESET}")

    def run(self) -> None:
        """Exercise every gated toggle once, in the same order as the .NET demo."""
        self._show(self.testing_true, "testing_true", "BooleanStrategy")
        self._show(self.testing_false, "testing_false", "BooleanStrategy")
        self._show(self.testing_percentage, "testing_percentage", "PercentageRollout")
        self._show(self.testing_blue_green, "testing_blue_green", "BlueGreenStrategy")
        self._show(self.testing_user_target, "testing_user_target", "UserTargetingStrategy")
        self._show(self.testing_attribute, "testing_attribute", "AttributeRuleStrategy")
        self._show(self.testing_ab_test, "testing_ab_test", "ABTestStrategy")
        self._show(self.testing_ab_test_salted, "testing_ab_test_salted", "ABTestStrategy (salted)")
        self._show(self.testing_no_attribute, "testing_no_attribute", "(no @toggle)")

    @toggle
    def testing_true(self) -> None:
        self._ran = True
        print(f"  {'testing_true':<22}  {'BooleanStrategy':<26}  {_GREEN}ON {_RESET}  base: true | override: bob=false")

    @toggle
    def testing_false(self) -> None:
        self._ran = True
        print(f"  {'testing_false':<22}  {'BooleanStrategy':<26}  {_GREEN}ON {_RESET}  overlay: true, base: false")

    @toggle
    def testing_percentage(self) -> None:
        self._ran = True
        print(f"  {'testing_percentage':<22}  {'PercentageRollout':<26}  {_GREEN}ON {_RESET}  overlay: 80%, base: 50% - random per call")

    @toggle
    def testing_blue_green(self) -> None:
        self._ran = True
        print(f"  {'testing_blue_green':<22}  {'BlueGreenStrategy':<26}  {_GREEN}ON {_RESET}  slot: blue")

    @toggle
    def testing_user_target(self) -> None:
        self._ran = True
        print(f"  {'testing_user_target':<22}  {'UserTargetingStrategy':<26}  {_GREEN}ON {_RESET}  users: alice, charlie")

    @toggle
    def testing_attribute(self) -> None:
        self._ran = True
        print(f"  {'testing_attribute':<22}  {'AttributeRuleStrategy':<26}  {_GREEN}ON {_RESET}  attribute: plan equals premium")

    @toggle
    def testing_ab_test(self) -> None:
        self._ran = True
        print(f"  {'testing_ab_test':<22}  {'ABTestStrategy':<26}  {_GREEN}ON {_RESET}  ab:50 | override: alice=true always")

    @toggle
    def testing_ab_test_salted(self) -> None:
        self._ran = True
        print(f"  {'testing_ab_test_salted':<22}  {'ABTestStrategy (salted)':<26}  {_GREEN}ON {_RESET}  ab:50:round2 - independent bucket")

    def testing_no_attribute(self) -> None:
        # No @toggle: always runs, demonstrating the baseline.
        self._ran = True
        print(f"  {'testing_no_attribute':<22}  {'(no @toggle)':<26}  {_GREEN}ON {_RESET}  always executes")


def main() -> None:
    """Configure the toggle pipeline and run the live demo loop."""
    # Resolve appsettings.json relative to this package and make it the working
    # directory, mirroring how the .NET build copies appsettings.json next to the
    # executable (AppContext.BaseDirectory). All default base-path lookups then
    # resolve to the playground's own config.
    playground_directory = Path(__file__).resolve().parent
    os.chdir(playground_directory)

    accessor = SimulatedContextAccessor()

    # Strategy order is preserved exactly: context-aware strategies (user
    # targeting, attribute rules, A/B) first, then percentage rollout, then
    # blue/green. Overrides are checked before any strategy.
    ToggleParserProvider.configure_builder(
        lambda builder: builder
        .with_context_strategies(accessor)
        .with_percentage_rollout()
        .with_blue_green()
        .with_overrides()
    )

    base_file = playground_directory / "appsettings.json"
    active_environment: str | None = None
    with base_file.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
        active_environment = document.get("FtrIO", {}).get("Environment")

    print("=" * 74)
    print("FtrIO Playground - @toggle in action")
    print("=" * 74)
    print(f"Base file : {base_file}")
    if active_environment:
        print(f"Overlay   : appsettings.{active_environment}.json")
    print()
    print("Cycling through 4 users every 2s. Edit appsettings.json live. Ctrl+C to exit.")
    print("-" * 74)

    users = [
        ("alice", {"plan": "premium", "country": "IE"}),
        ("bob", {"plan": "free", "country": "US"}),
        ("charlie", {"plan": "free", "country": "GB"}),
        ("dave", {"plan": "premium", "country": "US"}),
    ]

    demo = ToggleDemo()
    iteration = 0
    try:
        while True:
            user_id, attributes = users[iteration % len(users)]
            accessor.set_context(user_id, attributes)
            iteration += 1

            print()
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(
                f"[{timestamp}]  User: {user_id:<10}  "
                f"plan={attributes['plan']:<12}  country={attributes['country']}"
            )
            print(f"  {'Toggle':<22}  {'Strategy':<26}  State")
            print("  " + "-" * 54)

            demo.run()
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nExiting.")


if __name__ == "__main__":
    main()
