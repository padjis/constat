"""A release is declared, and a rule version is agreed for one (CON-85, D-102).

The four parts decided on 2026-11-18 are what these tests pin:

1. **Declared, never derived.** No tag is read, and a release nobody declared
   cannot come into being by being used.
2. **Optional and nullable.** A workspace that declares no release behaves
   exactly as it did before — which is most of the suite, and why the join
   that reads a release back has to be a LEFT JOIN.
3. **The name is stored verbatim and never parsed.** No semver, no ordering, no
   case-folding, no "latest".
4. **Several open at once**, so there is nothing to order and no close.

And one property that is not about releases at all: a workspace migrated to 21
must be structurally identical to one created at 21. The schema comments have
claimed that since CON-81 and nothing checked it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from constat.errors import InvalidInput, NotRegistered
from constat.models import Anchor, RuleProposal
from constat.operations import open_run
from constat.store import (
    Registry,
    Releases,
    Review,
    RuleProposals,
    TicketStore,
    Workspace,
)
from constat.store.schema import SCHEMA_VERSION

from helpers import rewind_workspace
from test_runs import distinct_subject


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")),
            alias="billing",
        )
        TicketStore(ws).add("402")
        yield ws


def _proposal(workspace, name: str = "daily-limit") -> int:
    run_id = open_run(workspace, "402", "submit_reply")
    return RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name=name,
            statement="A transfer above the daily limit is refused.",
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            area="payments",
        ),
        provider="mcp",
    )


# -- declaring ----------------------------------------------------------------


class TestDeclaring:
    def test_a_release_is_declared_with_a_decider(self, workspace):
        declared = Releases(workspace).declare("2026.11", "A Reviewer")

        assert declared.name == "2026.11"
        assert declared.declared_by == "A Reviewer"

    def test_the_name_is_stored_exactly_as_given(self, workspace):
        """Verbatim is the decision. `v4.2-HOTFIX` is what somebody calls their
        release, and normalising it would be Constat deciding how they version
        their product."""
        declared = Releases(workspace).declare("v4.2-HOTFIX (eu)", "A Reviewer")

        assert Releases(workspace).find("v4.2-HOTFIX (eu)") == declared

    def test_surrounding_whitespace_is_stripped(self, workspace):
        declared = Releases(workspace).declare("  2026.11  ", "A Reviewer")

        assert declared.name == "2026.11"

    def test_an_empty_name_is_refused(self, workspace):
        with pytest.raises(InvalidInput, match="needs a name"):
            Releases(workspace).declare("   ", "A Reviewer")

    def test_a_statement_pasted_into_the_field_is_refused(self, workspace):
        with pytest.raises(InvalidInput, match="is a label"):
            Releases(workspace).declare("x" * 200, "A Reviewer")

    def test_declaring_the_same_name_twice_is_refused(self, workspace):
        """Refused rather than returning the existing row: somebody declaring a
        release that exists has a different picture of the workspace than the
        workspace does."""
        releases = Releases(workspace)
        releases.declare("2026.11", "A Reviewer")

        with pytest.raises(InvalidInput, match="already declared"):
            releases.declare("2026.11", "Another Reviewer")

    def test_names_differing_only_in_case_are_two_releases(self, workspace):
        """The cost of verbatim, accepted deliberately. Case-folding `V4.2`
        onto `v4.2` would be a guess about somebody else's convention — the
        kind D-020 refuses for an ambiguous revision."""
        releases = Releases(workspace)
        releases.declare("v4.2", "A Reviewer")
        releases.declare("V4.2", "A Reviewer")

        assert [r.name for r in releases.list()] == ["v4.2", "V4.2"]

    def test_several_may_be_open_at_once(self, workspace):
        """There is no close, so "open" is every release there is (CON-86)."""
        releases = Releases(workspace)
        for name in ("2026.11", "2026.12", "hotfix-3"):
            releases.declare(name, "A Reviewer")

        assert len(releases.list()) == 3

    def test_they_are_listed_in_declaration_order_not_by_name(self, workspace):
        """Sorting names would mean interpreting them — is `v10` before `v9`?
        Declaration order is a fact about what happened."""
        releases = Releases(workspace)
        for name in ("v9", "v10", "v2"):
            releases.declare(name, "A Reviewer")

        assert [r.name for r in releases.list()] == ["v9", "v10", "v2"]

    def test_a_release_cannot_be_edited(self, workspace):
        """Append-only, like every other recorded decision. A release whose
        name could change after versions were agreed for it would make those
        agreements say something nobody decided."""
        Releases(workspace).declare("2026.11", "A Reviewer")

        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            workspace.execute("UPDATE release SET name = 'other'")

    def test_a_release_cannot_be_deleted(self, workspace):
        Releases(workspace).declare("2026.11", "A Reviewer")

        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            workspace.execute("DELETE FROM release")


class TestResolving:
    def test_an_undeclared_name_refuses_and_names_what_exists(self, workspace):
        """The usual cause is a typo, so the refusal lists the real ones."""
        Releases(workspace).declare("2026.11", "A Reviewer")

        with pytest.raises(NotRegistered, match="'2026.11'"):
            Releases(workspace).require("2026.12")

    def test_the_refusal_says_where_a_release_comes_from(self, workspace):
        with pytest.raises(NotRegistered, match="release declare"):
            Releases(workspace).require("2026.11")

    def test_find_returns_nothing_rather_than_refusing(self, workspace):
        assert Releases(workspace).find("2026.11") is None

    def test_resolving_is_case_sensitive(self, workspace):
        """`declare` compares exactly, so `find` has to as well — otherwise
        two releases can exist that only one of them can be reached by, and a
        version would be agreed for whichever the collation happened to pick."""
        Releases(workspace).declare("v4.2", "A Reviewer")

        assert Releases(workspace).find("V4.2") is None
        with pytest.raises(NotRegistered):
            Releases(workspace).require("V4.2")


# -- agreeing a version for one -----------------------------------------------


class TestAcceptance:
    def test_a_version_records_the_release_it_was_agreed_for(self, workspace):
        Releases(workspace).declare("2026.11", "A Reviewer")
        proposal_id = _proposal(workspace)

        result = Review(workspace).accept(
            proposal_id, decided_by="A Reviewer", release="2026.11"
        )

        assert result.release == "2026.11"
        stored = workspace.execute(
            "SELECT release_id FROM rule_version WHERE id = ?",
            (result.rule_version_id,),
        ).fetchone()
        assert stored["release_id"] is not None

    def test_accepting_without_a_release_is_the_ordinary_case(self, workspace):
        """Nullable is the design: a workspace declaring no release behaves
        exactly as it did before this landed."""
        proposal_id = _proposal(workspace)

        result = Review(workspace).accept(proposal_id, decided_by="A Reviewer")

        assert result.release is None
        stored = workspace.execute(
            "SELECT release_id FROM rule_version WHERE id = ?",
            (result.rule_version_id,),
        ).fetchone()
        assert stored["release_id"] is None

    def test_an_undeclared_release_refuses_the_acceptance(self, workspace):
        """A release is never coined by using it. Creating one as a side effect
        of accepting a rule is exactly what "declared, never derived" rules
        out."""
        proposal_id = _proposal(workspace)

        with pytest.raises(NotRegistered, match="never created by being used"):
            Review(workspace).accept(
                proposal_id, decided_by="A Reviewer", release="2026.11"
            )

    def test_a_refused_release_leaves_the_proposal_undecided(self, workspace):
        """Resolved before anything is written, so a typo does not half-accept
        a reading. The proposal has to remain acceptable afterwards."""
        proposal_id = _proposal(workspace)

        with pytest.raises(NotRegistered):
            Review(workspace).accept(
                proposal_id, decided_by="A Reviewer", release="typo"
            )

        assert RuleProposals(workspace).find(proposal_id).decision is None
        # And nothing entered the catalogue. Resolving the release *after*
        # `_target_rule` would leave a rule behind with no accepted version —
        # a rule that entered without a decision, which is the thing D-048
        # exists to prevent. A mutation found this: the proposal's state alone
        # does not notice it.
        from constat.store import Catalogue

        assert Catalogue(workspace).list() == ()

        Releases(workspace).declare("2026.11", "A Reviewer")
        result = Review(workspace).accept(
            proposal_id, decided_by="A Reviewer", release="2026.11"
        )
        assert result.version_no == 1

    def test_two_versions_can_be_agreed_for_different_releases(self, workspace):
        releases = Releases(workspace)
        releases.declare("2026.11", "A Reviewer")
        releases.declare("2026.12", "A Reviewer")
        review = Review(workspace)

        first = review.accept(
            _proposal(workspace, "one"), decided_by="A Reviewer", release="2026.11"
        )
        second = review.accept(
            _proposal(workspace, "two"), decided_by="A Reviewer", release="2026.12"
        )

        assert (first.release, second.release) == ("2026.11", "2026.12")

    def test_the_release_is_readable_from_the_version_history(self, workspace):
        """Written and never readable would be a column, not a record."""
        Releases(workspace).declare("2026.11", "A Reviewer")
        result = Review(workspace).accept(
            _proposal(workspace), decided_by="A Reviewer", release="2026.11"
        )

        versions = Review(workspace).versions(result.rule_id)

        assert versions[0]["release_name"] == "2026.11"

    def test_a_version_with_no_release_still_appears_in_history(self, workspace):
        """The LEFT JOIN this needs. An inner join would drop every version
        accepted without a release, which is all of them in any workspace that
        declares none — and the history would simply be empty."""
        result = Review(workspace).accept(
            _proposal(workspace), decided_by="A Reviewer"
        )

        versions = Review(workspace).versions(result.rule_id)

        assert len(versions) == 1
        assert versions[0]["release_name"] is None


class TestWhatItDoesNotDecide:
    def test_a_release_does_not_make_a_version_current_behaviour(
        self, workspace, tmp_path
    ):
        """The line this ticket must not cross. D-087 verifies what is shipped
        by checking a rule's evidence commits against mainline, which is a
        stronger claim than a declared release's asserted ship (D-085). If
        agreeing a version for a release changed `constat state`, asserted
        behaviour would have replaced verified behaviour."""
        from constat.operations import product_state

        Releases(workspace).declare("2026.11", "A Reviewer")
        with_release = Review(workspace).accept(
            _proposal(workspace, "with-release"),
            decided_by="A Reviewer",
            release="2026.11",
        )
        without = Review(workspace).accept(
            _proposal(workspace, "without-release"), decided_by="A Reviewer"
        )

        state = product_state(workspace)

        # Both rules are treated identically: the release changed nothing about
        # whether either is in effect.
        placed = {entry.rule.name for entry in state.rules}
        assert {"with-release", "without-release"} <= placed
        assert with_release.release == "2026.11"
        assert without.release is None


# -- the schema ---------------------------------------------------------------


class TestTheMigration:
    def _rewound(self, tmp_path: Path) -> Path:
        home = tmp_path / "old"
        with Workspace.create(home) as ws:
            ws.execute(
                "INSERT INTO ticket (reference, created_at) VALUES ('402', '2026-01-01')"
            )
        rewind_workspace(home / "workspace.db", 20)
        return home

    def test_a_schema_20_workspace_migrates_on_open(self, tmp_path: Path):
        home = self._rewound(tmp_path)

        with Workspace.open(home) as ws:
            assert ws.schema_version == SCHEMA_VERSION
            tables = {
                row["name"]
                for row in ws.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        assert "release" in tables

    def test_nothing_is_back_filled(self, tmp_path: Path):
        """Giving existing versions a release would assert that they shipped in
        one nobody declared — the claim this ticket exists to make recordable
        rather than to invent."""
        home = self._rewound(tmp_path)

        with Workspace.open(home) as ws:
            assert ws.execute("SELECT COUNT(*) AS n FROM release").fetchone()["n"] == 0
            unassigned = ws.execute(
                "SELECT COUNT(*) AS n FROM rule_version WHERE release_id IS NOT NULL"
            ).fetchone()["n"]
        assert unassigned == 0

    def test_the_existing_ticket_survives(self, tmp_path: Path):
        home = self._rewound(tmp_path)

        with Workspace.open(home) as ws:
            rows = ws.execute("SELECT reference FROM ticket").fetchall()

        assert [row["reference"] for row in rows] == ["402"]

    def test_a_release_declared_after_migrating_works(self, tmp_path: Path):
        """The migration has to produce a working table, not just a present
        one — including its append-only triggers."""
        home = self._rewound(tmp_path)

        with Workspace.open(home) as ws:
            Releases(ws).declare("2026.11", "A Reviewer")
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                ws.execute("DELETE FROM release")

    def test_a_migrated_workspace_matches_a_fresh_one(self, tmp_path: Path):
        """The property the schema comments have claimed since CON-81 and
        nothing checked: `ALTER TABLE` cannot add an inline `UNIQUE`, so a
        migration has to use an explicit index — and two shapes of the same
        table is a difference waiting to surprise somebody.

        Compared across every table, index and trigger, so this guards each
        future migration rather than only this one.
        """
        migrated = self._rewound(tmp_path)
        with Workspace.open(migrated) as ws:
            was_migrated = _shape(ws)

        with Workspace.create(tmp_path / "fresh") as ws:
            was_fresh = _shape(ws)

        assert was_migrated == was_fresh


def _shape(workspace) -> dict[str, object]:
    """Every table's columns, and every index and trigger, for comparison.

    **Tables are compared by `PRAGMA table_info`, not by their SQL text.** The
    fresh DDL carries its `--` comments inside `sqlite_master.sql` and a
    migration's does not, so comparing the text could never match however it
    was normalised — and the text is not the structure anyway. The pragma
    gives name, type, nullability, default and primary key, in order, which is
    what a query actually depends on.

    Indexes and triggers *are* compared by SQL, with whitespace collapsed: the
    fresh DDL is formatted for reading and a migration's is written on one
    line, and the difference that matters is what they say.
    """
    shape: dict[str, object] = {}
    for row in workspace.execute(
        "SELECT name, type, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        if row["type"] == "table":
            shape[f"table:{row['name']}"] = tuple(
                (c["name"], c["type"], c["notnull"], c["dflt_value"], c["pk"])
                for c in workspace.execute(
                    f"PRAGMA table_info({row['name']})"
                )
            )
        else:
            shape[f"{row['type']}:{row['name']}"] = " ".join(
                (row["sql"] or "").split()
            )
    return shape
