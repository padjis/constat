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

from .decisions import DECISIONS_DIRECTORY

from ..errors import DecisionsNotReadable


STATE_REFERENCE = "status"
"""The page the catalogue itself is published to (CON-106).

Not a ticket, and deliberately shaped like one so no target needs a second
way to name a page: every `Target` already turns a reference into a filename,
and the state page is just the reference nobody opens a ticket for.

Reserved, therefore. `publish <REF>` refuses a ticket whose page name would
collide with this one rather than letting a ticket document overwrite the
catalogue — a collision nobody would notice until the page was already wrong.
"""


AREAS_DIRECTORY = "areas"
"""Where an area page goes.

A folder rather than a prefix, so the target reads as what it is: `areas/`
beside `evidence/` and `decisions/`, with the whole-product pages at the root.
The `area-` prefix survives as the *reference* — how Constat names the page
internally — because a reference is what every publishing command takes.
"""

#: Where a ticket's page goes, re-exported so a renderer need not know that
#: it comes from the decisions module.
TICKETS_DIRECTORY = DECISIONS_DIRECTORY
"""One folder for deciding, with the ticket page above the rules (CON-123).

It was `evidence/` for an afternoon, then `reviews/` for a day. The page is
not evidence: it is the proposals awaiting a verdict, which is what a reviewer
needs in order to decide and all they need. The evidence itself stays in the
workspace, where the durable record is a pointer to a commit rather than a
copy of a diff (CON-79) — a published page of diffs looks like an archive and
is not one, because it is rewritten on every run and regenerates empty once
the ticket lands.

And it is not a *second* place either. `reviews/630.md` listing three
proposals while `decisions/630/26.md` held one of them was two folders for one
act, with each statement printed twice. The ticket page now sits at
`decisions/630.md`, directly above the pages it links to, which is also how a
wiki nests them.
"""

EVIDENCE_DIRECTORY = "evidence"
"""Where a ticket's page goes (CON-113).

A ticket page is the **technical evidence view** product rule 8 asks for: it
is made of paths, changed files and diffs, by design. The business pages — the
catalogue, the areas, the releases, the index — carry none of that (D-115).

Both audiences share one target, so the separation is a directory rather than
a second repository: one credential, one setting, and a reader who lands in
`evidence/` can see from the path alone which of the two they are reading.
"""


def is_generated(reference: str) -> bool:
    """Whether a reference names a page Constat generates for the business.

    The generated pages live at the root; a ticket page lives under
    `evidence/`. Asked here rather than at the target so every implementation
    of the port answers it the same way.
    """
    return (
        reference in (STATE_REFERENCE, INDEX_REFERENCE)
        or reference.startswith(AREA_PREFIX)
        or reference.startswith(RELEASE_PREFIX)
    )


AREA_PREFIX = "area-"
"""Reserved for area pages (CON-111).

An area is free text frozen on each accepted version — it has no row and no
identity (D-079, CON-88) — so an area page is named by prefixing its name
rather than by any identifier. Reserved like `release-`: every page is named
from a reference, and a ticket called `area-payments` would overwrite one.
"""

RELEASE_PREFIX = "release-"
"""Reserved for release pages (CON-112). Defined here with the other page
names so `is_generated` can answer without importing from operations."""

INDEX_REFERENCE = "index"
"""The page that lists every other page (CON-110).

Reserved on the same reasoning as `STATE_REFERENCE`: both page kinds are named
from a reference, so without reserving it a ticket called `index` would
silently overwrite the index and nobody would notice until it was wrong.
"""


@dataclass(frozen=True)
class Awaiting:
    """A proposal waiting for a verdict, with what a reviewer needs to give one.

    Carried to the target so the page a verdict is written on can say *what*
    is being decided (CON-120). Before this it held bare numbers: a reviewer
    read the statements on one page and wrote verdicts on another, and for a
    revision neither page said what had changed. Since CON-122 each of these
    gets a page of its own on the target.
    """

    id: str
    name: str
    statement: str

    previous: str | None = None
    """The statement this one would replace, when the proposal revises a rule.

    `None` for a new rule. The distinction is the reviewer's whole question —
    *is this a change, and is the change right* — and it cannot be read off a
    statement alone."""


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

    def publish(
        self, reference: str, body: str, awaiting: tuple["Awaiting", ...] = ()
    ) -> PublishedRef:
        """Write the document for `reference`, returning where it went.

        `awaiting` names the proposals on this page that nobody has decided
        yet. A target may use it to give each one somewhere to be decided —
        `git_pages` writes a page per proposal, carrying its statement and one
        line to answer (CON-122). Whatever a target writes there it writes
        **once**: a reviewer's file is never read back, moved or altered
        (D-105).

        Must raise `PublishFailed` rather than returning a `PublishedRef` for a
        write that did not land. Overwriting an existing page is the expected
        case: a document is a living view of one ticket, and the durable record
        is the workspace, where `document_version` is append-only (D-004).
        """
        ...

    def read_decisions(self, reference: str) -> tuple[dict, ...]:
        """Decisions recorded in the target. CON-58."""
        ...

    def references_published(self, prefix: str) -> tuple[str, ...]:
        """Every reference already published under `prefix` (CON-111).

        Needed because an area can empty: when the last rule filed under it is
        re-accepted elsewhere, the area stops existing and nothing in the
        workspace remembers that a page was ever written for it. Constat's own
        publication record does not help — it covers ticket pages only, since
        an `operation` requires a document (D-110).

        So the target is asked. A page Constat wrote and no longer has content
        for is rewritten as a tombstone rather than deleted or left stale: the
        URL keeps resolving and the page stops claiming to be current.
        """
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
