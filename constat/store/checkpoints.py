"""Checkpoints: the last state of the product somebody agreed to (CON-15).

**Why this exists when `constat state` already renders the picture.** That view
is computed and stored nowhere (D-070), which is exactly what makes it always
true of the revisions it names — and also what leaves nothing to compare
against. The two are complementary: `state` says what the product does now,
a checkpoint says what it did when a person last looked, and the difference
between them is what a reviewer actually wants.

**Taken explicitly.** "The last approved state" needs a point somebody chose.
Deriving it from the newest acceptance would make the comparison shift every
time a rule was accepted, so "what is new since" would quietly come to mean
"since the previous rule" — a moving reference point, which is no reference
point.

**Append-only**, like every other record of a human decision here. A
checkpoint that could be edited would make "what changed since" unanswerable,
which is the whole reason to have one.

**A note on the word.** `PRODUCT_SPEC` § 6 calls this a *baseline*, and so did
CON-14; the CLI also says "version 1 baselined" when a rule version is frozen,
and CON-89 took `constat baseline <AREA>` for documenting an area. Three senses
of one word, so this object is a **checkpoint** and the others keep "baseline".
Recorded in D-085 rather than left to be rediscovered.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import InvalidInput, NotRegistered
from .workspace import Workspace, utc_now


@dataclass(frozen=True)
class Checkpoint:
    """A frozen record of which rules stood at which versions."""

    id: int
    ref: str | None
    label: str
    taken_by: str
    attribution: str
    taken_at: str
    rule_count: int = 0


@dataclass(frozen=True)
class RuleChange:
    """What happened to one rule between a checkpoint and now (CON-15)."""

    ref: str | None
    name: str
    status: str
    """`added`, `retired`, `revised`, or `unchanged`."""
    from_version: int | None = None
    to_version: int | None = None
    detail: str | None = None
    """Why, when there is something to say — a retirement's reason."""


class Checkpoints:
    """Taking checkpoints and comparing the catalogue against them."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def take(
        self, label: str, taken_by: str, attribution: str = "stated"
    ) -> Checkpoint:
        """Freeze which rules stand now, at which versions.

        Retired rules are **excluded**: a checkpoint records the product as it
        stood, and a rule a person has taken out of the picture was not part of
        it (CON-83). A rule retired *after* a checkpoint is therefore a change
        the comparison reports, which is the behaviour wanted.
        """
        cleaned = label.strip()
        if not cleaned:
            raise InvalidInput(
                "a checkpoint needs a label. It is how a person refers to the "
                "state they agreed to — a date, a release, a meeting."
            )

        standing = self._workspace.execute(
            "SELECT r.id AS rule_id, MAX(v.version_no) AS version_no "
            "FROM rule r JOIN rule_version v ON v.rule_id = r.id "
            "WHERE r.id NOT IN (SELECT rule_id FROM rule_retirement) "
            "GROUP BY r.id"
        ).fetchall()

        highest = self._workspace.execute(
            "SELECT MAX(CAST(SUBSTR(ref, 3) AS INTEGER)) AS top FROM checkpoint "
            "WHERE ref LIKE 'C-%'"
        ).fetchone()
        ref = f"C-{(highest['top'] or 0) + 1}"
        now = utc_now()

        with self._workspace.transaction() as ws:
            cursor = ws.execute(
                "INSERT INTO checkpoint "
                "(ref, label, taken_by, attribution, taken_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (ref, cleaned, taken_by, attribution, now),
            )
            checkpoint_id = int(cursor.lastrowid)
            for row in standing:
                version = ws.execute(
                    "SELECT id FROM rule_version WHERE rule_id = ? "
                    "AND version_no = ?",
                    (row["rule_id"], row["version_no"]),
                ).fetchone()
                ws.execute(
                    "INSERT INTO checkpoint_rule "
                    "(checkpoint_id, rule_id, rule_version_id) VALUES (?, ?, ?)",
                    (checkpoint_id, row["rule_id"], int(version["id"])),
                )

        return Checkpoint(
            id=checkpoint_id,
            ref=ref,
            label=cleaned,
            taken_by=taken_by,
            attribution=attribution,
            taken_at=now,
            rule_count=len(standing),
        )

    def list(self) -> tuple[Checkpoint, ...]:
        """Every checkpoint, oldest first."""
        rows = self._workspace.execute(
            "SELECT c.*, COUNT(cr.id) AS rule_count FROM checkpoint c "
            "LEFT JOIN checkpoint_rule cr ON cr.checkpoint_id = c.id "
            "GROUP BY c.id ORDER BY c.id"
        ).fetchall()
        return tuple(
            Checkpoint(
                id=int(row["id"]),
                ref=row["ref"],
                label=row["label"],
                taken_by=row["taken_by"],
                attribution=row["attribution"],
                taken_at=row["taken_at"],
                rule_count=int(row["rule_count"]),
            )
            for row in rows
        )

    def latest(self) -> Checkpoint | None:
        found = self.list()
        return found[-1] if found else None

    def find(self, ref: str) -> Checkpoint | None:
        return next((c for c in self.list() if c.ref == ref), None)

    def changes_since(self, checkpoint: Checkpoint) -> tuple[RuleChange, ...]:
        """What changed in the catalogue since this checkpoint was taken.

        Compared by **rule id and version number**, never by statement text. A
        rule whose wording a later version rephrased has changed; a rule nobody
        touched has not; and only the stored version numbers can tell those
        apart — which is why a checkpoint records the version rather than the
        rule.

        Four outcomes, kept apart because a reviewer's next move differs for
        each: `added`, `retired`, `revised`, `unchanged`.
        """
        before = {
            int(row["rule_id"]): int(row["version_no"])
            for row in self._workspace.execute(
                "SELECT cr.rule_id, v.version_no FROM checkpoint_rule cr "
                "JOIN rule_version v ON v.id = cr.rule_version_id "
                "WHERE cr.checkpoint_id = ?",
                (checkpoint.id,),
            ).fetchall()
        }
        now = {
            int(row["rule_id"]): row
            for row in self._workspace.execute(
                "SELECT r.id AS rule_id, r.ref, r.name, "
                "       MAX(v.version_no) AS version_no, t.reason "
                "FROM rule r JOIN rule_version v ON v.rule_id = r.id "
                "LEFT JOIN rule_retirement t ON t.rule_id = r.id "
                "GROUP BY r.id"
            ).fetchall()
        }

        changes: list[RuleChange] = []
        for rule_id, row in sorted(now.items()):
            was = before.get(rule_id)
            version = int(row["version_no"])
            if row["reason"] is not None:
                # Retired. Reported only when it was *in* the checkpoint: a
                # rule accepted and retired since would otherwise read as
                # something the product lost, when the product never had it in
                # the state being compared against.
                if was is not None:
                    changes.append(
                        RuleChange(
                            ref=row["ref"],
                            name=row["name"],
                            status="retired",
                            from_version=was,
                            detail=row["reason"],
                        )
                    )
                continue
            if was is None:
                changes.append(
                    RuleChange(
                        ref=row["ref"],
                        name=row["name"],
                        status="added",
                        to_version=version,
                    )
                )
            elif version != was:
                changes.append(
                    RuleChange(
                        ref=row["ref"],
                        name=row["name"],
                        status="revised",
                        from_version=was,
                        to_version=version,
                    )
                )
            else:
                changes.append(
                    RuleChange(
                        ref=row["ref"],
                        name=row["name"],
                        status="unchanged",
                        from_version=was,
                        to_version=version,
                    )
                )
        return tuple(changes)

    def require(self, ref: str | None) -> Checkpoint:
        """The named checkpoint, or the most recent one.

        Refuses rather than inventing an empty comparison: "nothing has changed
        since a checkpoint that does not exist" is the confidently-wrong answer
        this product exists to avoid.
        """
        if ref is not None:
            found = self.find(ref)
            if found is None:
                raise NotRegistered(
                    f"no checkpoint {ref!r}. See them with `constat checkpoint list`."
                )
            return found

        found = self.latest()
        if found is None:
            raise NotRegistered(
                "no checkpoint has been taken, so there is no approved state "
                "to compare against. Take one with `constat checkpoint take`."
            )
        return found
