"""Comparing the catalogue against the last agreed state (CON-15, D-085).

The oldest open ticket in the register, and it was waiting on something
`constat state` deliberately is not: D-070 made that view *computed and stored
nowhere*, which is what keeps it always true of the revisions it names — and
also what left nothing to compare against.

Four properties carry these tests:

1. **Taken explicitly.** "The last approved state" needs a point somebody
   chose. Derived from the newest acceptance it would move every time a rule
   was accepted, and a moving reference point is no reference point.
2. **Compared by version, not by text.** A rule whose wording a later version
   rephrased has changed; one nobody touched has not. Only the stored version
   numbers tell those apart, which is why a checkpoint records the version
   rather than the rule.
3. **Four outcomes, kept apart**: added, retired, revised, unchanged. A
   reviewer's next move differs for each.
4. **No checkpoint is refused, never answered.** "Nothing has changed since a
   checkpoint that does not exist" is the confidently-wrong answer this product
   exists to avoid.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from constat.errors import InvalidInput, NotRegistered
from constat.models import Anchor, RuleProposal
from constat.operations import open_run
from constat.store import (
    Catalogue,
    Checkpoints,
    Registry,
    Review,
    RuleProposals,
    TicketStore,
    Workspace,
)
from constat.store.schema import SCHEMA_VERSION

from helpers import rewind_workspace
from test_runs import distinct_subject


REFERENCE = "615"


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
        )
        TicketStore(ws).add(REFERENCE)
        yield ws


def _accept(workspace, name: str, revises: int | None = None, statement: str | None = None) -> int:
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    proposal_id = RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name=name,
            statement=statement or "A transfer above the daily limit is refused.",
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            area="payments",
            relation="revises" if revises else "establishes",
            revises_rule_id=revises,
        ),
        provider="mcp",
        revises_rule_id=revises,
    )
    return Review(workspace).accept(proposal_id, decided_by="a person").rule_id


def _statuses(changes) -> dict[str, str]:
    return {c.ref: c.status for c in changes}


# -- taking one ---------------------------------------------------------------


class TestTakingACheckpoint:
    def test_it_freezes_the_rules_that_stand(self, workspace) -> None:
        _accept(workspace, "daily-limit")
        _accept(workspace, "payout-threshold")

        taken = Checkpoints(workspace).take("before the November release", "a person")

        assert taken.ref == "C-1"
        assert taken.rule_count == 2

    def test_a_label_is_required(self, workspace) -> None:
        """A checkpoint nobody can name is one nobody will compare against."""
        with pytest.raises(InvalidInput, match="needs a label"):
            Checkpoints(workspace).take("   ", "a person")

    def test_checkpoints_are_cited_in_order(self, workspace) -> None:
        _accept(workspace, "daily-limit")
        checkpoints = Checkpoints(workspace)
        checkpoints.take("first", "a person")
        checkpoints.take("second", "a person")

        assert [c.ref for c in checkpoints.list()] == ["C-1", "C-2"]

    def test_a_retired_rule_is_not_in_it(self, workspace) -> None:
        """A checkpoint records the product as it stood, and a rule a person
        had taken out of the picture was not part of it (CON-83)."""
        rule_id = _accept(workspace, "daily-limit")
        _accept(workspace, "payout-threshold")
        Review(workspace).retire(rule_id, reason="no longer applies", decided_by="a person")

        taken = Checkpoints(workspace).take("after the retirement", "a person")

        assert taken.rule_count == 1

    def test_an_empty_catalogue_can_be_checkpointed(self, workspace) -> None:
        """A legitimate state: "we agreed the catalogue was empty" is a real
        starting point, and refusing it would make the first comparison
        impossible."""
        taken = Checkpoints(workspace).take("before we started", "a person")

        assert taken.rule_count == 0

    def test_the_decider_and_attribution_are_recorded(self, workspace) -> None:
        taken = Checkpoints(workspace).take(
            "a label", "e@example.invalid", attribution="inferred"
        )

        assert taken.taken_by == "e@example.invalid"
        assert taken.attribution == "inferred"


class TestACheckpointIsFrozen:
    def test_it_cannot_be_edited(self, workspace) -> None:
        """A checkpoint that could be edited would make "what changed since"
        unanswerable, which is the whole reason to have one."""
        Checkpoints(workspace).take("a label", "a person")

        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            workspace.execute("UPDATE checkpoint SET label = 'other'")

    def test_it_cannot_be_deleted(self, workspace) -> None:
        Checkpoints(workspace).take("a label", "a person")

        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            workspace.execute("DELETE FROM checkpoint")

    def test_a_later_acceptance_does_not_change_it(self, workspace) -> None:
        """The property that makes it a reference point at all."""
        _accept(workspace, "daily-limit")
        checkpoints = Checkpoints(workspace)
        taken = checkpoints.take("before", "a person")

        _accept(workspace, "payout-threshold")

        assert checkpoints.find("C-1").rule_count == taken.rule_count == 1


# -- the comparison -----------------------------------------------------------


class TestChangesSince:
    def test_a_new_rule_reads_as_added(self, workspace) -> None:
        _accept(workspace, "daily-limit")
        checkpoints = Checkpoints(workspace)
        taken = checkpoints.take("before", "a person")

        _accept(workspace, "payout-threshold")

        assert _statuses(checkpoints.changes_since(taken)) == {
            "R-1": "unchanged",
            "R-2": "added",
        }

    def test_a_revision_reads_as_revised(self, workspace) -> None:
        """Compared by version, not by text: only the stored version numbers
        can tell a rephrased rule from an untouched one."""
        rule_id = _accept(workspace, "daily-limit")
        checkpoints = Checkpoints(workspace)
        taken = checkpoints.take("before", "a person")

        _accept(
            workspace,
            "daily-limit",
            revises=rule_id,
            statement="A transfer above the daily limit is refused and explained.",
        )

        change = checkpoints.changes_since(taken)[0]
        assert change.status == "revised"
        assert (change.from_version, change.to_version) == (1, 2)

    def test_a_retirement_reads_as_retired_with_its_reason(self, workspace) -> None:
        rule_id = _accept(workspace, "daily-limit")
        checkpoints = Checkpoints(workspace)
        taken = checkpoints.take("before", "a person")

        Review(workspace).retire(
            rule_id, reason="the limit was removed entirely", decided_by="a person"
        )

        change = checkpoints.changes_since(taken)[0]
        assert change.status == "retired"
        assert change.detail == "the limit was removed entirely"

    def test_an_untouched_rule_reads_as_unchanged(self, workspace) -> None:
        _accept(workspace, "daily-limit")
        checkpoints = Checkpoints(workspace)
        taken = checkpoints.take("before", "a person")

        assert _statuses(checkpoints.changes_since(taken)) == {"R-1": "unchanged"}

    def test_a_rule_added_and_retired_since_is_not_reported_as_lost(
        self, workspace
    ) -> None:
        """It was never in the state being compared against, so calling it
        retired would describe the product losing something it never had in
        that state."""
        checkpoints = Checkpoints(workspace)
        taken = checkpoints.take("before anything", "a person")

        rule_id = _accept(workspace, "short-lived")
        Review(workspace).retire(rule_id, reason="a mistake", decided_by="a person")

        assert checkpoints.changes_since(taken) == ()

    def test_nothing_changed_is_an_answer(self, workspace) -> None:
        _accept(workspace, "daily-limit")
        checkpoints = Checkpoints(workspace)
        taken = checkpoints.take("before", "a person")

        changes = checkpoints.changes_since(taken)

        assert all(c.status == "unchanged" for c in changes)


class TestNoCheckpointIsRefused:
    def test_comparing_with_none_taken_is_refused(self, workspace) -> None:
        """"Nothing has changed since a checkpoint that does not exist" is the
        confidently-wrong answer this product exists to avoid."""
        with pytest.raises(NotRegistered, match="no checkpoint has been taken"):
            Checkpoints(workspace).require(None)

    def test_an_unknown_reference_is_refused(self, workspace) -> None:
        Checkpoints(workspace).take("a label", "a person")

        with pytest.raises(NotRegistered, match="no checkpoint 'C-9'"):
            Checkpoints(workspace).require("C-9")

    def test_the_most_recent_is_the_default(self, workspace) -> None:
        checkpoints = Checkpoints(workspace)
        checkpoints.take("first", "a person")
        checkpoints.take("second", "a person")

        assert checkpoints.require(None).label == "second"

    def test_an_earlier_one_can_be_named(self, workspace) -> None:
        checkpoints = Checkpoints(workspace)
        checkpoints.take("first", "a person")
        checkpoints.take("second", "a person")

        assert checkpoints.require("C-1").label == "first"


class TestTheCommandLine:
    def _home(self, workspace) -> str:
        return str(Path(workspace.path).parent)

    def test_take_then_changes(self, workspace, capsys) -> None:
        from constat.cli import main

        _accept(workspace, "daily-limit")
        capsys.readouterr()

        assert (
            main(["--workspace", self._home(workspace), "checkpoint", "take",
                  "--label", "the November state", "--by", "a person"]) == 0
        )
        assert "took C-1" in capsys.readouterr().out

        _accept(workspace, "payout-threshold")
        assert main(["--workspace", self._home(workspace), "checkpoint", "changes"]) == 0

        out = capsys.readouterr().out
        assert "Since C-1 (the November state)" in out
        assert "R-2  added" in out

    def test_changes_with_no_checkpoint_exits_nonzero(self, workspace, capsys) -> None:
        from constat.cli import main

        code = main(["--workspace", self._home(workspace), "checkpoint", "changes"])

        assert code != 0
        assert "no checkpoint has been taken" in capsys.readouterr().err

    def test_list_with_none_taken_says_so(self, workspace, capsys) -> None:
        from constat.cli import main

        main(["--workspace", self._home(workspace), "checkpoint", "list"])

        assert "No checkpoints taken" in capsys.readouterr().out


class TestMigrationFromSchema19:
    def _at_schema_19(self, home: Path, tmp_path: Path) -> None:
        with Workspace.create(home) as ws:
            Registry(ws).add(
                str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")),
                alias="billing",
            )
            TicketStore(ws).add(REFERENCE)
            _accept(ws, "daily-limit")

        rewind_workspace(home / "workspace.db", 19)

    def test_it_migrates_on_open(self, tmp_path: Path) -> None:
        self._at_schema_19(tmp_path / "ws", tmp_path)

        with Workspace.open(tmp_path / "ws") as ws:
            assert ws.schema_version == SCHEMA_VERSION
            assert Checkpoints(ws).list() == ()

    def test_nothing_is_checkpointed_by_the_migration(self, tmp_path: Path) -> None:
        """A checkpoint records that a person looked at the product and agreed
        it was this. Inventing one would put a human decision in the record
        that nobody made."""
        self._at_schema_19(tmp_path / "ws", tmp_path)

        with Workspace.open(tmp_path / "ws") as ws:
            assert Checkpoints(ws).latest() is None

    def test_a_checkpoint_taken_after_migrating_works(self, tmp_path: Path) -> None:
        self._at_schema_19(tmp_path / "ws", tmp_path)

        with Workspace.open(tmp_path / "ws") as ws:
            taken = Checkpoints(ws).take("after migrating", "a person")

            assert taken.ref == "C-1"
            assert taken.rule_count == 1
            assert len(Catalogue(ws).list()) == 1
