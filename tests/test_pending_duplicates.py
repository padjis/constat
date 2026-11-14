"""A re-run must not duplicate a pending rule proposal (CON-70).

Found by running ticket 615 through the MCP loop on 2026-11-14: a second
reading of the same evidence produced a near-identical proposal, and
`submit_rules` reported `possible_duplicates: {}` while the first one sat in
the queue. Duplicate detection looked at the `anchor` table — accepted rules
only — and the payload never showed the queue at all.

Two halves, tested separately because they fail separately:

1. **The reader is shown the queue**, so it can decline to say what has
   already been said.
2. **The submission reports the overlap**, so a reviewer about to accept sees
   that two proposals may be one rule.

What is deliberately *not* tested is refusal, because a duplicate is not
refused. Two readings converging is evidence worth keeping (it is what
validated the guidance in the first place), so both are stored and a person
collapses them. A test asserting a discard would be asserting the wrong
product.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.ai import PendingProposal
from constat.ai import as_dict as payload_as_dict
from constat.models import Anchor, Behaviour, RuleProposal
from constat.operations import (
    export_payload,
    open_run,
    pending_readings,
    submit_reply,
)
from constat.store import Registry, Review, RuleProposals, TicketStore, Workspace

from test_runs import distinct_subject


REFERENCE = "622"


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
        )
        TicketStore(ws).add(REFERENCE)
        yield ws


def a_reading(
    name: str = "daily-limit",
    statement: str = "A transfer over the daily limit is refused.",
    glob: str = "rules.py",
) -> RuleProposal:
    return RuleProposal(
        name=name,
        statement=statement,
        behaviours=(Behaviour(description="Refuse and explain the limit"),),
        anchors=(Anchor(path_glob=glob, repository_alias="billing"),),
    )


def record(workspace, reading: RuleProposal) -> int:
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    return RuleProposals(workspace).record(
        run_id, reading, provider="mcp", model="claude-opus-5"
    )


# -- the reader is shown the queue --------------------------------------------


class TestThePayloadShowsTheQueue:
    def test_an_undecided_proposal_reaches_the_reader(self, workspace) -> None:
        proposal_id = record(workspace, a_reading())

        pending = pending_readings(workspace, REFERENCE)

        assert [p.proposal_id for p in pending] == [proposal_id]
        assert pending[0].statement == "A transfer over the daily limit is refused."
        assert pending[0].anchors == ("rules.py",)

    def test_a_decided_proposal_does_not(self, workspace) -> None:
        """Decided is handled elsewhere, and showing it twice would mislead.

        An accepted reading became a rule and reaches the reader through
        `catalogue`, where it can be revised. A rejected one was found
        inconclusive, and another reading of the same evidence is what D-036
        expects next — not something to warn about.
        """
        accepted = record(workspace, a_reading(name="accepted-one"))
        rejected = record(workspace, a_reading(name="rejected-one"))
        review = Review(workspace)
        review.accept(accepted, decided_by="emmanuel")
        review.reject(rejected, decided_by="emmanuel")

        assert pending_readings(workspace, REFERENCE) == ()

    def test_the_queue_is_scoped_to_the_ticket(self, workspace) -> None:
        """Another ticket's queue is not this reading's problem."""
        TicketStore(workspace).add("999")
        mine = record(workspace, a_reading())
        other_run = open_run(workspace, "999", "submit_reply")
        RuleProposals(workspace).record(
            other_run, a_reading(name="elsewhere"), provider="mcp", model=None
        )

        assert [p.proposal_id for p in pending_readings(workspace, REFERENCE)] == [mine]

    def test_the_exported_payload_carries_it(self, workspace) -> None:
        """The whole point: the reader cannot avoid a duplicate it cannot see."""
        record(workspace, a_reading())

        payload = payload_as_dict(export_payload(workspace, REFERENCE).payload)

        assert [p["name"] for p in payload["pending"]] == ["daily-limit"]

    def test_a_pending_proposal_is_not_offered_as_revisable(self, workspace) -> None:
        """`revises` names a rule. A pending proposal has no rule to revise.

        Asserted on the serialised payload because that is what a model reads:
        the key is `proposal_id`, not `rule_id`, so a reading cannot mistake it
        for something to put in `revises`.
        """
        record(workspace, a_reading())

        payload = payload_as_dict(export_payload(workspace, REFERENCE).payload)

        assert payload["catalogue"] == ()
        assert "proposal_id" in payload["pending"][0]
        assert "rule_id" not in payload["pending"][0]


# -- the submission reports the overlap ---------------------------------------


class TestSubmissionReportsPendingOverlap:
    def test_a_second_reading_of_the_same_anchor_is_reported(self, workspace) -> None:
        """The exact failure from 615: two proposals, one rule, no warning."""
        first = record(workspace, a_reading())

        result = submit_reply(
            workspace,
            REFERENCE,
            '{"rules": [{"name": "daily-limit", "statement": "A transfer over '
            'the daily limit is refused.", "behaviours": ["Refuse it"], '
            '"anchors": [{"path_glob": "rules.py", "repository_alias": "billing"}]}]}',
            provider="mcp",
        )

        assert result.stored_count == 1
        second = result.stored[0]
        assert result.pending_candidates == {second: (first,)}
        assert result.possible_pending_duplicates == 1

    def test_the_duplicate_is_still_stored(self, workspace) -> None:
        """Reported, not refused. Convergence is evidence, not an error."""
        record(workspace, a_reading())

        result = submit_reply(
            workspace,
            REFERENCE,
            '{"rules": [{"name": "daily-limit", "statement": "A transfer over '
            'the daily limit is refused.", "behaviours": ["Refuse it"], '
            '"anchors": [{"path_glob": "rules.py", "repository_alias": "billing"}]}]}',
            provider="mcp",
        )

        assert result.stored_count == 1
        assert result.rejections == ()
        assert len(RuleProposals(workspace).undecided(REFERENCE)) == 2

    def test_a_proposal_does_not_overlap_itself(self, workspace) -> None:
        """A reading is recorded before its candidates are looked up.

        Without the exclusion every single submission would report itself as
        its own duplicate, which is worse than the bug it replaces: a warning
        that always fires is a warning nobody reads.
        """
        result = submit_reply(
            workspace,
            REFERENCE,
            '{"rules": [{"name": "daily-limit", "statement": "A transfer over '
            'the daily limit is refused.", "behaviours": ["Refuse it"], '
            '"anchors": [{"path_glob": "rules.py", "repository_alias": "billing"}]}]}',
            provider="mcp",
        )

        assert result.pending_candidates == {}

    def test_a_decided_proposal_is_not_reported_as_pending(self, workspace) -> None:
        first = record(workspace, a_reading())
        Review(workspace).reject(first, decided_by="emmanuel")

        result = submit_reply(
            workspace,
            REFERENCE,
            '{"rules": [{"name": "daily-limit", "statement": "A transfer over '
            'the daily limit is refused.", "behaviours": ["Refuse it"], '
            '"anchors": [{"path_glob": "rules.py", "repository_alias": "billing"}]}]}',
            provider="mcp",
        )

        assert result.pending_candidates == {}

    def test_catalogue_overlap_and_queue_overlap_stay_apart(self, workspace) -> None:
        """Both numbers are ids; only the field says which table they index.

        A reviewer told "overlaps 1" cannot act without knowing whether 1 is a
        rule to revise or a proposal to collapse. Merging the two dictionaries
        would make that undecidable.
        """
        accepted = record(workspace, a_reading(name="in-the-catalogue"))
        rule_id = Review(workspace).accept(accepted, decided_by="emmanuel").rule_id
        queued = record(workspace, a_reading(name="in-the-queue"))

        result = submit_reply(
            workspace,
            REFERENCE,
            '{"rules": [{"name": "daily-limit", "statement": "A transfer over '
            'the daily limit is refused.", "behaviours": ["Refuse it"], '
            '"anchors": [{"path_glob": "rules.py", "repository_alias": "billing"}]}]}',
            provider="mcp",
        )
        new = result.stored[0]

        assert result.candidates == {new: (rule_id,)}
        assert result.pending_candidates == {new: (queued,)}

    def test_a_different_anchor_is_not_a_duplicate(self, workspace) -> None:
        """Overlap is by path. A reading about elsewhere is not a duplicate.

        The queued proposal is anchored by a glob that matches the evidence
        without being the same string, so the two differ in anchor alone —
        everything else about the submission is identical to the duplicate
        test above.
        """
        record(workspace, a_reading(glob="*.py"))

        result = submit_reply(
            workspace,
            REFERENCE,
            '{"rules": [{"name": "daily-limit", "statement": "A transfer over '
            'the daily limit is refused.", "behaviours": ["Refuse it"], '
            '"anchors": [{"path_glob": "rules.py", "repository_alias": "billing"}]}]}',
            provider="mcp",
        )

        assert result.stored_count == 1
        assert result.pending_candidates == {}


# -- the guidance tells the reader what to do with it -------------------------


class TestGuidance:
    def test_both_paths_carry_the_same_instruction(self) -> None:
        """A rule proposed over MCP and by a provider must mean the same thing."""
        import asyncio

        from constat.ai.guidance import PENDING, for_system_prompt
        from constat.mcp import build_server

        assert PENDING in for_system_prompt()

        got = asyncio.run(
            build_server("/tmp").get_prompt("document", {"reference": REFERENCE})
        )
        assert PENDING in got.messages[0].content.text

    def test_it_does_not_offer_revises_for_a_pending_proposal(self) -> None:
        """The instruction has to say why `revises` is not the answer here.

        Without that a reader shown a pending duplicate will reach for the
        only collapse mechanism it knows, and `revises` on a proposal id would
        either fail or, worse, name an unrelated rule that happens to share
        the number.
        """
        from constat.ai.guidance import PENDING

        assert "`revises` cannot be used" in PENDING
