"""Reading the catalogue as it stood at a past point (CON-87).

The ticket asked for "the rules **in effect** at a named past release", and two
words of that cannot be delivered honestly yet.

**"In effect" is not knowable.** Nothing records that a release shipped —
closing one is CON-86, and the ship it would record is *asserted* rather than
verified, because Constat cannot detect a partial ship across a plural
registered set. So this answers "as the catalogue stood", which is a fact about
what people had agreed, and never "what the product did", which is a different
claim. `constat state` is the view that answers the second, and it verifies
against mainline (D-087).

**"At a release" has no ordering to lean on.** D-102 stores a release name
verbatim and parses nothing, so there is no sense in which one release precedes
another — and `release.id` is declaration order, which is not release order
either: a hotfix declared last may cover work agreed first.

What *is* a fact is **when the versions agreed for a release were accepted**.
So a release is turned into a moment — the latest acceptance among its own
versions — and the catalogue is reconstructed at that moment. The basis is
reported with the answer rather than buried, because a reader who thinks they
are seeing a stored snapshot would be wrong: nothing was snapshotted at the
time, which is exactly what the ticket asked for.

A release with no versions agreed for it yields **no moment and no
reconstruction**. Falling back to "now" would answer a question nobody asked
with the confidence of one they did.
"""

from __future__ import annotations

from dataclasses import dataclass

from .workspace import Workspace


@dataclass(frozen=True)
class VersionAtPoint:
    """One rule, at the version it stood at, at some moment."""

    rule_id: int
    ref: str | None
    name: str
    statement: str
    area: str | None
    version_no: int
    rule_version_id: int
    accepted_at: str
    #: The release this *version* was agreed for, if any. Often `None` even in
    #: a release reconstruction: a rule untouched since an earlier release
    #: still stood then, and its version carries that earlier release or none.
    agreed_for: str | None


class CatalogueHistory:
    """Point-in-time reads over the frozen versions.

    Read-only, and on its own class rather than on `Catalogue` for the reason
    that one is deliberately narrow: `Catalogue` answers "what does the
    catalogue hold now", and a method that answered "what did it hold then"
    would make every caller's question ambiguous at the call site.
    """

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def agreed_for(self, release_name: str) -> tuple[VersionAtPoint, ...]:
        """The versions agreed for a release. A fact, with no inference.

        Empty for a release nobody has agreed a version for, which is a real
        and ordinary state: a release is declared before the work is decided.
        """
        rows = self._workspace.execute(
            "SELECT v.id, v.rule_id, v.version_no, v.name, v.statement, "
            "       v.area, v.created_at, r.ref, rel.name AS release_name "
            "FROM rule_version v "
            "JOIN release rel ON rel.id = v.release_id "
            "LEFT JOIN rule r ON r.id = v.rule_id "
            "WHERE rel.name = ? "
            "ORDER BY v.name",
            (release_name.strip(),),
        ).fetchall()
        return tuple(_at_point(row) for row in rows)

    def moment_of(self, release_name: str) -> str | None:
        """When the last version agreed for this release was accepted.

        `None` when none has been, and the caller must not substitute anything
        for it. This is the only defensible way to turn a release into a point
        in time: it is a fact about what was decided, where any ordering of
        release *names* would be an invention (D-102).
        """
        row = self._workspace.execute(
            "SELECT MAX(v.created_at) AS moment "
            "FROM rule_version v "
            "JOIN release rel ON rel.id = v.release_id "
            "WHERE rel.name = ?",
            (release_name.strip(),),
        ).fetchone()
        return None if row is None else row["moment"]

    def as_at(self, moment: str) -> tuple[VersionAtPoint, ...]:
        """Every rule that stood at `moment`, at the version it stood at.

        Reconstructed from the frozen version tables, so no snapshot had to
        have been taken at the time — which is the whole of CON-87.

        Three things it gets right and a naive query would not:

        - **The newest version at or before the moment**, not the newest
          version. Reading the live `rule` table would show today's substance
          under a past heading, the mistake CON-61 was written to prevent.
        - **A rule accepted after the moment is absent**, rather than present
          at its first version.
        - **A rule retired at or before the moment is absent**, and one retired
          *after* it is present. Retirement is a dated decision (D-084), so it
          belongs in a point-in-time read like any other.
        """
        rows = self._workspace.execute(
            "SELECT v.id, v.rule_id, v.version_no, v.name, v.statement, "
            "       v.area, v.created_at, r.ref, rel.name AS release_name "
            "FROM rule_version v "
            "JOIN ("
            "  SELECT rule_id, MAX(version_no) AS version_no "
            "  FROM rule_version WHERE created_at <= ? GROUP BY rule_id"
            ") newest "
            "  ON newest.rule_id = v.rule_id "
            " AND newest.version_no = v.version_no "
            "LEFT JOIN rule r ON r.id = v.rule_id "
            "LEFT JOIN release rel ON rel.id = v.release_id "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM rule_retirement x "
            "  WHERE x.rule_id = v.rule_id AND x.decided_at <= ?"
            ") "
            "ORDER BY v.name",
            (moment, moment),
        ).fetchall()
        return tuple(_at_point(row) for row in rows)


def _at_point(row) -> VersionAtPoint:
    return VersionAtPoint(
        rule_id=int(row["rule_id"]),
        ref=row["ref"],
        name=row["name"],
        statement=row["statement"],
        area=row["area"],
        version_no=int(row["version_no"]),
        rule_version_id=int(row["id"]),
        accepted_at=row["created_at"],
        agreed_for=row["release_name"],
    )
