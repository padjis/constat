"""The publication port (CON-57, D-058).

A document has to reach the people who decide about it, and they are not in a
terminal. This is the seam that lets it, shaped the same way the provider seam
is: a `Protocol` plus a registry, so Confluence, GitBook and GitLab docs arrive
behind it as optional extras (CON-59) rather than as branches in one function.

**Two methods, both implemented for git.** `publish` writes a document;
`read_decisions` reads the decisions a reviewer wrote in the target, which
`GitPages` does with nothing but `git` (D-105). Declaring it here is what kept
the first backend from inventing its own shape, and a backend that cannot yet
read *raises* rather than returning nothing — an empty list of decisions reads
as "nobody has decided", which is the substitution D-041 refuses.

**Nothing here holds a credential.** A target authenticates the way the
underlying tool already does; for git that is the user's SSH agent or
credential helper. `CLAUDE.md` forbids a secret in any file in this repository,
and the way to keep that promise is to never be the thing holding the secret.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..errors import DecisionsNotReadable


STATE_REFERENCE = "the-product-as-it-stands"
"""The page the catalogue itself is published to (CON-106).

Not a ticket, and deliberately shaped like one so no target needs a second
way to name a page: every `Target` already turns a reference into a filename,
and the state page is just the reference nobody opens a ticket for.

Reserved, therefore. `publish <REF>` refuses a ticket whose page name would
collide with this one rather than letting a ticket document overwrite the
catalogue — a collision nobody would notice until the page was already wrong.
"""


@dataclass(frozen=True)
class PublishedRef:
    """Where a document went, concretely enough to go and look.

    `location` is what a person can open; `revision` is what the target called
    the write, where it has such a notion. Both are recorded as an operation so
    a disclosure is attributable afterwards (D-029, D-049) — a publication
    nobody can trace is indistinguishable from none.
    """

    target: str
    location: str
    reference: str
    revision: str | None = None

    def describe(self) -> str:
        where = self.location
        if self.revision is not None:
            where += f" ({self.revision[:12]})"
        return f"{self.target}: {where}"


@runtime_checkable
class Target(Protocol):
    """Somewhere a document can be published."""

    name: str

    def describe(self) -> str:
        """Where this target writes, for the confirmation line and the record."""
        ...

    def publish(self, reference: str, body: str) -> PublishedRef:
        """Write the document for `reference`, returning where it went.

        Must raise `PublishFailed` rather than returning a `PublishedRef` for a
        write that did not land. Overwriting an existing page is the expected
        case: a document is a living view of one ticket, and the durable record
        is the workspace, where `document_version` is append-only (D-004).
        """
        ...

    def read_decisions(self, reference: str) -> tuple[dict, ...]:
        """Decisions recorded in the target. CON-58."""
        ...


class NotYetReadable:
    """Mixin for a target that can publish but cannot yet read decisions back.

    Inherited rather than copied so every such backend fails the same way, with
    the same message, instead of each inventing a silence.

    **`GitPages` no longer uses this** — CON-58 landed for git (D-105), where
    reading decisions needs nothing but `git`. The backends CON-59 names, which
    each need their own API, will publish before they can read and inherit this
    in the meantime.
    """

    name = "unnamed"

    def read_decisions(self, reference: str) -> tuple[dict, ...]:
        raise DecisionsNotReadable(
            f"{self.name} cannot report decisions made in it yet (CON-58). "
            "Refusing rather than returning none: an empty list would read as "
            "'nobody has decided'. Accept or reject at the command line, where "
            "the decision is recorded with its channel."
        )
