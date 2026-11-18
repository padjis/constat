"""A rule's details are tracked across versions (CON-67, D-078).

A version's substance became readable at CON-61 and examples arrived at
CON-80, so two versions can now be compared. What was missing was an
*identity*: position cannot serve, because "the second example changed" means
something different the moment an earlier one is removed. D-043 already
required durable identities rather than positions in text; this supplies them.

Identity is the detail's text — a behaviour's description, an example's
situation — recorded as a number at acceptance. Four properties carry these
tests:

1. **A number is never reused.** The high-water mark is the append-only
   version table, not the live one, so a removed detail's number cannot come
   back attached to something unrelated.
2. **A changed outcome reads as `changed`, not as remove-plus-add.** That is
   the case a reviewer most needs to see, and it is only visible because the
   outcome is excluded from identity.
3. **Position is not identity.** Removing an earlier detail must not make a
   later one read as changed.
4. **A detail with no number is not compared.** Accepted before schema 15,
   never numbered; matching it today and presenting the result as history
   would be this code's guess wearing the costume of a record.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.models import Anchor, Behaviour, Example, RuleProposal
from constat.operations import open_run
from constat.store import Catalogue, Registry, Review, RuleProposals, TicketStore, Workspace
from constat.store.schema import SCHEMA_VERSION

from helpers import rewind_workspace
from test_runs import distinct_subject


REFERENCE = "615"
STATEMENT = "A transfer above the daily limit is refused."


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
        )
        TicketStore(ws).add(REFERENCE)
        yield ws


def _accept(
    workspace,
    examples: tuple[tuple[str, str], ...],
    behaviours: tuple[str, ...] = ("Refuse it",),
    revises: int | None = None,
) -> int:
    """Submit and accept one reading. Returns the rule id."""
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    proposal_id = RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name="daily-limit",
            statement=STATEMENT,
            behaviours=tuple(Behaviour(description=b) for b in behaviours),
            examples=tuple(
                Example(situation=s, outcome=o) for s, o in examples
            ),
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            area="payments",
            relation="revises" if revises else "establishes",
            revises_rule_id=revises,
        ),
        provider="mcp",
        model="claude-opus-5",
        revises_rule_id=revises,
    )
    return Review(workspace).accept(proposal_id, decided_by="a person").rule_id


def _numbers(review, rule_id: int) -> list[list[int | None]]:
    return [
        [e.number for e in version["examples"]]
        for version in review.versions(rule_id)
    ]


def _statuses(diff) -> dict[int | None, str]:
    return {c.number: c.status for c in diff.examples}


# -- numbering ----------------------------------------------------------------


class TestNumbering:
    def test_details_are_numbered_from_one(self, workspace) -> None:
        rule_id = _accept(
            workspace, (("A transfer of 240", "Accepted"), ("A transfer of 600", "Refused"))
        )

        assert _numbers(Review(workspace), rule_id) == [[1, 2]]

    def test_a_reading_carries_no_numbers(self, workspace) -> None:
        """A number is spent at acceptance, not at submission: numbering a
        proposal would commit an identity to something that may be rejected."""
        run_id = open_run(workspace, REFERENCE, "submit_reply")
        proposal_id = RuleProposals(workspace).record(
            run_id,
            RuleProposal(
                name="daily-limit",
                statement=STATEMENT,
                examples=(Example(situation="A transfer of 600", outcome="Refused"),),
                anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            ),
            provider="mcp",
        )

        stored = next(
            p
            for p in RuleProposals(workspace).for_ticket(REFERENCE)
            if p.id == proposal_id
        )
        assert stored.proposal.examples[0].number is None

    def test_an_unchanged_situation_keeps_its_number(self, workspace) -> None:
        rule_id = _accept(
            workspace, (("A transfer of 240", "Accepted"), ("A transfer of 600", "Refused"))
        )
        _accept(
            workspace,
            (("A transfer of 240", "Accepted"), ("A transfer of 600", "Refused, limit shown")),
            revises=rule_id,
        )

        assert _numbers(Review(workspace), rule_id) == [[1, 2], [1, 2]]

    def test_a_new_situation_takes_the_next_number(self, workspace) -> None:
        rule_id = _accept(workspace, (("A transfer of 240", "Accepted"),))
        _accept(
            workspace,
            (("A transfer of 240", "Accepted"), ("A transfer of 600", "Refused")),
            revises=rule_id,
        )

        assert _numbers(Review(workspace), rule_id) == [[1], [1, 2]]

    def test_two_new_details_in_one_acceptance_do_not_collide(
        self, workspace
    ) -> None:
        rule_id = _accept(workspace, (("A transfer of 240", "Accepted"),))
        _accept(
            workspace,
            (
                ("A transfer of 240", "Accepted"),
                ("A transfer of 600", "Refused"),
                ("A refund of 400", "Accepted"),
            ),
            revises=rule_id,
        )

        assert _numbers(Review(workspace), rule_id)[-1] == [1, 2, 3]

    def test_behaviours_are_numbered_independently_of_examples(
        self, workspace
    ) -> None:
        """Two sequences, not one. Sharing a counter would make a behaviour's
        number depend on how many examples happened to be accepted first."""
        rule_id = _accept(
            workspace,
            (("A transfer of 240", "Accepted"),),
            behaviours=("Refuse it", "Explain the limit"),
        )

        version = Review(workspace).versions(rule_id)[0]
        assert [b.number for b in version["behaviour_details"]] == [1, 2]
        assert [e.number for e in version["examples"]] == [1]


class TestNumbersAreNeverReused:
    def test_a_removed_number_does_not_come_back(self, workspace) -> None:
        """The property the whole design rests on.

        The live `example` table is deleted and rewritten on every acceptance,
        so its maximum forgets every detail a rule ever dropped. Taking the
        high-water mark from there would hand number 2 to an unrelated case,
        and the diff would then claim a case had been *edited* when it had been
        replaced — a false statement about what a reviewer agreed to.
        """
        rule_id = _accept(
            workspace,
            (("A transfer of 240", "Accepted"), ("A transfer of 600", "Refused")),
        )
        # Drop example 2.
        _accept(workspace, (("A transfer of 240", "Accepted"),), revises=rule_id)
        # Add a different case: it must not take number 2.
        _accept(
            workspace,
            (("A transfer of 240", "Accepted"), ("A refund of 400", "Accepted")),
            revises=rule_id,
        )

        assert _numbers(Review(workspace), rule_id) == [[1, 2], [1], [1, 3]]

    def test_a_restored_situation_gets_its_old_number_back(
        self, workspace
    ) -> None:
        """Not a contradiction of the rule above: identity is the text, so the
        same situation returning *is* the same example, and giving it a new
        number would claim a case was replaced when it was reinstated."""
        rule_id = _accept(
            workspace,
            (("A transfer of 240", "Accepted"), ("A transfer of 600", "Refused")),
        )
        _accept(workspace, (("A transfer of 240", "Accepted"),), revises=rule_id)
        _accept(
            workspace,
            (("A transfer of 240", "Accepted"), ("A transfer of 600", "Refused")),
            revises=rule_id,
        )

        assert _numbers(Review(workspace), rule_id) == [[1, 2], [1], [1, 2]]


# -- the diff -----------------------------------------------------------------


class TestDiff:
    def test_the_first_version_differs_from_nothing(self, workspace) -> None:
        rule_id = _accept(workspace, (("A transfer of 600", "Refused"),))

        diff = Review(workspace).diffs(rule_id)[0]

        assert diff.is_first
        assert _statuses(diff) == {1: "added"}

    def test_a_changed_outcome_reads_as_changed(self, workspace) -> None:
        """The case this ticket exists for. If identity included the outcome,
        this would read as one example removed and another added, and the one
        thing a reviewer needs to notice would be the thing it hid."""
        rule_id = _accept(workspace, (("A transfer of 600", "Refused"),))
        _accept(
            workspace, (("A transfer of 600", "Refused, limit shown"),), revises=rule_id
        )

        change = Review(workspace).diffs(rule_id)[1].examples[0]

        assert change.status == "changed"
        assert change.was == "A transfer of 600 → Refused"
        assert change.text == "A transfer of 600 → Refused, limit shown"

    def test_an_untouched_detail_reads_as_unchanged(self, workspace) -> None:
        rule_id = _accept(
            workspace,
            (("A transfer of 240", "Accepted"), ("A transfer of 600", "Refused")),
        )
        _accept(
            workspace,
            (("A transfer of 240", "Accepted"), ("A transfer of 600", "Refused, limit shown")),
            revises=rule_id,
        )

        assert _statuses(Review(workspace).diffs(rule_id)[1]) == {
            1: "unchanged",
            2: "changed",
        }

    def test_removing_an_earlier_detail_does_not_shift_the_others(
        self, workspace
    ) -> None:
        """Position is not identity. Under a positional comparison, dropping
        example 1 makes example 2 slide into first place and read as changed —
        a wrong claim about a case nobody touched."""
        rule_id = _accept(
            workspace,
            (("A transfer of 240", "Accepted"), ("A transfer of 600", "Refused")),
        )
        _accept(workspace, (("A transfer of 600", "Refused"),), revises=rule_id)

        assert _statuses(Review(workspace).diffs(rule_id)[1]) == {
            1: "removed",
            2: "unchanged",
        }

    def test_a_removal_is_reported(self, workspace) -> None:
        rule_id = _accept(
            workspace,
            (("A transfer of 240", "Accepted"), ("A transfer of 600", "Refused")),
        )
        _accept(workspace, (("A transfer of 240", "Accepted"),), revises=rule_id)

        change = [
            c for c in Review(workspace).diffs(rule_id)[1].examples if c.status == "removed"
        ][0]
        assert change.number == 2
        assert "A transfer of 600" in change.text

    def test_behaviours_are_diffed_too(self, workspace) -> None:
        rule_id = _accept(
            workspace,
            (("A transfer of 600", "Refused"),),
            behaviours=("Refuse it",),
        )
        _accept(
            workspace,
            (("A transfer of 600", "Refused"),),
            behaviours=("Refuse it", "Notify the account holder"),
            revises=rule_id,
        )

        statuses = {c.number: c.status for c in Review(workspace).diffs(rule_id)[1].behaviours}
        assert statuses == {1: "unchanged", 2: "added"}


class TestTheStatedLimit:
    def test_a_rewording_reads_as_a_replacement(self, workspace) -> None:
        """The cost of taking identity from the text, asserted rather than
        hidden. A reviewer sees one removed and one added, not an edit."""
        rule_id = _accept(workspace, (("A transfer of 600 euros", "Refused"),))
        _accept(workspace, (("A transfer of 600 EUR", "Refused"),), revises=rule_id)

        assert _statuses(Review(workspace).diffs(rule_id)[1]) == {
            1: "removed",
            2: "added",
        }

    def test_the_diff_knows_to_warn_about_it(self, workspace) -> None:
        rule_id = _accept(workspace, (("A transfer of 600 euros", "Refused"),))
        _accept(workspace, (("A transfer of 600 EUR", "Refused"),), revises=rule_id)

        assert Review(workspace).diffs(rule_id)[1].rewording_is_indistinguishable

    def test_it_does_not_warn_when_nothing_was_replaced(self, workspace) -> None:
        rule_id = _accept(workspace, (("A transfer of 600", "Refused"),))
        _accept(
            workspace, (("A transfer of 600", "Refused, limit shown"),), revises=rule_id
        )

        assert not Review(workspace).diffs(rule_id)[1].rewording_is_indistinguishable


class TestUnnumberedDetails:
    def test_details_accepted_before_schema_15_are_not_compared(
        self, tmp_path: Path
    ) -> None:
        """Reported as `unnumbered`, never matched. A match made today and
        presented as a diff would be this code's guess rendered as history —
        the same reason no migration back-fills a number."""
        home = tmp_path / "ws"
        with Workspace.create(home) as ws:
            Registry(ws).add(
                str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")),
                alias="billing",
            )
            TicketStore(ws).add(REFERENCE)
            _accept(ws, (("A transfer of 600", "Refused"),))

        rewind_workspace(home / "workspace.db", 14)

        with Workspace.open(home) as ws:
            assert ws.schema_version == SCHEMA_VERSION
            rule = Catalogue(ws).find("daily-limit")
            assert rule.examples[0].number is None

            diff = Review(ws).diffs(1)[0]
            assert [c.status for c in diff.examples] == ["unnumbered"]

    def test_the_migration_adds_the_columns_without_back_filling(
        self, tmp_path: Path
    ) -> None:
        home = tmp_path / "ws"
        with Workspace.create(home) as ws:
            Registry(ws).add(
                str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")),
                alias="billing",
            )
            TicketStore(ws).add(REFERENCE)
            _accept(ws, (("A transfer of 600", "Refused"),))

        rewind_workspace(home / "workspace.db", 14)

        with Workspace.open(home) as ws:
            row = ws.execute(
                "SELECT example_no FROM rule_version_example"
            ).fetchone()
            assert row["example_no"] is None
