"""A reading can say that evidence repairs a rule (CON-73, D-065).

Three relations, and the third is the new one:

* `establishes` — the evidence creates business knowledge that was not there.
* `revises` — it changes a rule already accepted.
* `repairs` — the rule was already true and the code was violating it.

A bug fix is the third case. Before this, a reading had to call it an
establishment, which is how ticket 628's repaired defect turned into three
proposals of invented business knowledge.

**The migration is tested as carefully as the feature.** A reading written
before schema 10 keeps `relation` NULL and is *derived* on read, never
updated: `rule_proposal` is append-only by trigger, and a migration that wrote
a column into historical readings would be editing what a reviewer was shown.
The derivation is sound rather than a guess — before the column existed the
only two relations were establishes and revises, and `revises_rule_id`
already says which.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from constat.ai.parsing import parse
from constat.ai.redaction import (
    CommitContext,
    FileChange,
    KnownRule,
    ProviderPayload,
    RepositoryContext,
)
from constat.models import Anchor, Behaviour, RuleProposal
from constat.operations import open_run
from constat.store import Registry, Review, RuleProposals, TicketStore, Workspace
from constat.store.schema import SCHEMA_VERSION
from constat.store.workspace import utc_now

from test_runs import distinct_subject


REFERENCE = "628"


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
        )
        TicketStore(ws).add(REFERENCE)
        yield ws


def _payload(catalogue: tuple[KnownRule, ...] = ()) -> ProviderPayload:
    """Evidence containing `rules.py`, so an anchor to it is grounded.

    Without a changed path the anchor check rejects every proposal first and
    these tests would pass or fail for a reason that has nothing to do with
    relations.
    """
    return ProviderPayload(
        reference=REFERENCE,
        repositories=(
            RepositoryContext(
                alias="billing",
                default_branch="main",
                status="pending",
                commits=(
                    CommitContext(
                        sha="d2797f4f4a3c03181d1a2654ad2cb2e10e301a5f",
                        subject="Absorb the first-launch race",
                        body="",
                        files=(
                            FileChange(
                                path="rules.py",
                                change_type="modified",
                                diff="@@ -1 +1 @@\n-LIMIT = 100\n+LIMIT = 250\n",
                            ),
                        ),
                    ),
                ),
            ),
        ),
        catalogue=catalogue,
    )


def _reply(**overrides) -> str:
    rule = {
        "name": "a-first-launch-works",
        "statement": "A new user's first use of the app works.",
        "behaviours": ["A new user reaches the app on first launch"],
        "anchors": [{"path_glob": "rules.py", "repository_alias": "billing"}],
    }
    rule.update(overrides)
    return json.dumps({"rules": [rule]})


# -- parsing the relation -----------------------------------------------------


class TestParsingTheRelation:
    def test_a_repair_is_accepted_and_carried(self) -> None:
        result = parse(_reply(relation="repairs"), _payload())

        assert result.rejections == ()
        assert result.proposals[0].relation == "repairs"
        assert result.proposals[0].revises_rule_id is None

    def test_the_default_is_establishes(self) -> None:
        """Silence must not read as a repair: the weaker claim is the default."""
        result = parse(_reply(), _payload())

        assert result.proposals[0].relation == "establishes"

    def test_an_omitted_relation_with_an_id_is_a_revision(self) -> None:
        """Derived from what the reply already said, not defaulted.

        A reading written before `relation` existed names an id to mean a
        revision, and that is still exactly what it means.
        """
        catalogue = (KnownRule(rule_id=7, name="old", statement="An old rule."),)
        result = parse(_reply(revises=7), _payload(catalogue))

        assert result.proposals[0].relation == "revises"
        assert result.proposals[0].revises_rule_id == 7

    def test_an_unknown_relation_is_refused(self) -> None:
        result = parse(_reply(relation="improves"), _payload())

        assert result.proposals == ()
        assert "'relation' is 'improves'" in result.rejections[0].reason

    def test_revises_without_an_id_is_refused(self) -> None:
        """The relation and the id have to agree, or the reading says nothing."""
        result = parse(_reply(relation="revises"), _payload())

        assert result.proposals == ()
        assert "no rule id was named" in result.rejections[0].reason

    def test_a_repair_naming_an_id_is_refused(self) -> None:
        """CON-73's stated boundary, refused rather than silently dropped.

        A repair states its rule; it does not point at one. Dropping half of a
        contradictory claim would store a reading that says something the
        reader did not say.
        """
        catalogue = (KnownRule(rule_id=7, name="old", statement="An old rule."),)
        result = parse(_reply(relation="repairs", revises=7), _payload(catalogue))

        assert result.proposals == ()
        reason = result.rejections[0].reason
        assert "a repair states the rule it repairs" in reason

    def test_the_relation_is_case_insensitive(self) -> None:
        result = parse(_reply(relation="REPAIRS"), _payload())

        assert result.proposals[0].relation == "repairs"


# -- storing and reading it back ----------------------------------------------


def _record(workspace, relation: str = "repairs", revises: int | None = None) -> int:
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    return RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name="a-first-launch-works",
            statement="A new user's first use of the app works.",
            behaviours=(Behaviour(description="A new user reaches the app"),),
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            revises_rule_id=revises,
            relation=relation,
        ),
        provider="mcp",
        model="claude-opus-5",
        revises_rule_id=revises,
    )


class TestStorage:
    def test_a_repair_survives_the_round_trip(self, workspace) -> None:
        proposal_id = _record(workspace)

        stored = RuleProposals(workspace).find(proposal_id)

        assert stored.relation == "repairs"
        assert stored.is_repair

    def test_an_establishment_is_not_a_repair(self, workspace) -> None:
        stored = RuleProposals(workspace).find(_record(workspace, "establishes"))

        assert stored.relation == "establishes"
        assert stored.is_repair is False

    def test_accepting_a_repair_creates_the_rule(self, workspace) -> None:
        """The valuable case: the rule nobody had written down.

        D-065 routes a repair through the queue precisely so acceptance stays
        the only door into the catalogue — a repair that proposed nothing would
        be an assertion with no human decision behind it.
        """
        proposal_id = _record(workspace)

        result = Review(workspace).accept(proposal_id, decided_by="emmanuel")

        assert result.created_rule
        assert result.version_no == 1

    def test_the_accepted_version_still_points_at_the_repair(self, workspace) -> None:
        """No column on `rule_version`: the relation is reachable through the
        reading the version was baselined from, which is where provenance
        already lives."""
        proposal_id = _record(workspace)
        Review(workspace).accept(proposal_id, decided_by="emmanuel")

        row = workspace.execute(
            "SELECT v.from_rule_proposal_id AS pid, p.relation "
            "FROM rule_version v JOIN rule_proposal p ON p.id = v.from_rule_proposal_id",
        ).fetchone()
        assert row["pid"] == proposal_id
        assert row["relation"] == "repairs"

    def test_the_database_refuses_an_unknown_relation(self, workspace) -> None:
        """Enforced by CHECK for a workspace created at schema 10.

        A migrated workspace cannot carry this constraint — SQLite's ADD COLUMN
        takes no CHECK — so `parse` is the gate that covers both. Asserted here
        so the difference is visible rather than assumed.
        """
        run_id = open_run(workspace, REFERENCE, "submit_reply")
        with pytest.raises(sqlite3.IntegrityError):
            workspace.execute(
                "INSERT INTO rule_proposal "
                "(run_id, name, statement, relation, provider, created_at) "
                "VALUES (?, 'x', 'y', 'improves', 'mcp', ?)",
                (run_id, utc_now()),
            )


# -- the migration ------------------------------------------------------------


class TestMigrationFromSchema9:
    """A schema 9 workspace gains the column and keeps its readings intact."""

    def _at_schema_9(self, home: Path) -> int:
        """A real workspace, wound back to 9 by dropping the new column.

        Built forwards and then reversed rather than hand-written: the v1
        fixture in test_workspace.py is 300 lines of DDL, and reproducing
        schema 9 by hand would test my transcription rather than the
        migration.
        """
        with Workspace.create(home) as ws:
            Registry(ws).add(
                str(distinct_subject(home.parent, "billing", "LIMIT = 250\n")),
                alias="billing",
            )
            TicketStore(ws).add(REFERENCE)
            proposal_id = _record(ws, "establishes")

        connection = sqlite3.connect(home / "workspace.db")
        connection.execute("DROP TRIGGER rule_proposal_is_append_only_update")
        connection.execute("ALTER TABLE rule_proposal DROP COLUMN relation")
        connection.execute(
            "CREATE TRIGGER rule_proposal_is_append_only_update "
            "BEFORE UPDATE ON rule_proposal BEGIN "
            "SELECT RAISE(ABORT, 'rule_proposal is append-only: a reading "
            "cannot be edited'); END"
        )
        connection.execute("UPDATE schema_meta SET schema_version = 9 WHERE id = 1")
        connection.commit()
        connection.close()
        return proposal_id

    def test_the_workspace_is_migrated_on_open(self, tmp_path: Path) -> None:
        self._at_schema_9(tmp_path / "ws")

        with Workspace.open(tmp_path / "ws") as ws:
            assert ws.schema_version == SCHEMA_VERSION

    def test_an_older_readings_relation_is_derived_not_stored(
        self, tmp_path: Path
    ) -> None:
        """NULL in the column, `establishes` on read. Both halves asserted:
        the row is untouched *and* the reading still answers the question."""
        proposal_id = self._at_schema_9(tmp_path / "ws")

        with Workspace.open(tmp_path / "ws") as ws:
            raw = ws.execute(
                "SELECT relation FROM rule_proposal WHERE id = ?", (proposal_id,)
            ).fetchone()
            assert raw["relation"] is None

            assert RuleProposals(ws).find(proposal_id).relation == "establishes"

    def test_an_older_revision_derives_as_a_revision(self, tmp_path: Path) -> None:
        home = tmp_path / "ws"
        self._at_schema_9(home)

        with Workspace.open(home) as ws:
            # Accept the migrated reading so there is a rule to revise, then
            # record a revision and wind its relation back to NULL the way a
            # schema 9 row would have it.
            first = RuleProposals(ws).for_ticket(REFERENCE)[0]
            rule_id = Review(ws).accept(first.id, decided_by="emmanuel").rule_id
            revision = _record(ws, "revises", revises=rule_id)
            ws.execute("DROP TRIGGER rule_proposal_is_append_only_update")
            ws.execute(
                "UPDATE rule_proposal SET relation = NULL WHERE id = ?", (revision,)
            )

            assert RuleProposals(ws).find(revision).relation == "revises"

    def test_a_migrated_reading_can_never_read_as_a_repair(
        self, tmp_path: Path
    ) -> None:
        """Nothing could claim a repair before there was a way to say it, so no
        derivation may produce one."""
        proposal_id = self._at_schema_9(tmp_path / "ws")

        with Workspace.open(tmp_path / "ws") as ws:
            assert RuleProposals(ws).find(proposal_id).is_repair is False


# -- what the reader and the reviewer are told --------------------------------


class TestGuidanceAndDisplay:
    def test_the_guidance_names_the_three_relations(self) -> None:
        from constat.ai.guidance import RELATIONS

        for relation in ("establishes", "revises", "repairs"):
            assert relation in RELATIONS

    def test_the_guidance_says_a_bug_fix_is_usually_a_repair(self) -> None:
        from constat.ai.guidance import RELATIONS

        assert "bug fix" in RELATIONS

    def test_the_guidance_keeps_the_repair_out_of_the_statement(self) -> None:
        """Product rule 3: the claim about the code must not enter the rule."""
        from constat.ai.guidance import RELATIONS

        assert "Keep the repair out of the statement" in RELATIONS

    def test_both_prompt_paths_carry_it(self) -> None:
        import asyncio

        from constat.ai.guidance import RELATIONS, for_system_prompt
        from constat.mcp import build_server

        assert RELATIONS in for_system_prompt()
        got = asyncio.run(
            build_server("/tmp").get_prompt("document", {"reference": REFERENCE})
        )
        assert RELATIONS in got.messages[0].content.text

    def test_the_cli_queue_says_a_repair_is_a_repair(self, workspace, capsys) -> None:
        from constat.cli import _report_proposals

        _record(workspace)
        _report_proposals(RuleProposals(workspace), REFERENCE, False)

        assert "REPAIR" in capsys.readouterr().out

    def test_the_document_renders_a_repair_distinctly(self, workspace) -> None:
        """A business reader has to be able to tell "we now do this" from "we
        always said we did this, and had stopped"."""
        from constat.ai.provider import Interpretation
        from constat.operations import catalogue_view, collect, render

        _record(workspace)
        findings = collect(workspace, REFERENCE)
        body = render(
            REFERENCE,
            findings,
            # The business half renders only when a run reported something,
            # even nothing: "we found no rules" and "we did not look" are
            # different claims, so the section is absent rather than empty.
            interpretation=Interpretation(provider="mcp", note="an agent reads this"),
            view=catalogue_view(workspace, REFERENCE, findings),
        )

        assert "the code was violating" in body
