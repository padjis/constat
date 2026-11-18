"""Declaring a business area ahead of its first rule (CON-88).

**Why this is not on `Catalogue`.** That class is read-only on purpose: a rule
enters the catalogue through `Review.accept` and through nothing else (D-048),
and a test asserts it has no write surface. Declaring an area is a write, and a
*human* write — the same kind acceptance is — so it lives beside the other
human-driven store rather than widening a read-only door.

**Most areas are never declared here.** An area is declared by accepting a rule
that carries it: acceptance freezes the area onto the version (D-070), so the
catalogue is already the register. `Catalogue.areas` reads both and is the
single answer to "which areas exist".

This table exists for the case the catalogue cannot express: naming an area
*before* it has a rule, which is what a baseline does when it opens an area and
then files rules under it (CON-89). Without it, an area could only come into
being as a side effect of a rule, and an area new to the product would have
nowhere to be declared.

**No vocabulary, no CHECK, no refusal of a name.** Constat records what a
person calls a part of their product. Rejecting a heading for not being in a
list would be deciding how someone's business is organised, which is not a
judgement any of this is entitled to make.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import InvalidInput
from .workspace import Workspace, utc_now

MAX_AREA = 60
"""Same bound the parse applies (`ai/parsing.py`). An area is a heading, and a
long one is a statement that has wandered into the wrong field. Duplicated as a
constant rather than imported, because the store must not depend on the
interpretation layer — the dependency rule in ARCHITECTURE.md section 2.1."""


@dataclass(frozen=True)
class DeclaredArea:
    name: str
    declared_by: str
    created_at: str


class Areas:
    """Areas named ahead of their first rule."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def declare(self, name: str, declared_by: str) -> DeclaredArea:
        """Declare an area, or raise if it is already declared.

        Refusing the duplicate rather than ignoring it: someone declaring an
        area that exists has a different picture of the catalogue than the
        catalogue does, and silently succeeding would leave them with it.
        """
        cleaned = name.strip()
        if not cleaned:
            raise InvalidInput("an area needs a name.")
        if len(cleaned) > MAX_AREA:
            raise InvalidInput(
                f"an area name is at most {MAX_AREA} characters; this one is "
                f"{len(cleaned)}. An area is a heading a business reader "
                "navigates by, not a statement."
            )

        existing = self._workspace.execute(
            "SELECT name FROM area WHERE name = ?", (cleaned,)
        ).fetchone()
        if existing is not None:
            raise InvalidInput(f"area {cleaned!r} is already declared.")

        in_use = self._workspace.execute(
            "SELECT 1 FROM rule WHERE area = ? LIMIT 1", (cleaned,)
        ).fetchone()
        if in_use is not None:
            raise InvalidInput(
                f"area {cleaned!r} already exists: an accepted rule carries "
                "it, which is what declares an area. Nothing to do."
            )

        now = utc_now()
        self._workspace.execute(
            "INSERT INTO area (name, declared_by, created_at) VALUES (?, ?, ?)",
            (cleaned, declared_by, now),
        )
        return DeclaredArea(name=cleaned, declared_by=declared_by, created_at=now)

    def list(self) -> tuple[DeclaredArea, ...]:
        """Only the explicitly declared ones.

        Deliberately not the full set — that is `Catalogue.areas`, which unions
        these with the areas on accepted rules. A caller wanting "which areas
        exist" must not get "which areas were typed in", because the second is a
        small and misleading subset.
        """
        rows = self._workspace.execute(
            "SELECT name, declared_by, created_at FROM area ORDER BY name"
        ).fetchall()
        return tuple(
            DeclaredArea(
                name=row["name"],
                declared_by=row["declared_by"],
                created_at=row["created_at"],
            )
            for row in rows
        )
