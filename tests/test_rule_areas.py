"""A rule carries a business area (CON-77, D-070).

The catalogue *is* the product's business documentation, and documentation with
no organisation is a list nobody reads. An area is the heading a business
reader would look under — "advertising", "device provisioning" — and never a
module, package or directory, because the axis a business reader does not care
about is where the code lives.

Three properties carry these tests:

1. **An area is a business statement**, so D-066's gate applies to it
   unchanged: `DeviceProvisioningService` is not an area.
2. **It is frozen on the accepted version**, alongside the name and statement.
   Which area a rule was understood to belong to is part of what a human
   accepted, and a later re-grouping must not rewrite that.
3. **Absence is a real value.** A rule accepted before areas existed has none
   and renders as unplaced. Nothing back-fills one: inventing an area for a
   frozen version would put a claim nobody made into a governance record.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from constat.ai import as_dict as payload_as_dict
from constat.ai.parsing import MAX_AREA, parse
from constat.ai.redaction import (
    CommitContext,
    FileChange,
    ProviderPayload,
    RepositoryContext,
)
from constat.models import Anchor, Behaviour, RuleProposal
from constat.operations import export_payload, open_run
from constat.store import Catalogue, Registry, Review, RuleProposals, TicketStore, Workspace
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


def _payload() -> ProviderPayload:
    return ProviderPayload(
        reference=REFERENCE,
        repositories=(
            RepositoryContext(
                alias="billing",
                default_branch="main",
                status="pending",
                commits=(
                    CommitContext(
                        sha="d" * 40,
                        subject="Raise the limit",
                        body="",
                        files=(
                            FileChange(
                                path="rules.py", change_type="modified", diff="d"
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def _reply(**overrides) -> str:
    rule = {
        "name": "daily-limit",
        "statement": "A transfer above the daily limit is refused.",
        "behaviours": ["Refuse it and explain the limit"],
        "anchors": [{"path_glob": "rules.py", "repository_alias": "billing"}],
    }
    rule.update(overrides)
    return json.dumps({"rules": [rule]})


def _record(workspace, area: str | None = "payments") -> int:
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    return RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name="daily-limit",
            statement="A transfer above the daily limit is refused.",
            behaviours=(Behaviour(description="Refuse it"),),
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            area=area,
        ),
        provider="mcp",
        model="claude-opus-5",
    )


# -- an area is a business statement ------------------------------------------


class TestParsingTheArea:
    def test_a_business_area_is_accepted(self) -> None:
        result = parse(_reply(area="payments"), _payload())

        assert result.rejections == ()
        assert result.proposals[0].area == "payments"

    def test_an_area_naming_code_is_refused(self) -> None:
        """D-066 applies to the area unchanged — same gate, no new machinery."""
        result = parse(_reply(area="DeviceProvisioningService"), _payload())

        assert result.proposals == ()
        reason = result.rejections[0].reason
        assert "'area' is not a business area" in reason
        assert "DeviceProvisioningService" in reason

    @pytest.mark.parametrize(
        "area", ["commons/src/main/java", "device_provisioning", "poll()"]
    )
    def test_other_shapes_of_code_too(self, area: str) -> None:
        result = parse(_reply(area=area), _payload())

        assert result.proposals == ()
        assert "not a business area" in result.rejections[0].reason

    def test_an_omitted_area_is_unplaced_not_an_error(self) -> None:
        """A reading that cannot see where a rule belongs must say nothing
        rather than invent a heading."""
        result = parse(_reply(), _payload())

        assert result.rejections == ()
        assert result.proposals[0].area is None

    def test_an_empty_area_is_unplaced(self) -> None:
        result = parse(_reply(area="   "), _payload())

        assert result.proposals[0].area is None

    def test_a_statement_in_the_area_field_is_refused(self) -> None:
        """An area is a heading. A long one is a sentence that wandered."""
        result = parse(_reply(area="a" * (MAX_AREA + 1)), _payload())

        assert result.proposals == ()
        assert f"longer than {MAX_AREA}" in result.rejections[0].reason


# -- it is frozen on what a human accepted ------------------------------------


class TestAcceptanceCarriesIt:
    def test_the_rule_gets_the_area(self, workspace) -> None:
        Review(workspace).accept(_record(workspace), decided_by="emmanuel")

        assert Catalogue(workspace).find("daily-limit").area == "payments"

    def test_the_frozen_version_keeps_it(self, workspace) -> None:
        """Part of what was accepted, so a later re-grouping cannot rewrite it.

        Asserted on the stored version rather than on the rule: `rule` is the
        mutable working view and `rule_version` is the durable record (D-029).
        """
        result = Review(workspace).accept(_record(workspace), decided_by="emmanuel")

        row = workspace.execute(
            "SELECT area FROM rule_version WHERE id = ?", (result.rule_version_id,)
        ).fetchone()
        assert row["area"] == "payments"

    def test_a_revision_can_move_a_rule_without_losing_the_old_placement(
        self, workspace
    ) -> None:
        """Version 1 stays readable under the area it was accepted in."""
        review = Review(workspace)
        first = review.accept(_record(workspace, "payments"), decided_by="emmanuel")

        run_id = open_run(workspace, REFERENCE, "submit_reply")
        moved = RuleProposals(workspace).record(
            run_id,
            RuleProposal(
                name="daily-limit",
                statement="A transfer above the daily limit is refused.",
                anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
                area="transfers",
                relation="revises",
                revises_rule_id=first.rule_id,
            ),
            provider="mcp",
            revises_rule_id=first.rule_id,
        )
        review.accept(moved, decided_by="emmanuel")

        versions = review.versions(first.rule_id)
        assert [v["area"] for v in versions] == ["payments", "transfers"]
        assert Catalogue(workspace).find("daily-limit").area == "transfers"

    def test_an_unplaced_rule_stays_unplaced(self, workspace) -> None:
        Review(workspace).accept(_record(workspace, None), decided_by="emmanuel")

        assert Catalogue(workspace).find("daily-limit").area is None


# -- the reader is shown what exists, so the taxonomy can be reused -----------


class TestTheReaderSeesExistingAreas:
    def test_the_payload_carries_each_rule_area(self, workspace) -> None:
        """Otherwise every reading coins its own synonym: "advertising", then
        "ads", then "monetisation" (D-070 names this as expected)."""
        Review(workspace).accept(_record(workspace, "payments"), decided_by="emmanuel")

        payload = payload_as_dict(export_payload(workspace, REFERENCE).payload)

        assert [r["area"] for r in payload["catalogue"]] == ["payments"]

    def test_the_guidance_insists_on_reuse(self) -> None:
        from constat.ai.guidance import AREAS

        assert "Reuse an area that already exists" in AREAS

    def test_the_guidance_forbids_a_code_shaped_area(self) -> None:
        from constat.ai.guidance import AREAS

        assert "Not a module, a package, a service or a directory" in AREAS

    def test_the_guidance_allows_leaving_it_out(self) -> None:
        """A guessed area quietly reorganises the documentation."""
        from constat.ai.guidance import AREAS

        assert "Leave the area out" in AREAS

    def test_both_prompt_paths_carry_it(self) -> None:
        import asyncio

        from constat.ai.guidance import AREAS, for_system_prompt
        from constat.mcp import build_server

        assert AREAS in for_system_prompt()
        got = asyncio.run(
            build_server("/tmp").get_prompt("document", {"reference": REFERENCE})
        )
        assert AREAS in got.messages[0].content.text


# -- the catalogue reads as documentation -------------------------------------


class TestTheCatalogueIsGrouped:
    def test_rule_list_groups_by_area_with_unplaced_last(
        self, tmp_path: Path, capsys
    ) -> None:
        """Unplaced is a gap, not a section, so it sorts to the end."""
        from constat.cli import main

        home = tmp_path / "cli-ws"
        with Workspace.create(home) as ws:
            Registry(ws).add(
                str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")),
                alias="billing",
            )
            TicketStore(ws).add(REFERENCE)
            review = Review(ws)
            review.accept(_record(ws, "payments"), decided_by="emmanuel")
            run_id = open_run(ws, REFERENCE, "submit_reply")
            unplaced = RuleProposals(ws).record(
                run_id,
                RuleProposal(
                    name="statements-are-monthly",
                    statement="A statement is issued every month.",
                    anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
                ),
                provider="mcp",
            )
            review.accept(unplaced, decided_by="emmanuel")

        capsys.readouterr()
        main(["--workspace", str(home), "rule", "list"])
        out = capsys.readouterr().out

        assert out.index("payments:") < out.index("(unplaced):")

    def test_the_queue_shows_the_proposed_area(self, workspace, capsys) -> None:
        """A reviewer deciding has to see the placement they are accepting."""
        from constat.cli import _report_proposals

        _record(workspace, "payments")
        _report_proposals(RuleProposals(workspace), REFERENCE, False)

        assert "area: payments" in capsys.readouterr().out


# -- the migration ------------------------------------------------------------


class TestMigrationFromSchema10:
    def _at_schema_10(self, home: Path) -> int:
        """A real workspace wound back by dropping schema 11's columns.

        Built forwards and reversed rather than hand-written, for the reason
        the schema 9 fixture gives: hand-written DDL tests the transcription.
        """
        with Workspace.create(home) as ws:
            Registry(ws).add(
                str(distinct_subject(home.parent, "billing", "LIMIT = 250\n")),
                alias="billing",
            )
            TicketStore(ws).add(REFERENCE)
            proposal_id = _record(ws, "payments")
            Review(ws).accept(proposal_id, decided_by="emmanuel")

        rewind_workspace(home / "workspace.db", 10)
        return proposal_id

    def test_it_migrates_on_open(self, tmp_path: Path) -> None:
        self._at_schema_10(tmp_path / "ws")

        with Workspace.open(tmp_path / "ws") as ws:
            assert ws.schema_version == SCHEMA_VERSION

    def test_an_older_rule_is_unplaced_rather_than_back_filled(
        self, tmp_path: Path
    ) -> None:
        """Inventing an area for a frozen version would put a claim nobody
        made into a governance record."""
        self._at_schema_10(tmp_path / "ws")

        with Workspace.open(tmp_path / "ws") as ws:
            assert Catalogue(ws).find("daily-limit").area is None

    def test_an_older_reading_reads_back_without_an_area(
        self, tmp_path: Path
    ) -> None:
        proposal_id = self._at_schema_10(tmp_path / "ws")

        with Workspace.open(tmp_path / "ws") as ws:
            assert RuleProposals(ws).find(proposal_id).proposal.area is None
