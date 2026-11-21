"""Declaring a release, and resolving one by name (CON-85).

A release is **a name for a group of rule versions**, and nothing more than
that here. It does not decide what the product currently does: D-087 answers
that by verifying a rule's evidence commits against mainline, which is a
stronger claim than a declared release's asserted ship (D-085). Closing a
release so its versions take effect is CON-86 and is not built.

**Declared, never derived.** Constat does not read tags to find releases. D-009
found 777 machine-generated build tags in one subject repository, so a tag is
not evidence that anything was released, and a release that appeared because
somebody's CI pushed a tag would be a claim nobody made.

**The name is repeated, never interpreted.** No semver, no ordering, no
"latest". This is what survives of D-032: a field Constat *parses* becomes a
claim it cannot support, where a name a person chose and Constat only repeats
is a human decision. Several releases may be open at once (there is no close),
so there is no ordering to infer in any case.

**A write, and a human one**, so it lives here rather than on `Catalogue` —
which is read-only on purpose, because a rule enters the catalogue through
`Review.accept` and through nothing else (D-048). Same reasoning as `Areas`.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import InvalidInput, NotRegistered
from .workspace import Workspace, utc_now

MAX_RELEASE = 120
"""A release name is a label — `2026.11`, `Autumn release`, `v4.2 hotfix`. The
bound is generous because naming conventions vary wildly and refusing somebody's
own convention would be deciding how they version their product. It exists only
so a statement cannot be pasted into the field."""


@dataclass(frozen=True)
class Release:
    id: int
    name: str
    declared_by: str
    created_at: str


class Releases:
    """Releases somebody declared in this workspace."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def declare(self, name: str, declared_by: str) -> Release:
        """Declare a release, or refuse if that name is already taken.

        Refusing the duplicate rather than returning the existing row: someone
        declaring a release that exists has a different picture of the
        workspace than the workspace does, and silently succeeding would leave
        them holding it. The same choice `Areas.declare` makes.
        """
        cleaned = name.strip()
        if not cleaned:
            raise InvalidInput("a release needs a name.")
        if len(cleaned) > MAX_RELEASE:
            raise InvalidInput(
                f"a release name is at most {MAX_RELEASE} characters; this one "
                f"is {len(cleaned)}. A release is a label, not a description "
                "of what is in it."
            )

        existing = self._workspace.execute(
            "SELECT id FROM release WHERE name = ?", (cleaned,)
        ).fetchone()
        if existing is not None:
            raise InvalidInput(
                f"release {cleaned!r} is already declared. Names are stored "
                "verbatim and compared exactly, so two releases cannot share "
                "one."
            )

        now = utc_now()
        cursor = self._workspace.execute(
            "INSERT INTO release (name, declared_by, created_at) "
            "VALUES (?, ?, ?)",
            (cleaned, declared_by, now),
        )
        return Release(
            id=int(cursor.lastrowid),
            name=cleaned,
            declared_by=declared_by,
            created_at=now,
        )

    def list(self) -> tuple[Release, ...]:
        """Every declared release, oldest first.

        **Ordered by when it was declared, not by its name.** Sorting names
        would be interpreting them — `v10` before `v9`, or after, depending on
        a convention Constat was never told. Declaration order is a fact.
        """
        rows = self._workspace.execute(
            "SELECT id, name, declared_by, created_at FROM release "
            "ORDER BY id"
        ).fetchall()
        return tuple(
            Release(
                id=int(row["id"]),
                name=row["name"],
                declared_by=row["declared_by"],
                created_at=row["created_at"],
            )
            for row in rows
        )

    def find(self, name: str) -> Release | None:
        """Exact match on the stored name, or nothing.

        No normalisation beyond the surrounding whitespace `declare` also
        strips. Case-folding `V4.2` onto `v4.2` would be a guess about somebody
        else's convention, and the kind of guess D-020 refuses for an ambiguous
        revision.
        """
        row = self._workspace.execute(
            "SELECT id, name, declared_by, created_at FROM release "
            "WHERE name = ?",
            (name.strip(),),
        ).fetchone()
        if row is None:
            return None
        return Release(
            id=int(row["id"]),
            name=row["name"],
            declared_by=row["declared_by"],
            created_at=row["created_at"],
        )

    def require(self, name: str) -> Release:
        """Resolve a name, or refuse with the declared ones named.

        **A release is never coined by using it.** Accepting a rule for an
        undeclared release would create one as a side effect of a different
        decision, and a release nobody declared is exactly what "declared,
        never derived" rules out. The refusal lists what exists, because the
        usual cause is a typo rather than a missing release.
        """
        found = self.find(name)
        if found is not None:
            return found

        declared = [release.name for release in self.list()]
        if declared:
            known = "Declared releases: " + ", ".join(repr(n) for n in declared) + "."
        else:
            known = (
                "No releases are declared in this workspace. "
                "`constat release declare` is where one comes from."
            )
        raise NotRegistered(
            f"no release named {name.strip()!r}. A release is declared by a "
            f"person, never created by being used. {known}"
        )
