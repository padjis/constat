"""The requirements a person says a ticket answers (CON-18).

This is the first producer of `requirement_ref`, which has been declared in the
provenance taxonomy since the beginning and written by nothing. D-094 chose to
name that gap rather than tidy the enum; this closes it for one of the three.

**Three boundaries, and they are the whole design.**

*Supplied, never fetched.* Constat does not read the artefact at the other end.
No network call, no parsing, no check that a URI resolves or that what it points
at has anything to do with the ticket. `requirement_ref` means "supplied by a
human or integration" (PRODUCT_SPEC § 7.1) — it has never meant "verified", and
every view that renders one says which it is.

*A person supplies it, never a model.* There is no path from a reading to this
table and there must not be. A requirement reference written by a provider would
be `ai_interpretation` wearing the label of external evidence, which would make
the taxonomy itself dishonest — the same boundary D-048 draws around acceptance,
applied to evidence instead of to decisions.

*It does not leave the machine.* A supplied requirement is deliberately absent
from the provider payload. The label and URI are internal by nature — a tracker
host, a project code, sometimes a customer's name — and the payload is an egress
boundary that D-040 and D-047 guard carefully. Feeding requirements to a model
would plainly make a reading better, and it is a separate question with a
disclosure dimension, so it is not smuggled in here.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import InvalidInput, NotRegistered
from .workspace import Workspace, utc_now

MAX_LABEL = 120
"""A label is `REQ-14`, `JIRA-882`, `spec § 3.2`. Generous, because naming
conventions vary and refusing somebody's own would be deciding how they track
work. It exists so a requirement's *text* cannot be pasted in where its
reference belongs — the artefact lives at the other end of the pointer, and
copying it here would be ingesting it by hand."""

MAX_URI = 500


@dataclass(frozen=True)
class Requirement:
    """A pointer somebody supplied, and who supplied it."""

    id: int
    reference: str
    label: str
    uri: str | None
    supplied_by: str
    attribution: str
    created_at: str

    def describe(self) -> str:
        """One line for a reviewer, with the pointer if there is one."""
        return f"{self.label} — {self.uri}" if self.uri else self.label


class Requirements:
    """Requirement references, per ticket."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def _ticket_id(self, reference: str) -> int:
        row = self._workspace.execute(
            "SELECT id FROM ticket WHERE reference = ?", (reference.strip(),)
        ).fetchone()
        if row is None:
            raise NotRegistered(
                f"no ticket {reference.strip()!r}. A requirement is attached to "
                "work that exists; open the ticket first with `constat ticket "
                "add`."
            )
        return int(row["id"])

    def supply(
        self,
        reference: str,
        label: str,
        supplied_by: str,
        uri: str | None = None,
        attribution: str = "stated",
    ) -> Requirement:
        """Record that a person says this ticket answers `label`."""
        ticket_id = self._ticket_id(reference)

        cleaned = label.strip()
        if not cleaned:
            raise InvalidInput("a requirement needs a label.")
        if len(cleaned) > MAX_LABEL:
            raise InvalidInput(
                f"a requirement label is at most {MAX_LABEL} characters; this "
                f"one is {len(cleaned)}. A label is a reference — `REQ-14`, "
                "`JIRA-882` — not the requirement's text, which stays at the "
                "other end of the pointer."
            )

        cleaned_uri = uri.strip() if uri else None
        if cleaned_uri is not None and len(cleaned_uri) > MAX_URI:
            raise InvalidInput(
                f"a requirement URI is at most {MAX_URI} characters; this one "
                f"is {len(cleaned_uri)}."
            )
        if cleaned_uri == "":
            cleaned_uri = None

        existing = self._workspace.execute(
            "SELECT id FROM requirement WHERE ticket_id = ? AND label = ?",
            (ticket_id, cleaned),
        ).fetchone()
        if existing is not None:
            raise InvalidInput(
                f"ticket {reference.strip()} already cites {cleaned!r}. "
                "References are append-only, so a correction is supplied "
                "beside the original rather than replacing it."
            )

        now = utc_now()
        cursor = self._workspace.execute(
            "INSERT INTO requirement "
            "(ticket_id, label, uri, supplied_by, attribution, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_id, cleaned, cleaned_uri, supplied_by, attribution, now),
        )
        return Requirement(
            id=int(cursor.lastrowid),
            reference=reference.strip(),
            label=cleaned,
            uri=cleaned_uri,
            supplied_by=supplied_by,
            attribution=attribution,
            created_at=now,
        )

    def for_ticket(self, reference: str) -> tuple[Requirement, ...]:
        """What this ticket cites, oldest first.

        Does not refuse for an unknown ticket: a caller rendering a view asks
        "what does this cite" and the answer for something that does not exist
        is "nothing". `supply` is where a missing ticket matters, because
        attaching a reference to work nobody opened would leave a row nothing
        can reach.
        """
        rows = self._workspace.execute(
            "SELECT r.id, r.label, r.uri, r.supplied_by, r.attribution, "
            "       r.created_at, t.reference "
            "FROM requirement r "
            "JOIN ticket t ON t.id = r.ticket_id "
            "WHERE t.reference = ? ORDER BY r.id",
            (reference.strip(),),
        ).fetchall()
        return tuple(_hydrate(row) for row in rows)

    def all(self) -> tuple[Requirement, ...]:
        """Every supplied reference in the workspace, oldest first."""
        rows = self._workspace.execute(
            "SELECT r.id, r.label, r.uri, r.supplied_by, r.attribution, "
            "       r.created_at, t.reference "
            "FROM requirement r "
            "JOIN ticket t ON t.id = r.ticket_id "
            "ORDER BY r.id"
        ).fetchall()
        return tuple(_hydrate(row) for row in rows)


def _hydrate(row) -> Requirement:
    return Requirement(
        id=int(row["id"]),
        reference=row["reference"],
        label=row["label"],
        uri=row["uri"],
        supplied_by=row["supplied_by"],
        attribution=row["attribution"],
        created_at=row["created_at"],
    )
