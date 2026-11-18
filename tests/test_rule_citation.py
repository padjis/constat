"""A rule has a citable identifier (CON-81, D-081).

Before this, a rule could be identified two ways and neither was citable: the
row id is an implementation detail that means nothing to a business reader, and
`name` is a label that may change between versions (D-050). There was nothing
to write in a comment, an email or a pull request.

Four properties carry these tests:

1. **Flat, not area-prefixed.** An area is mutable by design (D-079 left it
   free text), and an identifier encoding a mutable fact becomes a false claim
   the moment that fact changes — what CON-67 established about positions,
   applied to areas.
2. **Stored, not derived from the row id.** `R-{id}` would be free and is a
   trap: a public citation would depend on rowids surviving every future table
   rebuild, and `rule` has already been rebuilt once (migration 4 → 5).
3. **Never reused**, and here that holds without qualification: a rule can
   never be deleted (the trigger aborts it), so `rule` is the whole history.
4. **It resolves.** A citation nobody can look up is decoration.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

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


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
        )
        TicketStore(ws).add(REFERENCE)
        yield ws


def _accept(workspace, name: str, area: str | None = "payments") -> int:
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    proposal_id = RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name=name,
            statement="A transfer above the daily limit is refused.",
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            area=area,
        ),
        provider="mcp",
    )
    return Review(workspace).accept(proposal_id, decided_by="a person").rule_id


# -- the citation -------------------------------------------------------------


class TestEveryRuleIsCitable:
    def test_a_new_rule_gets_a_citation(self, workspace) -> None:
        _accept(workspace, "daily-limit")

        assert Catalogue(workspace).find("daily-limit").ref == "R-1"

    def test_citations_count_up(self, workspace) -> None:
        _accept(workspace, "daily-limit")
        _accept(workspace, "payout-threshold")

        refs = [rule.ref for rule in Catalogue(workspace).list()]
        assert sorted(refs) == ["R-1", "R-2"]

    def test_it_is_flat_rather_than_area_prefixed(self, workspace) -> None:
        """The decision, asserted so it cannot drift back.

        `BR-PAY-001` reads better and encodes the area — which is mutable by
        design (D-079), so the identifier would become a lie the first time a
        rule was re-grouped. A flat citation cannot go wrong, and the area is
        one field away in every rendering.
        """
        _accept(workspace, "daily-limit", area="payments")

        ref = Catalogue(workspace).find("daily-limit").ref
        assert ref == "R-1"
        assert "PAY" not in ref


class TestACitationIsStable:
    def test_a_revision_does_not_change_it(self, workspace) -> None:
        """A citation survives everything about a rule changing, which is the
        point: a person who wrote it down keeps a working reference."""
        rule_id = _accept(workspace, "daily-limit")
        before = Catalogue(workspace).by_id(rule_id).ref

        run_id = open_run(workspace, REFERENCE, "submit_reply")
        proposal_id = RuleProposals(workspace).record(
            run_id,
            RuleProposal(
                name="a-completely-different-name",
                statement="A different statement entirely.",
                anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
                area="payouts",
                relation="revises",
                revises_rule_id=rule_id,
            ),
            provider="mcp",
            revises_rule_id=rule_id,
        )
        Review(workspace).accept(proposal_id, decided_by="a person")

        after = Catalogue(workspace).by_id(rule_id)
        assert after.ref == before
        assert after.name == "a-completely-different-name"
        assert after.area == "payouts"

    def test_it_is_a_stored_column_rather_than_a_computed_string(
        self, workspace
    ) -> None:
        """`R-{id}` would be free, and is a trap: a public citation would then
        depend on rowids surviving every future table rebuild, and `rule` has
        already been rebuilt once (migration 4 → 5). Asserted against the
        schema, because that is where the property lives."""
        _accept(workspace, "daily-limit")

        columns = {
            row["name"]
            for row in workspace.execute("PRAGMA table_info(rule)").fetchall()
        }
        assert "ref" in columns

        stored = workspace.execute("SELECT ref FROM rule").fetchone()["ref"]
        assert stored == "R-1"

    def test_a_gap_in_the_citations_does_not_cause_a_collision(
        self, workspace
    ) -> None:
        """The high-water mark has to be the greatest citation, not a count of
        rules.

        **Citations can have gaps**, because the schema-17 migration back-fills
        them from row ids and row ids can have gaps — a rolled-back insert
        consumes one, and `rule` has been rebuilt once already (migration
        4 → 5). With a gap, counting rules returns a number already in use, the
        unique index refuses the insert, and an acceptance is lost to a
        numbering bug.

        **Added after two mutations survived.** Replacing MAX with COUNT passed
        every other test here, including a first attempt at this one that
        inserted an *uncited* rule — which does not distinguish the two, since
        a NULL ref is counted by neither.
        """
        _accept(workspace, "daily-limit")
        workspace.execute(
            "INSERT INTO rule (ref, name, statement, created_at) "
            "VALUES ('R-9', 'imported', 'A rule with a high citation.', "
            "'2026-01-01T00:00:00Z')"
        )

        rule_id = _accept(workspace, "payout-threshold")

        assert Catalogue(workspace).by_id(rule_id).ref == "R-10"

    def test_a_citation_is_unique(self, workspace) -> None:
        _accept(workspace, "daily-limit")

        with pytest.raises(sqlite3.DatabaseError):
            workspace.execute(
                "INSERT INTO rule (ref, name, statement, created_at) "
                "VALUES ('R-1', 'other', 'x', '2026-11-18T00:00:00Z')"
            )


class TestItResolves:
    def test_a_rule_is_found_by_its_citation(self, workspace) -> None:
        """A citation nobody can look up is decoration."""
        _accept(workspace, "daily-limit")

        found = Catalogue(workspace).find("R-1")

        assert found is not None
        assert found.name == "daily-limit"

    def test_a_rule_is_still_found_by_name(self, workspace) -> None:
        _accept(workspace, "daily-limit")

        assert Catalogue(workspace).find("daily-limit") is not None

    def test_an_unknown_citation_is_not_found(self, workspace) -> None:
        _accept(workspace, "daily-limit")

        assert Catalogue(workspace).find("R-99") is None


class TestItIsShownWhereItMatters:
    def test_the_product_state_carries_it(self, workspace) -> None:
        _accept(workspace, "daily-limit")

        rendered = render_state(product_state(workspace))

        assert "`R-1`" in rendered

    def test_rule_show_leads_with_it(self, workspace, capsys) -> None:
        from constat.cli import main

        _accept(workspace, "daily-limit")
        capsys.readouterr()

        main(
            [
                "--workspace",
                str(Path(workspace.path).parent),
                "rule",
                "show",
                "daily-limit",
            ]
        )

        assert capsys.readouterr().out.startswith("R-1")

    def test_rule_show_accepts_the_citation_as_its_argument(
        self, workspace, capsys
    ) -> None:
        from constat.cli import main

        _accept(workspace, "daily-limit")
        capsys.readouterr()

        code = main(
            ["--workspace", str(Path(workspace.path).parent), "rule", "show", "R-1"]
        )

        assert code == 0
        assert "daily-limit" in capsys.readouterr().out


# -- the migration ------------------------------------------------------------


class TestMigrationFromSchema16:
    def _at_schema_16(self, home: Path, tmp_path: Path) -> None:
        with Workspace.create(home) as ws:
            Registry(ws).add(
                str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")),
                alias="billing",
            )
            TicketStore(ws).add(REFERENCE)
            _accept(ws, "daily-limit")
            _accept(ws, "payout-threshold")

        rewind_workspace(home / "workspace.db", 16)

    def test_existing_rules_are_back_filled(self, tmp_path: Path) -> None:
        """**Back-filled, unlike every migration before it, and the difference
        is the point.** The others refused because they would have invented a
        claim nobody made — an area, a number, an example. A citation invents
        nothing: the rules exist, and naming them asserts nothing about them.
        Refusing here would leave a catalogue whose rules nobody can cite,
        which is the defect this closes.
        """
        self._at_schema_16(tmp_path / "ws", tmp_path)

        with Workspace.open(tmp_path / "ws") as ws:
            assert ws.schema_version == SCHEMA_VERSION
            refs = sorted(rule.ref for rule in Catalogue(ws).list())
            assert refs == ["R-1", "R-2"]

    def test_the_back_fill_is_stable_in_id_order(self, tmp_path: Path) -> None:
        self._at_schema_16(tmp_path / "ws", tmp_path)

        with Workspace.open(tmp_path / "ws") as ws:
            rows = ws.execute("SELECT id, ref FROM rule ORDER BY id").fetchall()
            assert [row["ref"] for row in rows] == ["R-1", "R-2"]

    def test_a_rule_accepted_after_the_migration_does_not_collide(
        self, tmp_path: Path
    ) -> None:
        """The high-water mark has to see the back-filled citations, or the
        next rule takes `R-1` again and the unique index refuses the
        acceptance."""
        self._at_schema_16(tmp_path / "ws", tmp_path)

        with Workspace.open(tmp_path / "ws") as ws:
            rule_id = _accept(ws, "a-third-rule")

            assert Catalogue(ws).by_id(rule_id).ref == "R-3"
