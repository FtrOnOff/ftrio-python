"""Exception types raised throughout FtrIO.

These mirror the three exception classes in the .NET source (``ToggleExceptions``
namespace). The intent of each is preserved: they signal *why* a toggle could not
be resolved so callers can distinguish "the key is genuinely absent" from "the
value made no sense" from "you forgot to decorate the method".
"""

from __future__ import annotations


class ToggleDoesNotExistError(Exception):
    """Raised when a toggle key is requested but is absent from the source.

    Composite parsers rely on this exception specifically to decide whether to
    fall through to the next parser in the chain; it is the load-bearing signal
    for "this source does not know about that key", not a generic failure.
    """


class ToggleParsedOutOfRangeError(Exception):
    """Raised when a toggle value exists but cannot be interpreted.

    A value that is neither truthy/falsey nor handled by any registered strategy
    is out of range. This deliberately differs from a missing key: the operator
    configured *something*, it just is not a value FtrIO can act on.
    """


class ToggleAttributeMissingError(Exception):
    """Raised when a method is gated without a resolvable toggle key.

    The explicit-execution API needs either an explicit key name or a method that
    carries the ``@toggle`` marker. When neither is present there is no way to know
    which toggle should gate the call, so this is raised rather than guessing.
    """
