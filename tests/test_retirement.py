"""A rule can be retired, and nothing is deleted (CON-83, D-084).

D-070 said a rule whose anchors have vanished is a *retirement candidate, never
a retirement*. This is the other half of that sentence: the decision a person
makes, recorded like acceptance.

Four properties carry these tests:

1. **A human decision.** Nothing retires a rule automatically — not vanished
   anchors, not an unreadable repository, not a migration.
2. **A decision, not a deletion.** The rule, its versions, its citation and its
   evidence stay readable. `rule` cannot be deleted at all, which product rule
   5 requires: a catalogue that forgets what it used to claim cannot be
   audited.
3. **Final.** Append-only with no reinstatement row. Behaviour coming back
   means a new rule with its own citation — a decision somebody makes rather
   than a flag somebody clears.
4. **A reason is required**, because the interesting retirements are the ones
   nothing else can express — above all a lapsed condition (D-071).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from constat.errors import InvalidInput, NotRegistered
from constat.models import Anchor, RuleProposal
from constat.operations import open_run, product_state, render_state
from constat.store import (
    Catalogue,
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
LAPSED = "the site was approved by the ad network on 2026-11-18, so the condition no longer holds"


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
        )
        TicketStore(ws).add(REFERENCE)
        yield ws


def _accept(workspace, name: str = "no-ads-while-unapproved") -> int:
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    proposal_id = RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name=name,
            statement="The news pages carry no advertising while the site is not approved.",
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            area="advertising",
        ),
        provider="mcp",
    )
    return Review(workspace).accept(proposal_id, decided_by="a person").rule_id


def _revision_of(workspace, rule_id: int) -> int:
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    return RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name="no-ads-while-unapproved",
            statement="The news pages carry no advertising at all.",
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            area="advertising",
            relation="revises",
            revises_rule_id=rule_id,
        ),
        provider="mcp",
        revises_rule_id=rule_id,
    )


# -- the decision -------------------------------------------------------------


class TestRetiringIsADecision:
    def test_a_rule_can_be_retired_with_a_reason(self, workspace) -> None:
        rule_id = _accept(workspace)

        retired = Review(workspace).retire(
            rule_id, reason=LAPSED, decided_by="a person"
        )

        assert retired.rule_id == rule_id
        assert retired.reason == LAPSED
        assert retired.decided_by == "a person"

    def test_a_reason_is_required(self, workspace) -> None:
        """It is the only record of why the product stopped behaving this way,
        and the rule itself cannot say so."""
        rule_id = _accept(workspace)

        with pytest.raises(InvalidInput, match="needs a reason"):
            Review(workspace).retire(rule_id, reason="   ", decided_by="a person")

    def test_an_unknown_rule_is_refused(self, workspace) -> None:
        with pytest.raises(NotRegistered, match="no rule with id 99"):
            Review(workspace).retire(99, reason=LAPSED, decided_by="a person")

    def test_the_decider_and_attribution_are_recorded(self, workspace) -> None:
        """Same posture as acceptance (D-061): neither `stated` nor `inferred`
        is verified, and a reviewer is entitled to know which it was."""
        rule_id = _accept(workspace)

        Review(workspace).retire(
            rule_id, reason=LAPSED, decided_by="e@example.invalid", attribution="inferred"
        )

        retired = Review(workspace).retirement_of(rule_id)
        assert retired.decided_by == "e@example.invalid"
        assert retired.attribution == "inferred"

    def test_nothing_retires_a_rule_automatically(self, workspace, tmp_path) -> None:
        """The property D-070 set and this must not quietly undo: a rule whose
        anchors have vanished is a *candidate*, and a person decides."""
        import shutil

        rule_id = _accept(workspace)
        entry = Registry(workspace).list()[0]
        shutil.rmtree(entry.source)

        state = product_state(workspace)

        assert Review(workspace).retirement_of(rule_id) is None
        assert state.retired == ()


class TestNothingIsDeleted:
    def test_the_rule_is_still_in_the_catalogue(self, workspace) -> None:
        rule_id = _accept(workspace)
        Review(workspace).retire(rule_id, reason=LAPSED, decided_by="a person")

        rule = Catalogue(workspace).by_id(rule_id)

        assert rule is not None
        assert rule.ref == "R-1"

    def test_its_versions_stay_readable(self, workspace) -> None:
        """Product rule 5. A catalogue that forgets what it used to claim
        cannot be audited."""
        rule_id = _accept(workspace)
        Review(workspace).retire(rule_id, reason=LAPSED, decided_by="a person")

        versions = Review(workspace).versions(rule_id)

        assert len(versions) == 1
        assert versions[0]["statement"].startswith("The news pages carry no advertising")

    def test_it_is_findable_by_its_citation(self, workspace) -> None:
        rule_id = _accept(workspace)
        Review(workspace).retire(rule_id, reason=LAPSED, decided_by="a person")

        assert Catalogue(workspace).find("R-1") is not None

    def test_the_rule_row_still_cannot_be_deleted(self, workspace) -> None:
        """Retirement does not open a door the trigger closed (D-048)."""
        rule_id = _accept(workspace)
        Review(workspace).retire(rule_id, reason=LAPSED, decided_by="a person")

        with pytest.raises(sqlite3.DatabaseError, match="cannot be removed"):
            workspace.execute("DELETE FROM rule WHERE id = ?", (rule_id,))


class TestRetirementIsFinal:
    def test_retiring_twice_is_refused(self, workspace) -> None:
        rule_id = _accept(workspace)
        review = Review(workspace)
        review.retire(rule_id, reason=LAPSED, decided_by="a person")

        with pytest.raises(InvalidInput, match="already retired"):
            review.retire(rule_id, reason="again", decided_by="a person")

    def test_a_retirement_cannot_be_modified(self, workspace) -> None:
        rule_id = _accept(workspace)
        Review(workspace).retire(rule_id, reason=LAPSED, decided_by="a person")

        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            workspace.execute("UPDATE rule_retirement SET reason = 'other'")

    def test_a_retirement_cannot_be_undone(self, workspace) -> None:
        """No reinstatement row by design: behaviour coming back is a new rule,
        which is a decision somebody makes rather than a flag they clear."""
        rule_id = _accept(workspace)
        Review(workspace).retire(rule_id, reason=LAPSED, decided_by="a person")

        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            workspace.execute("DELETE FROM rule_retirement")

    def test_a_retired_rule_cannot_be_revised(self, workspace) -> None:
        """A new version would be the current state of something a person has
        said is no longer the product's behaviour. Refused with the route back
        named, rather than resurrected silently."""
        rule_id = _accept(workspace)
        review = Review(workspace)
        review.retire(rule_id, reason=LAPSED, decided_by="a person")
        proposal_id = _revision_of(workspace, rule_id)

        with pytest.raises(InvalidInput, match="was retired"):
            review.accept(proposal_id, decided_by="a person")

    def test_the_refusal_names_the_way_back(self, workspace) -> None:
        rule_id = _accept(workspace)
        review = Review(workspace)
        review.retire(rule_id, reason=LAPSED, decided_by="a person")
        proposal_id = _revision_of(workspace, rule_id)

        with pytest.raises(InvalidInput, match="as a new rule"):
            review.accept(proposal_id, decided_by="a person")

    def test_a_new_rule_takes_a_fresh_citation(self, workspace) -> None:
        """The citation of a retired rule is never reused, which is automatic:
        a rule can never be deleted, so `rule` is the whole history."""
        rule_id = _accept(workspace)
        Review(workspace).retire(rule_id, reason=LAPSED, decided_by="a person")

        new_rule_id = _accept(workspace, name="no-ads-at-all")

        assert Catalogue(workspace).by_id(new_rule_id).ref == "R-2"


# -- the current picture ------------------------------------------------------


class TestTheCurrentPicture:
    def test_a_retired_rule_leaves_the_rules_section(self, workspace) -> None:
        rule_id = _accept(workspace)
        Review(workspace).retire(rule_id, reason=LAPSED, decided_by="a person")

        state = product_state(workspace)

        assert [r.rule.ref for r in state.rules] == []
        assert [rule.ref for rule, _ in state.retired] == ["R-1"]

    def test_the_picture_says_what_was_retired_and_why(self, workspace) -> None:
        """Silence would read as the rule never having existed. "The product
        used to do this and deliberately stopped" is a fact a reader of
        business documentation needs."""
        rule_id = _accept(workspace)
        Review(workspace).retire(rule_id, reason=LAPSED, decided_by="a person")

        rendered = render_state(product_state(workspace))

        assert "## Retired" in rendered
        assert "`R-1`" in rendered
        assert LAPSED in rendered

    def test_an_all_retired_catalogue_is_not_an_empty_one(self, workspace) -> None:
        """Two different claims about the product, and only one of them says
        the behaviour was deliberately stopped. The first version of this
        printed "the catalogue holds no rules" after everything was retired."""
        rule_id = _accept(workspace)
        Review(workspace).retire(rule_id, reason=LAPSED, decided_by="a person")

        rendered = render_state(product_state(workspace))

        assert "this is not an empty catalogue" in rendered
        assert "holds no rules, so there is nothing to describe" not in rendered

    def test_a_standing_rule_is_unaffected(self, workspace) -> None:
        retired_id = _accept(workspace)
        _accept(workspace, name="still-standing")
        Review(workspace).retire(retired_id, reason=LAPSED, decided_by="a person")

        state = product_state(workspace)

        assert [r.rule.name for r in state.rules] == ["still-standing"]

    def test_nothing_is_retired_by_default(self, workspace) -> None:
        _accept(workspace)

        assert product_state(workspace).retired == ()


class TestTheLapsedCondition:
    def test_a_lapsed_condition_is_expressed_as_a_retirement(
        self, workspace
    ) -> None:
        """The question D-071 left open.

        A rule may be conditional on a business state — "while the site is not
        approved by the ad network" — and becomes false when that state
        changes. Nothing in the statement can say so, and editing it would
        rewrite what a person accepted. Retiring it with that reason is the
        answer, which is why a reason is required rather than optional.
        """
        rule_id = _accept(workspace)
        assert "while the site is not approved" in Catalogue(workspace).by_id(
            rule_id
        ).statement

        Review(workspace).retire(rule_id, reason=LAPSED, decided_by="a person")

        retired = Review(workspace).retirement_of(rule_id)
        assert "no longer holds" in retired.reason
        # And the statement a person accepted is untouched.
        assert "while the site is not approved" in Catalogue(workspace).by_id(
            rule_id
        ).statement


class TestTheCommandLine:
    def test_retire_records_the_decision(self, workspace, capsys) -> None:
        from constat.cli import main

        rule_id = _accept(workspace)
        capsys.readouterr()

        code = main(
            [
                "--workspace",
                str(Path(workspace.path).parent),
                "rule",
                "retire",
                str(rule_id),
                "--reason",
                LAPSED,
                "--by",
                "a person",
            ]
        )

        out = capsys.readouterr().out
        assert code == 0
        assert "retired: R-1" in out
        assert "nothing is deleted" in out

    def test_a_reason_is_required_by_the_parser(self, workspace, capsys) -> None:
        from constat.cli import main

        rule_id = _accept(workspace)

        with pytest.raises(SystemExit):
            main(
                [
                    "--workspace",
                    str(Path(workspace.path).parent),
                    "rule",
                    "retire",
                    str(rule_id),
                ]
            )


class TestMigrationFromSchema18:
    def _at_schema_18(self, home: Path, tmp_path: Path) -> int:
        with Workspace.create(home) as ws:
            Registry(ws).add(
                str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")),
                alias="billing",
            )
            TicketStore(ws).add(REFERENCE)
            rule_id = _accept(ws)

        rewind_workspace(home / "workspace.db", 18)
        return rule_id

    def test_it_migrates_on_open(self, tmp_path: Path) -> None:
        self._at_schema_18(tmp_path / "ws", tmp_path)

        with Workspace.open(tmp_path / "ws") as ws:
            assert ws.schema_version == SCHEMA_VERSION
            assert ws.execute(
                "SELECT COUNT(*) AS n FROM rule_retirement"
            ).fetchone()["n"] == 0

    def test_no_rule_is_retired_by_the_migration(self, tmp_path: Path) -> None:
        """Retirement is a human decision, and inventing one would be the thing
        D-048 exists to prevent, performed by a migration."""
        rule_id = self._at_schema_18(tmp_path / "ws", tmp_path)

        with Workspace.open(tmp_path / "ws") as ws:
            assert Review(ws).retirement_of(rule_id) is None
            assert Catalogue(ws).retirements() == {}

    def test_the_triggers_arrive_with_the_table(self, tmp_path: Path) -> None:
        rule_id = self._at_schema_18(tmp_path / "ws", tmp_path)

        with Workspace.open(tmp_path / "ws") as ws:
            Review(ws).retire(rule_id, reason=LAPSED, decided_by="a person")

            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                ws.execute("DELETE FROM rule_retirement")
