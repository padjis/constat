"""A ticket carries the requirements it answers (CON-18, D-104).

`requirement_ref` has been in the provenance taxonomy since the beginning and
written by nothing. D-094 chose to name that gap rather than tidy the enum away;
this closes it for one of the three, and the tests here are mostly about the
three boundaries that keep the label honest:

1. **Supplied, never fetched.** Constat does not open the artefact. Every view
   says *supplied*, never *verified* — a reference that read as checked would be
   a stronger claim than anything here can support.
2. **A person supplies it, never a model.** There is no path from a reading to
   this table. A reference written by a provider would be `ai_interpretation`
   wearing the label of external evidence, which would make the taxonomy itself
   dishonest.
3. **It does not leave the machine.** A label or URI is internal by nature — a
   tracker host, a project code, sometimes a customer's name — and the payload
   is an egress boundary (D-040, D-047). Sending requirements to a model would
   plainly improve a reading, and that is a separate question with a disclosure
   dimension.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from constat.errors import InvalidInput, NotRegistered
from constat.operations import PRODUCED_PROVENANCE, UNPRODUCED_PROVENANCE
from constat.store import Registry, Requirements, TicketStore, Workspace

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


# -- supplying -----------------------------------------------------------------


class TestSupplying:
    def test_a_reference_is_recorded_against_a_ticket(self, workspace):
        supplied = Requirements(workspace).supply("402", "REQ-14", "A Reviewer")

        assert supplied.label == "REQ-14"
        assert supplied.reference == "402"
        assert supplied.supplied_by == "A Reviewer"

    def test_a_uri_is_optional(self, workspace):
        """A label with no pointer is still traceability: `spec § 3.2` is a
        reference somebody can follow without a URL."""
        supplied = Requirements(workspace).supply("402", "spec § 3.2", "A Reviewer")

        assert supplied.uri is None
        assert supplied.describe() == "spec § 3.2"

    def test_a_uri_is_recorded_when_given(self, workspace):
        supplied = Requirements(workspace).supply(
            "402", "REQ-14", "A Reviewer", uri="https://tracker.invalid/REQ-14"
        )

        assert "tracker.invalid" in supplied.describe()

    def test_an_empty_uri_is_stored_as_absent(self, workspace):
        """So a view does not render an empty link, which reads as broken
        rather than as omitted."""
        supplied = Requirements(workspace).supply(
            "402", "REQ-14", "A Reviewer", uri="   "
        )

        assert supplied.uri is None

    def test_the_label_is_stored_verbatim(self, workspace):
        """D-102's reasoning: a field Constat interprets becomes a claim it
        cannot support. Nothing parses `JIRA-882` into a project and a number."""
        supplied = Requirements(workspace).supply("402", "JIRA-882", "A Reviewer")

        assert supplied.label == "JIRA-882"

    def test_an_empty_label_is_refused(self, workspace):
        with pytest.raises(InvalidInput, match="needs a label"):
            Requirements(workspace).supply("402", "   ", "A Reviewer")

    def test_the_requirement_s_text_cannot_be_pasted_in(self, workspace):
        """The bound exists for this. Copying the requirement's prose into the
        label would be ingesting the artefact by hand, which is the thing this
        deliberately does not do — the artefact stays at the other end."""
        with pytest.raises(InvalidInput, match="not the requirement's text"):
            Requirements(workspace).supply("402", "x" * 200, "A Reviewer")

    def test_an_unknown_ticket_is_refused(self, workspace):
        """Attaching a reference to work nobody opened would leave a row
        nothing can reach."""
        with pytest.raises(NotRegistered, match="no ticket '999'"):
            Requirements(workspace).supply("999", "REQ-14", "A Reviewer")

    def test_the_same_label_twice_on_one_ticket_is_refused(self, workspace):
        requirements = Requirements(workspace)
        requirements.supply("402", "REQ-14", "A Reviewer")

        with pytest.raises(InvalidInput, match="already cites"):
            requirements.supply("402", "REQ-14", "Another Reviewer")

    def test_the_same_label_on_a_different_ticket_is_fine(self, workspace):
        """Two tickets can answer one requirement, which is the normal shape of
        work split across changes."""
        TicketStore(workspace).add("403")
        requirements = Requirements(workspace)
        requirements.supply("402", "REQ-14", "A Reviewer")
        requirements.supply("403", "REQ-14", "A Reviewer")

        assert len(requirements.all()) == 2

    def test_how_the_decider_was_established_is_recorded(self, workspace):
        """D-061 again: a name from git config and a name a person typed are
        both unverified, and only one was asserted."""
        supplied = Requirements(workspace).supply(
            "402", "REQ-14", "someone", attribution="inferred"
        )

        assert supplied.attribution == "inferred"


class TestItIsAppendOnly:
    def test_a_reference_cannot_be_edited(self, workspace):
        """A reviewer who navigated from a rule proposal to a requirement needs
        it to still say what it said."""
        Requirements(workspace).supply("402", "REQ-14", "A Reviewer")

        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            workspace.execute("UPDATE requirement SET label = 'REQ-99'")

    def test_a_reference_cannot_be_deleted(self, workspace):
        """Traceability that can be quietly removed is traceability only until
        it is inconvenient."""
        Requirements(workspace).supply("402", "REQ-14", "A Reviewer")

        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            workspace.execute("DELETE FROM requirement")


class TestReading:
    def test_they_come_back_oldest_first(self, workspace):
        requirements = Requirements(workspace)
        for label in ("REQ-14", "REQ-2", "JIRA-882"):
            requirements.supply("402", label, "A Reviewer")

        assert [r.label for r in requirements.for_ticket("402")] == [
            "REQ-14",
            "REQ-2",
            "JIRA-882",
        ]

    def test_a_ticket_with_none_returns_nothing(self, workspace):
        assert Requirements(workspace).for_ticket("402") == ()

    def test_an_unknown_ticket_reads_as_nothing_rather_than_refusing(
        self, workspace
    ):
        """A view asking "what does this cite" gets "nothing" for something
        that does not exist. `supply` is where a missing ticket matters."""
        assert Requirements(workspace).for_ticket("999") == ()


# -- the provenance type -------------------------------------------------------


class TestItHasAProducerNow:
    def test_requirement_ref_is_no_longer_listed_as_unproduced(self):
        """The gap D-094 named, closed for one of the three."""
        assert "requirement_ref" not in UNPRODUCED_PROVENANCE
        assert "requirement_ref" in PRODUCED_PROVENANCE

    def test_only_two_types_remain_without_a_producer(self):
        assert set(UNPRODUCED_PROVENANCE) == {"test_evidence", "assumption"}

    def test_its_meaning_says_supplied_not_verified(self):
        """The whole weight the label now carries. "Supplied" and "verified"
        are different claims, and the legend is where a reader learns which."""
        meaning = PRODUCED_PROVENANCE["requirement_ref"]

        assert "Supplied, never fetched" in meaning


# -- the boundaries ------------------------------------------------------------


class TestItNeverLeavesTheMachine:
    def test_the_payload_carries_no_requirement(self, workspace):
        """The egress boundary. A label or URI is internal by nature, and the
        payload is what crosses to a provider (D-040, D-047). Feeding
        requirements to a model is a separate question with a disclosure
        dimension, not something to smuggle in here."""
        from constat.ai import as_dict
        from constat.operations import export_payload, gather

        Requirements(workspace).supply(
            "402", "REQ-14", "A Reviewer", uri="https://tracker.invalid/REQ-14"
        )
        gather(workspace, "402")

        payload = as_dict(export_payload(workspace, "402").payload)

        assert "REQ-14" not in str(payload)
        assert "tracker.invalid" not in str(payload)

    def test_no_mcp_tool_can_supply_one(self):
        """A reference written by a model would be an interpretation wearing
        the label of external evidence. The same boundary D-048 draws around
        acceptance, applied to evidence."""
        pytest.importorskip("mcp", reason="the MCP server is an optional extra")
        from constat.mcp import EXPOSED_TOOLS

        assert not [name for name in EXPOSED_TOOLS if "requirement" in name]


# -- the views -----------------------------------------------------------------


class TestWhatAReviewerSees:
    def _home(self, workspace) -> str:
        return str(Path(workspace.path).parent)

    def test_ticket_show_lists_them(self, workspace, capsys):
        from constat.cli import main

        Requirements(workspace).supply(
            "402", "REQ-14", "A Reviewer", uri="https://tracker.invalid/REQ-14"
        )
        capsys.readouterr()

        main(["--workspace", self._home(workspace), "ticket", "show", "402"])

        out = capsys.readouterr().out
        assert "REQ-14" in out
        assert "not verified" in out

    def test_the_rule_proposal_queue_shows_them(self, workspace, capsys):
        """The moment the question "what was this supposed to do?" is actually
        asked. The answer existing on another command is not the same as a
        reviewer seeing it while deciding."""
        from constat.cli import main
        from constat.models import Anchor, RuleProposal
        from constat.operations import open_run
        from constat.store import RuleProposals

        Requirements(workspace).supply("402", "REQ-14", "A Reviewer")
        run_id = open_run(workspace, "402", "submit_reply")
        RuleProposals(workspace).record(
            run_id,
            RuleProposal(
                name="daily-limit",
                statement="A transfer above the daily limit is refused.",
                anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            ),
            provider="mcp",
        )
        capsys.readouterr()

        main(["--workspace", self._home(workspace), "rule", "proposals", "402"])

        out = capsys.readouterr().out
        assert "supplied requirements (1) — not verified" in out

    def test_the_command_refuses_a_duplicate_with_a_message_not_a_traceback(
        self, workspace, capsys
    ):
        """Found by running it: `_run_ticket` caught no `InvalidInput`, so the
        refusal arrived as a crash report where a sentence was meant."""
        from constat.cli import main

        home = self._home(workspace)
        main(["--workspace", home, "ticket", "requirement", "402", "REQ-14",
              "--by", "A Reviewer"])
        capsys.readouterr()

        code = main(["--workspace", home, "ticket", "requirement", "402",
                     "REQ-14", "--by", "A Reviewer"])

        assert code != 0
        assert "already cites" in capsys.readouterr().err

    def test_the_command_says_it_did_not_open_the_artefact(
        self, workspace, capsys
    ):
        from constat.cli import main

        capsys.readouterr()
        main(["--workspace", self._home(workspace), "ticket", "requirement",
              "402", "REQ-14", "--by", "A Reviewer"])

        out = capsys.readouterr().out
        assert "supplied, not verified" in out
        assert "did not open it" in out


class TestTheDocument:
    def test_a_supplied_requirement_appears_in_its_own_section(self, workspace):
        """Product rule 3: requirements stay distinguishable from implementation
        evidence. A pointer among observed facts would read as checked."""
        from constat.operations import collect, gather, render

        Requirements(workspace).supply(
            "402", "REQ-14", "A Reviewer", uri="https://tracker.invalid/REQ-14"
        )
        gather(workspace, "402")

        body = render(
            "402",
            collect(workspace, "402"),
            requirements=Requirements(workspace).for_ticket("402"),
        )

        assert "## Supplied requirements" in body
        assert "[REQ-14](https://tracker.invalid/REQ-14)" in body
        assert "supplied, not verified" in body

    def test_the_section_is_absent_when_nothing_was_supplied(self, workspace):
        """An empty section is a question nobody asked. The legend still names
        the type, which is how a reader knows it exists."""
        from constat.operations import collect, gather, render

        gather(workspace, "402")

        body = render("402", collect(workspace, "402"))

        assert "## Supplied requirements" not in body
        assert "`requirement_ref`" in body

    def test_the_legend_and_the_document_agree(self, workspace):
        """The consistency this had to maintain in both directions. Before
        CON-18 the legend said `requirement_ref` had no producer; it now says
        it has one, so a document must be able to show it — a label explained
        in the key and never appearing would be the same defect reversed."""
        from constat.operations import collect, gather, render

        Requirements(workspace).supply("402", "REQ-14", "A Reviewer")
        gather(workspace, "402")

        body = render(
            "402",
            collect(workspace, "402"),
            requirements=Requirements(workspace).for_ticket("402"),
        )

        assert "produced by nothing today" in body
        assert "requirement_ref" not in body.split("produced by nothing today")[1]
