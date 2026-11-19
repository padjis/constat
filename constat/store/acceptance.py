"""Accepting or rejecting a rule proposal (CON-44).

Acceptance is the only way a rule enters or changes in the catalogue (D-048),
and it is a human act — nothing here can be reached by a model.

**Accepting creates a version, never a mutation of history.** `rule` holds the
current state and `rule_version` the frozen record, the same split
`document`/`document_version` already uses (D-029). A later acceptance of a
reading that revises the rule appends version 2; version 1 stays readable
forever, pointing at the reading a human accepted to produce it.

**Rejecting changes nothing.** Under D-036 it means *inconclusive* — another
PR is expected — not "this rule is wrong" and not "never propose this again".
So it records a decision and leaves the catalogue alone.

**Which rule a reading revises is the reading's claim, not a key** (D-050). A
human accepting it is accepting that claim too, which is why acceptance is the
only place the claim takes effect.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import InvalidInput, NotRegistered
from ..models import Anchor, Behaviour, Example, Message
from .proposals import RuleProposals, StoredRuleProposal
from .workspace import Workspace, utc_now


def _compare(before, after, text) -> tuple[DetailChange, ...]:
    """Match two versions' details by number and say what moved.

    Identity is the number, which acceptance assigned by matching the
    detail's text — a behaviour's description, an example's situation. `text`
    renders the whole detail, so an example's *outcome* is compared but is not
    part of its identity. That asymmetry is the point: a changed outcome under
    an unchanged situation is the case a reviewer most needs to see, and it is
    only visible if identity excludes it.
    """
    changes: list[DetailChange] = []
    earlier = {d.number: d for d in (before or ()) if d.number is not None}
    later = {d.number: d for d in after if d.number is not None}

    for detail in after:
        if detail.number is None:
            # Accepted before schema 15 and never numbered. Reported, not
            # compared: a match made today is this code's guess, not history.
            changes.append(
                DetailChange(number=None, status="unnumbered", text=text(detail))
            )
            continue
        was = earlier.get(detail.number)
        if was is None:
            changes.append(
                DetailChange(
                    number=detail.number, status="added", text=text(detail)
                )
            )
        elif text(was) != text(detail):
            changes.append(
                DetailChange(
                    number=detail.number,
                    status="changed",
                    text=text(detail),
                    was=text(was),
                )
            )
        else:
            changes.append(
                DetailChange(
                    number=detail.number, status="unchanged", text=text(detail)
                )
            )

    for number, detail in earlier.items():
        if number not in later:
            changes.append(
                DetailChange(number=number, status="removed", text=text(detail))
            )

    return tuple(sorted(changes, key=lambda c: (c.number is None, c.number or 0)))


@dataclass(frozen=True)
class DetailChange:
    """What happened to one numbered detail between two versions (CON-67).

    `number` is None only for a detail accepted before schema 15, which was
    never numbered. Such a detail is reported as `unnumbered` rather than
    compared: matching it today and presenting the result as history would be
    this code's guess wearing the costume of a record.
    """

    number: int | None
    status: str
    """`added`, `removed`, `changed`, `unchanged`, or `unnumbered`."""
    text: str
    """The detail as the later version has it, or as the earlier one did when
    it was removed."""
    was: str | None = None
    """What it said before, set only when `status` is `changed`."""


@dataclass(frozen=True)
class VersionDiff:
    """How one version differs from the one before it."""

    version_no: int
    behaviours: tuple[DetailChange, ...] = ()
    examples: tuple[DetailChange, ...] = ()
    is_first: bool = False
    """The first version has nothing to differ from. Its details are reported
    as `added` and the renderer says so, because "everything was added" and
    "everything changed" are different claims."""

    @property
    def rewording_is_indistinguishable(self) -> bool:
        """Whether this diff contains both a removal and an addition.

        When it does, the output has to say that a reworded situation reads as
        a replacement: identity comes from the text (D-078), so a reviewer
        cannot otherwise tell a dropped case from a rephrased one. The limit is
        printed rather than left in a decision entry nobody reads at the
        terminal.
        """
        statuses = {c.status for c in self.examples + self.behaviours}
        return "removed" in statuses and "added" in statuses


@dataclass(frozen=True)
class Retirement:
    """A rule a human has decided no longer describes the product (CON-83)."""

    rule_id: int
    reason: str
    decided_by: str
    attribution: str
    decided_at: str


@dataclass(frozen=True)
class Acceptance:
    """What accepting a rule proposal produced."""

    rule_id: int
    rule_version_id: int
    version_no: int
    created_rule: bool

    @property
    def is_revision(self) -> bool:
        return not self.created_rule


class Review:
    """A human's answers to rule proposals."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace
        self._proposals = RuleProposals(workspace)

    def accept(
        self,
        proposal_id: int,
        decided_by: str,
        rationale: str | None = None,
        attribution: str = "stated",
    ) -> Acceptance:
        """Accept a reading: record the decision and baseline a rule version."""
        stored = self._require(proposal_id)
        if stored.decision == "accepted":
            raise InvalidInput(
                f"rule proposal {proposal_id} is already accepted. Accepting "
                "it again would baseline a second identical version."
            )

        rule_id, created = self._target_rule(stored)
        version_id, version_no = self._baseline(rule_id, stored)
        self._proposals.decide(
            proposal_id, "accepted", decided_by, rationale, attribution
        )
        return Acceptance(
            rule_id=rule_id,
            rule_version_id=version_id,
            version_no=version_no,
            created_rule=created,
        )

    def retire(
        self,
        rule_id: int,
        reason: str,
        decided_by: str,
        attribution: str = "stated",
    ) -> Retirement:
        """Retire a rule: record that it no longer describes the product.

        **A human decision, in the same sense acceptance is.** A rule leaves
        the current picture only because somebody says so — D-070 already said
        a rule whose anchors have vanished is a *retirement candidate, never a
        retirement*, and this is the other half of that sentence. Nothing
        automatic retires anything.

        **A decision, not a deletion.** The rule, its versions, its citation
        and its evidence stay readable. `rule` cannot be deleted at all (the
        trigger aborts it), and that is deliberate: product rule 5 makes
        history durable, and a catalogue that forgets what it used to claim
        cannot be audited.

        **Final.** The table is append-only with no reinstatement row, so
        bringing the behaviour back means accepting a new reading as a new
        rule. That is a decision somebody makes rather than a flag somebody
        clears, and it leaves both the retirement and the return in the record.

        A `reason` is required rather than optional, because the interesting
        retirements are the ones nothing else can express — in particular a
        *lapsed condition* (D-071): a rule conditional on a business state
        becomes false when that state changes, and no edit to the statement can
        say so.
        """
        cleaned = reason.strip()
        if not cleaned:
            raise InvalidInput(
                "a retirement needs a reason. It is the only record of why the "
                "product stopped behaving this way, and the rule itself cannot "
                "say so."
            )

        row = self._workspace.execute(
            "SELECT id FROM rule WHERE id = ?", (rule_id,)
        ).fetchone()
        if row is None:
            raise NotRegistered(f"no rule with id {rule_id}")

        already = self.retirement_of(rule_id)
        if already is not None:
            raise InvalidInput(
                f"rule {rule_id} was already retired on {already.decided_at} "
                f"by {already.decided_by}. A retirement is final: accept a new "
                "rule proposal if the behaviour has come back."
            )

        now = utc_now()
        self._workspace.execute(
            "INSERT INTO rule_retirement "
            "(rule_id, reason, decided_by, attribution, decided_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (rule_id, cleaned, decided_by, attribution, now),
        )
        return Retirement(
            rule_id=rule_id,
            reason=cleaned,
            decided_by=decided_by,
            attribution=attribution,
            decided_at=now,
        )

    def retirement_of(self, rule_id: int) -> Retirement | None:
        """The retirement of a rule, or None if it still stands."""
        row = self._workspace.execute(
            "SELECT rule_id, reason, decided_by, attribution, decided_at "
            "FROM rule_retirement WHERE rule_id = ? ORDER BY id LIMIT 1",
            (rule_id,),
        ).fetchone()
        if row is None:
            return None
        return Retirement(
            rule_id=int(row["rule_id"]),
            reason=row["reason"],
            decided_by=row["decided_by"],
            attribution=row["attribution"],
            decided_at=row["decided_at"],
        )

    def reject(
        self,
        proposal_id: int,
        decided_by: str,
        rationale: str | None = None,
        attribution: str = "stated",
    ) -> None:
        """Reject a reading as inconclusive (D-036).

        Deliberately changes nothing in the catalogue. Rejection is not a
        statement that the rule is wrong, so there is nothing to unwind — and
        a later reading of better evidence is expected rather than precluded.
        """
        self._require(proposal_id)
        self._proposals.decide(
            proposal_id, "rejected", decided_by, rationale, attribution
        )

    # -- internals ---------------------------------------------------------

    def _require(self, proposal_id: int) -> StoredRuleProposal:
        stored = self._proposals.find(proposal_id)
        if stored is None:
            raise NotRegistered(f"no rule proposal with id {proposal_id}")
        return stored

    def _target_rule(self, stored: StoredRuleProposal) -> tuple[int, bool]:
        """The rule this reading becomes a version of, creating it if new."""
        if stored.revises_rule_id is not None:
            row = self._workspace.execute(
                "SELECT id FROM rule WHERE id = ?", (stored.revises_rule_id,)
            ).fetchone()
            if row is None:
                # The claim named a rule that is not there. Refused rather
                # than silently creating a new rule: the reviewer accepted a
                # revision, and quietly giving them a separate rule instead is
                # the duplicate CON-43 exists to prevent.
                raise NotRegistered(
                    f"rule proposal claims to revise rule "
                    f"{stored.revises_rule_id}, which does not exist."
                )
            retired = self.retirement_of(int(row["id"]))
            if retired is not None:
                # Revising a retired rule is a contradiction: a new version
                # would be the current state of something a human has said is
                # no longer the product's behaviour. Refused with the route
                # back named, rather than resurrected silently (CON-83).
                raise InvalidInput(
                    f"rule {row['id']} was retired on {retired.decided_at} and "
                    "cannot be revised. Accept this reading as a new rule "
                    "instead: a retirement is final, and the way behaviour "
                    "comes back is a new rule with its own citation."
                )
            return int(row["id"]), False

        # The citation is assigned here because this is the one place a rule
        # comes into being (D-048). The high-water mark is `rule` itself, which
        # is sound without qualification: a rule can never be deleted (the
        # trigger aborts it), so the table *is* the whole history and a
        # citation can never be reused.
        highest = self._workspace.execute(
            "SELECT MAX(CAST(SUBSTR(ref, 3) AS INTEGER)) AS top FROM rule "
            "WHERE ref LIKE 'R-%'"
        ).fetchone()
        ref = f"R-{(highest['top'] or 0) + 1}"

        cursor = self._workspace.execute(
            "INSERT INTO rule (ref, name, statement, area, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                ref,
                stored.proposal.name,
                stored.proposal.statement,
                stored.proposal.area,
                utc_now(),
            ),
        )
        return int(cursor.lastrowid), True

    def _baseline(
        self, rule_id: int, stored: StoredRuleProposal
    ) -> tuple[int, int]:
        """Freeze this reading as the rule's next version, and make it current."""
        previous = self._workspace.execute(
            "SELECT id, version_no FROM rule_version WHERE rule_id = ? "
            "ORDER BY version_no DESC LIMIT 1",
            (rule_id,),
        ).fetchone()
        version_no = 1 if previous is None else int(previous["version_no"]) + 1
        previous_id = None if previous is None else int(previous["id"])
        now = utc_now()

        with self._workspace.transaction() as ws:
            cursor = ws.execute(
                "INSERT INTO rule_version "
                "(rule_id, version_no, name, statement, area, "
                " from_rule_proposal_id, previous_version_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rule_id,
                    version_no,
                    stored.proposal.name,
                    stored.proposal.statement,
                    stored.proposal.area,
                    stored.id,
                    previous_id,
                    now,
                ),
            )
            version_id = int(cursor.lastrowid)

            # Durable numbers, assigned here and nowhere else (CON-67). A
            # reading carries none: numbering a proposal would spend an
            # identity on something that may be rejected.
            behaviour_nos = self._assign_numbers(
                ws,
                rule_id,
                keys=[b.description for b in stored.proposal.behaviours],
                table="rule_version_behaviour",
                column="behaviour_no",
                key_column="description",
            )
            example_nos = self._assign_numbers(
                ws,
                rule_id,
                keys=[e.situation for e in stored.proposal.examples],
                table="rule_version_example",
                column="example_no",
                key_column="situation",
            )

            for behaviour, number in zip(stored.proposal.behaviours, behaviour_nos):
                ws.execute(
                    "INSERT INTO rule_version_behaviour "
                    "(rule_version_id, behaviour_no, description) VALUES (?, ?, ?)",
                    (version_id, number, behaviour.description),
                )
            message_ids = [
                self._message_id(ws, message.text)
                for message in stored.proposal.messages
            ]
            for message_id in message_ids:
                ws.execute(
                    "INSERT INTO rule_version_message "
                    "(rule_version_id, message_id) VALUES (?, ?)",
                    (version_id, message_id),
                )
            for example, number in zip(stored.proposal.examples, example_nos):
                ws.execute(
                    "INSERT INTO rule_version_example "
                    "(rule_version_id, example_no, situation, outcome) "
                    "VALUES (?, ?, ?, ?)",
                    (version_id, number, example.situation, example.outcome),
                )
            for anchor in stored.proposal.anchors:
                ws.execute(
                    "INSERT INTO rule_version_anchor "
                    "(rule_version_id, repository_id, path_glob, grounded_in) "
                    "VALUES (?, (SELECT id FROM repository WHERE alias = ?), ?, ?)",
                    (
                        version_id,
                        anchor.repository_alias,
                        anchor.path_glob,
                        anchor.grounded_in,
                    ),
                )

            # The current state follows the new version. `rule` is mutable for
            # the same reason `document` is: it is the working view, and the
            # durable record is the frozen version beside it.
            ws.execute(
                "UPDATE rule SET name = ?, statement = ?, area = ? WHERE id = ?",
                (
                    stored.proposal.name,
                    stored.proposal.statement,
                    stored.proposal.area,
                    rule_id,
                ),
            )
            ws.execute("DELETE FROM rule_message WHERE rule_id = ?", (rule_id,))
            for message_id in message_ids:
                ws.execute(
                    "INSERT INTO rule_message (rule_id, message_id) VALUES (?, ?)",
                    (rule_id, message_id),
                )
            ws.execute("DELETE FROM behaviour WHERE rule_id = ?", (rule_id,))
            ws.execute("DELETE FROM example WHERE rule_id = ?", (rule_id,))
            ws.execute("DELETE FROM anchor WHERE rule_id = ?", (rule_id,))
            for behaviour, number in zip(stored.proposal.behaviours, behaviour_nos):
                ws.execute(
                    "INSERT INTO behaviour "
                    "(rule_id, behaviour_no, description, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (rule_id, number, behaviour.description, now),
                )
            for example, number in zip(stored.proposal.examples, example_nos):
                ws.execute(
                    "INSERT INTO example "
                    "(rule_id, example_no, situation, outcome, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (rule_id, number, example.situation, example.outcome, now),
                )
            for anchor in stored.proposal.anchors:
                ws.execute(
                    "INSERT INTO anchor "
                    "(rule_id, repository_id, path_glob, grounded_in, created_at) "
                    "VALUES (?, (SELECT id FROM repository WHERE alias = ?), ?, ?, ?)",
                    (
                        rule_id,
                        anchor.repository_alias,
                        anchor.path_glob,
                        anchor.grounded_in,
                        now,
                    ),
                )

        return version_id, version_no

    @staticmethod
    def _message_id(ws, text: str) -> int:
        """The id of the message with this exact text, minting it if new.

        **Found before minted**, which is what makes a message live once
        (CON-82): the same wording shows under several rules, and a second copy
        is how two wordings come to disagree. Matching is on the exact text,
        because that is what a message *is* — a near-match is a different
        message, and deciding otherwise is a judgement no gate here is entitled
        to make.

        The citation is minted only for genuinely new text, from the greatest
        one in the table. `message` has no delete path, so that is the whole
        history and a citation is never reused.
        """
        found = ws.execute(
            "SELECT id FROM message WHERE text = ?", (text,)
        ).fetchone()
        if found is not None:
            return int(found["id"])

        highest = ws.execute(
            "SELECT MAX(CAST(SUBSTR(ref, 3) AS INTEGER)) AS top FROM message "
            "WHERE ref LIKE 'M-%'"
        ).fetchone()
        ref = f"M-{(highest['top'] or 0) + 1}"
        cursor = ws.execute(
            "INSERT INTO message (ref, text, created_at) VALUES (?, ?, ?)",
            (ref, text, utc_now()),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _assign_numbers(
        ws,
        rule_id: int,
        keys: list[str],
        table: str,
        column: str,
        key_column: str,
    ) -> list[int]:
        """Durable numbers for a rule's details, by matching their text (CON-67).

        A detail whose text this rule has carried before keeps the number it
        had; a new one takes the next number the rule has never used. That is
        what lets two versions be compared: the same number in both means the
        same detail, so a changed outcome reads as *changed* rather than as one
        detail removed and another added.

        **The high-water mark comes from the version table, not the live one.**
        The live table is deleted and rewritten on every acceptance, so its
        maximum forgets every detail a rule ever dropped — and the next
        acceptance would hand a retired number to something unrelated, silently
        making a diff claim that a case had been edited when it had been
        replaced. The version tables are append-only, so their maximum is the
        whole history.

        Why text and not a claim: see D-078. The cost is that a reworded
        situation is a different detail, which the history states rather than
        papers over.
        """
        known = {
            row[key_column]: row[column]
            for row in ws.execute(
                f"SELECT DISTINCT d.{key_column}, d.{column} FROM {table} d "
                f"JOIN rule_version v ON v.id = d.rule_version_id "
                f"WHERE v.rule_id = ? AND d.{column} IS NOT NULL",
                (rule_id,),
            ).fetchall()
        }
        highest = ws.execute(
            f"SELECT MAX(d.{column}) AS top FROM {table} d "
            f"JOIN rule_version v ON v.id = d.rule_version_id "
            f"WHERE v.rule_id = ?",
            (rule_id,),
        ).fetchone()
        nxt = (highest["top"] or 0) + 1

        numbers: list[int] = []
        for key in keys:
            if key in known:
                numbers.append(int(known[key]))
                continue
            numbers.append(nxt)
            # Recorded as we go: two new details in one acceptance must not
            # both take the same number.
            known[key] = nxt
            nxt += 1
        return numbers

    # -- reading -----------------------------------------------------------

    def versions(self, rule_id: int) -> tuple[dict, ...]:
        """Every accepted version of a rule, oldest first, with its substance.

        Returned as plain rows: this is the audit view, and a reviewer reading
        history wants what was recorded rather than a reconstructed object.

        **Behaviours and anchors come from the version, never from the rule**
        (CON-61). `rule` holds the current state and is rewritten by each
        acceptance; `rule_version_behaviour` and `rule_version_anchor` are what
        a human agreed to at the time. Reading the live tables here would make
        every version in the history display the newest one's substance, which
        is the opposite of what CON-14 promises — and it would look right.
        """
        rows = self._workspace.execute(
            "SELECT v.id, v.version_no, v.name, v.statement, v.area, v.created_at, "
            "       v.from_rule_proposal_id, d.decided_by, d.attribution, "
            "       d.decided_at "
            "FROM rule_version v "
            "LEFT JOIN rule_proposal_decision d "
            "  ON d.rule_proposal_id = v.from_rule_proposal_id "
            " AND d.decision = 'accepted' "
            "WHERE v.rule_id = ? ORDER BY v.version_no",
            (rule_id,),
        ).fetchall()

        versions = []
        for row in rows:
            version = dict(row)
            version["behaviours"] = self.version_behaviours(row["id"])
            version["behaviour_details"] = self.version_behaviour_details(row["id"])
            version["messages"] = self.version_messages(row["id"])
            version["examples"] = self.version_examples(row["id"])
            version["anchors"] = self.version_anchors(row["id"])
            versions.append(version)
        return tuple(versions)

    def diffs(self, rule_id: int) -> tuple[VersionDiff, ...]:
        """How each version of a rule differs from the one before it (CON-67).

        Compared by number, never by position. A positional comparison reports
        "the second example changed" when an earlier one was removed and
        everything shifted up — a wrong claim about what a reviewer agreed to,
        and the reason D-043 requires durable identities.

        Read from the frozen version tables, so this is history rather than a
        reconstruction from the live catalogue (CON-61).
        """
        versions = self.versions(rule_id)
        diffs: list[VersionDiff] = []
        previous: dict | None = None

        for version in versions:
            diffs.append(
                VersionDiff(
                    version_no=int(version["version_no"]),
                    behaviours=_compare(
                        None if previous is None else previous["behaviour_details"],
                        version["behaviour_details"],
                        text=lambda b: b.description,
                    ),
                    examples=_compare(
                        None if previous is None else previous["examples"],
                        version["examples"],
                        text=lambda e: f"{e.situation} → {e.outcome}",
                    ),
                    is_first=previous is None,
                )
            )
            previous = version
        return tuple(diffs)

    def version_behaviours(self, rule_version_id: int) -> tuple[str, ...]:
        """What this version said the system does, as it was frozen."""
        rows = self._workspace.execute(
            "SELECT description FROM rule_version_behaviour "
            "WHERE rule_version_id = ? ORDER BY id",
            (rule_version_id,),
        ).fetchall()
        return tuple(row["description"] for row in rows)

    def version_behaviour_details(
        self, rule_version_id: int
    ) -> tuple[Behaviour, ...]:
        """The same behaviours, carrying their numbers (CON-67).

        Separate from `version_behaviours`, which returns bare strings and is
        what the existing callers want. A diff needs the numbers, and widening
        the old return type would have changed every caller to gain a field
        most of them ignore.
        """
        rows = self._workspace.execute(
            "SELECT behaviour_no, description FROM rule_version_behaviour "
            "WHERE rule_version_id = ? ORDER BY id",
            (rule_version_id,),
        ).fetchall()
        return tuple(
            Behaviour(description=row["description"], number=row["behaviour_no"])
            for row in rows
        )

    def version_messages(self, rule_version_id: int) -> tuple[Message, ...]:
        """The messages this version was accepted with, as frozen (CON-82).

        Through the link table to `message`, so the *text* read back is the
        text as it stands. Deliberate, and worth stating because it differs
        from behaviours and examples: a message is one entry shared by every
        rule that shows it, so correcting its wording corrects it everywhere.
        That is the point of storing it once, and the one piece of a version's
        substance that is not frozen against later change."""
        rows = self._workspace.execute(
            "SELECT m.ref, m.text FROM rule_version_message v "
            "JOIN message m ON m.id = v.message_id "
            "WHERE v.rule_version_id = ? ORDER BY v.id",
            (rule_version_id,),
        ).fetchall()
        return tuple(Message(text=row["text"], ref=row["ref"]) for row in rows)

    def version_examples(self, rule_version_id: int) -> tuple[Example, ...]:
        """The worked cases this version was accepted with, as frozen (CON-80).

        Read from `rule_version_example` for CON-61's reason, which applies
        here with more force than it does to behaviours: examples are the part
        of a rule a reviewer actually checked, so showing version 1 the
        examples of version 3 would misattribute the very thing they agreed to.
        """
        rows = self._workspace.execute(
            "SELECT example_no, situation, outcome FROM rule_version_example "
            "WHERE rule_version_id = ? ORDER BY id",
            (rule_version_id,),
        ).fetchall()
        return tuple(
            Example(
                situation=row["situation"],
                outcome=row["outcome"],
                number=row["example_no"],
            )
            for row in rows
        )

    def version_anchors(self, rule_version_id: int) -> tuple[Anchor, ...]:
        """Where this version said the rule lived, as it was frozen.

        Carries `grounded_in` (D-072), because which ground supported an anchor
        is part of what was accepted: a reviewer looking back has to be able to
        tell "the evidence showed this changed" from "this file existed".
        """
        rows = self._workspace.execute(
            "SELECT a.path_glob, a.grounded_in, r.alias "
            "FROM rule_version_anchor a "
            "LEFT JOIN repository r ON r.id = a.repository_id "
            "WHERE a.rule_version_id = ? ORDER BY a.id",
            (rule_version_id,),
        ).fetchall()
        return tuple(
            Anchor(
                path_glob=row["path_glob"],
                repository_alias=row["alias"],
                grounded_in=row["grounded_in"],
            )
            for row in rows
        )
