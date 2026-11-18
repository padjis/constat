"""A rule carries worked examples (CON-80).

A statement can be read and agreed with without the reader learning anything.
An example can be *disagreed with* — "no, the limit is 100" — and that
correction is what a review is for. Examples are the business half of product
rule 8 expressed as data, which is why they are stored, frozen and rendered
rather than left in the prose of a statement.

Four properties carry these tests:

1. **Both halves or nothing.** A situation with no outcome is a case nobody
   answered; an outcome with no situation has nothing to check it against.
   Either one alone renders as a blank table cell, which reads as Constat
   having dropped something.
2. **A bad example rejects the whole reading, never itself.** Silently
   dropping one example from three means the stored reading says something the
   reader did not — `parsing.py` exists to refuse exactly that, and the rule
   applies one level down.
3. **Frozen on the version.** What a reviewer checked is part of what they
   accepted. Reading the live `example` table for a historical version would
   give version 1 the examples of version 3, which is CON-61's bug.
4. **Nothing here judges whether an outcome is right.** That is the reviewer's
   entire job. The tests below assert that a plausible-but-wrong example is
   stored, so this file can never be read as a correctness guarantee.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from constat.ai import as_dict as payload_as_dict
from constat.ai.guidance import EXAMPLES, for_system_prompt
from constat.ai.parsing import MAX_EXAMPLE, parse
from constat.ai.redaction import (
    CommitContext,
    FileChange,
    ProviderPayload,
    RepositoryContext,
)
from constat.ai.statements import restates
from constat.models import Anchor, Behaviour, Example, RuleProposal
from constat.operations import example_table, export_payload, known_rules, open_run
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
        "statement": STATEMENT,
        "anchors": [{"path_glob": "rules.py", "repository_alias": "billing"}],
    }
    rule.update(overrides)
    return json.dumps({"rules": [rule]})


def _two_examples() -> list[dict]:
    return [
        {"situation": "A transfer of 240 euros", "outcome": "Accepted"},
        {
            "situation": "A transfer of 260 euros",
            "outcome": "Refused, and the daily limit is shown",
        },
    ]


def _record(
    workspace, examples: tuple[Example, ...], revises: int | None = None
) -> int:
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    return RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name="daily-limit",
            statement=STATEMENT,
            behaviours=(Behaviour(description="Refuse it"),),
            examples=examples,
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            area="payments",
            relation="revises" if revises else "establishes",
            revises_rule_id=revises,
        ),
        provider="mcp",
        model="claude-opus-5",
        revises_rule_id=revises,
    )


# -- parsing ------------------------------------------------------------------


class TestParsingExamples:
    def test_examples_are_parsed_in_order(self) -> None:
        result = parse(_reply(examples=_two_examples()), _payload())

        assert result.rejections == ()
        examples = result.proposals[0].examples
        assert [e.situation for e in examples] == [
            "A transfer of 240 euros",
            "A transfer of 260 euros",
        ]
        assert examples[0].outcome == "Accepted"

    def test_order_is_preserved_rather_than_sorted(self) -> None:
        """The sequence a reading chose carries meaning: accepted, then the
        boundary, then the refusal. Sorting would scramble the argument."""
        examples = [
            {"situation": "Z — a transfer of 10 euros", "outcome": "Accepted"},
            {"situation": "A — a transfer of 10000 euros", "outcome": "Refused"},
        ]
        result = parse(_reply(examples=examples), _payload())

        assert [e.situation[0] for e in result.proposals[0].examples] == ["Z", "A"]

    def test_no_examples_is_accepted(self) -> None:
        """Optional, like an area. A reading that offers none is weaker, not
        invalid, and refusing it would discard a rule a human might accept."""
        result = parse(_reply(), _payload())

        assert result.rejections == ()
        assert result.proposals[0].examples == ()

    def test_an_empty_list_is_accepted_as_none(self) -> None:
        result = parse(_reply(examples=[]), _payload())

        assert result.rejections == ()
        assert result.proposals[0].examples == ()


class TestRefusals:
    def test_a_situation_with_no_outcome_is_refused(self) -> None:
        result = parse(
            _reply(examples=[{"situation": "A transfer of 260 euros"}]), _payload()
        )

        assert result.proposals == ()
        assert "no outcome" in result.rejections[0].reason

    def test_an_outcome_with_no_situation_is_refused(self) -> None:
        result = parse(_reply(examples=[{"outcome": "Refused"}]), _payload())

        assert result.proposals == ()
        assert "no situation" in result.rejections[0].reason

    def test_a_bad_example_rejects_the_whole_reading(self) -> None:
        """The property that matters most here.

        Two good examples and one broken one must not produce a stored reading
        with two examples: that reading would claim something the reader did
        not say, which is the failure `parsing.py` exists to prevent."""
        result = parse(
            _reply(examples=_two_examples() + [{"situation": "incomplete"}]),
            _payload(),
        )

        assert result.proposals == ()
        assert len(result.rejections) == 1
        assert "example 3" in result.rejections[0].reason

    def test_the_rejection_names_which_example_failed(self) -> None:
        result = parse(
            _reply(examples=[{"situation": "ok", "outcome": "ok"}, {"bad": True}]),
            _payload(),
        )

        assert "example 2" in result.rejections[0].reason

    def test_an_example_leaking_code_is_refused(self) -> None:
        """D-066 applies to every half of a rule a person reads. A clean
        statement whose examples name files is still a technical record."""
        result = parse(
            _reply(
                examples=[
                    {
                        "situation": "A transfer of 260 euros",
                        "outcome": "Refused by limits.py",
                    }
                ]
            ),
            _payload(),
        )

        assert result.proposals == ()
        assert "outcome" in result.rejections[0].reason
        assert "D-066" in result.rejections[0].reason

    def test_an_over_long_example_is_refused(self) -> None:
        result = parse(
            _reply(
                examples=[
                    {"situation": "x" * (MAX_EXAMPLE + 1), "outcome": "Refused"}
                ]
            ),
            _payload(),
        )

        assert result.proposals == ()
        assert str(MAX_EXAMPLE) in result.rejections[0].reason

    def test_a_repeated_situation_is_refused(self) -> None:
        result = parse(
            _reply(
                examples=[
                    {"situation": "A transfer of 260 euros", "outcome": "Refused"},
                    {"situation": "a transfer of 260 EUROS", "outcome": "Accepted"},
                ]
            ),
            _payload(),
        )

        assert result.proposals == ()
        assert "repeats" in result.rejections[0].reason

    def test_examples_that_are_not_a_list_are_refused(self) -> None:
        result = parse(_reply(examples="a transfer of 260 euros"), _payload())

        assert result.proposals == ()
        assert "not a list" in result.rejections[0].reason


class TestRestatement:
    def test_an_example_restating_the_statement_is_refused(self) -> None:
        result = parse(
            _reply(
                examples=[
                    {
                        "situation": "A transfer above the daily limit",
                        "outcome": "It is refused",
                    }
                ]
            ),
            _payload(),
        )

        assert result.proposals == ()
        assert "restates" in result.rejections[0].reason

    def test_a_specific_case_of_the_statement_is_kept(self) -> None:
        """The direction that matters more than the refusal.

        A real example shares most of the statement's vocabulary by
        construction — it is a case *of* it. The quantity is what makes it
        checkable, and a detector that refused this would have broken the
        feature in order to protect it."""
        result = parse(
            _reply(
                examples=[
                    {
                        "situation": "A transfer of 260 euros against a 250 limit",
                        "outcome": "Refused, and the limit is shown",
                    }
                ]
            ),
            _payload(),
        )

        assert result.rejections == ()
        assert len(result.proposals[0].examples) == 1

    @pytest.mark.parametrize(
        "situation,outcome",
        [
            ("A transfer of 10 euros", "Accepted"),
            ("A second transfer the same day", "Refused"),
            ("A refund of 400 euros", "Accepted, refunds are not limited"),
        ],
    )
    def test_short_concrete_examples_survive(self, situation, outcome) -> None:
        assert not restates(f"{situation} {outcome}", STATEMENT)

    def test_the_detector_errs_toward_allowing(self) -> None:
        """Stated as a limit, not a guarantee. A near-restatement with one
        extra clause passes, exactly as `code_leakage` lets a subtly
        non-business sentence through: a false refusal cannot be argued with."""
        assert not restates(
            "A transfer above the daily limit is refused on a weekday", STATEMENT
        )


class TestWhatIsNotChecked:
    def test_a_wrong_outcome_is_stored(self) -> None:
        """Deliberate, and the reason this file cannot be read as a quality
        guarantee. Deciding whether 260 against a 250 limit is really refused
        is the reviewer's entire job; a gate that guessed would manufacture
        the certainty product rule 1 forbids."""
        result = parse(
            _reply(
                examples=[
                    {
                        "situation": "A transfer of 10 euros",
                        "outcome": "Refused, which is not what the code does",
                    }
                ]
            ),
            _payload(),
        )

        assert result.rejections == ()
        assert result.proposals[0].examples[0].outcome.startswith("Refused")


# -- storage ------------------------------------------------------------------


class TestStorage:
    def test_examples_survive_being_read_back(self, workspace) -> None:
        proposal_id = _record(
            workspace,
            (
                Example(situation="A transfer of 240 euros", outcome="Accepted"),
                Example(situation="A transfer of 260 euros", outcome="Refused"),
            ),
        )

        stored = next(
            p
            for p in RuleProposals(workspace).for_ticket(REFERENCE)
            if p.id == proposal_id
        )

        assert [e.situation for e in stored.proposal.examples] == [
            "A transfer of 240 euros",
            "A transfer of 260 euros",
        ]

    def test_acceptance_carries_examples_onto_the_rule(self, workspace) -> None:
        proposal_id = _record(
            workspace,
            (Example(situation="A transfer of 260 euros", outcome="Refused"),),
        )

        Review(workspace).accept(proposal_id, decided_by="a person")

        rule = Catalogue(workspace).find("daily-limit")
        assert len(rule.examples) == 1
        assert rule.examples[0].outcome == "Refused"

    def test_an_earlier_version_keeps_its_own_examples(self, workspace) -> None:
        """The CON-61 property, applied to examples.

        If this fails because `version_examples` reads the live `example`
        table, every historical version displays the newest one's cases — and
        it would look entirely right."""
        review = Review(workspace)
        first = _record(
            workspace,
            (Example(situation="A transfer of 260 euros", outcome="Refused"),),
        )
        rule_id = review.accept(first, decided_by="a person").rule_id

        second = _record(
            workspace,
            (Example(situation="A transfer of 600 euros", outcome="Refused"),),
            revises=rule_id,
        )
        review.accept(second, decided_by="a person")

        v1, v2 = review.versions(rule_id)

        assert [e.situation for e in v1["examples"]] == ["A transfer of 260 euros"]
        assert [e.situation for e in v2["examples"]] == ["A transfer of 600 euros"]

class TestMigrationFromSchema13:
    def _at_schema_13(self, home: Path) -> None:
        """A real workspace wound back by dropping schema 14's tables.

        Built forwards and reversed rather than hand-written, for the reason
        every migration fixture here gives: hand-written DDL tests the
        transcription instead of the migration.
        """
        with Workspace.create(home) as ws:
            Registry(ws).add(
                str(distinct_subject(home.parent, "billing", "LIMIT = 250\n")),
                alias="billing",
            )
            TicketStore(ws).add(REFERENCE)
            proposal_id = _record(
                ws, (Example(situation="A transfer of 260 euros", outcome="Refused"),)
            )
            Review(ws).accept(proposal_id, decided_by="emmanuel")

        rewind_workspace(home / "workspace.db", 13)

    def test_the_tables_are_gone_before_the_migration(self, tmp_path: Path) -> None:
        self._at_schema_13(tmp_path / "ws")

        connection = sqlite3.connect(tmp_path / "ws" / "workspace.db")
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        finally:
            connection.close()

        assert "example" not in tables

    def test_it_migrates_on_open(self, tmp_path: Path) -> None:
        self._at_schema_13(tmp_path / "ws")

        with Workspace.open(tmp_path / "ws") as ws:
            assert ws.schema_version == SCHEMA_VERSION
            for table in (
                "example",
                "rule_proposal_example",
                "rule_version_example",
            ):
                ws.execute(f"SELECT COUNT(*) FROM {table}").fetchone()

    def test_an_older_rule_has_no_examples_rather_than_invented_ones(
        self, tmp_path: Path
    ) -> None:
        """Nothing is back-filled, and here that is not even a choice: no
        reading before schema 14 could propose an example, and deriving one
        from a statement would be Constat inventing the evidence a reviewer is
        meant to check — D-046's failure, committed by a migration."""
        self._at_schema_13(tmp_path / "ws")

        with Workspace.open(tmp_path / "ws") as ws:
            rule = Catalogue(ws).find("daily-limit")

        assert rule.examples == ()


# -- the revision hazard ------------------------------------------------------


class TestRevisionsSeeTheExamples:
    def test_the_payload_shows_an_accepted_rule_its_examples(self, workspace) -> None:
        """Accepting a revision rewrites the examples from the reading, so a
        reading that cannot see them cannot carry them forward — and the
        deletion of a case a human accepted would be invisible."""
        proposal_id = _record(
            workspace,
            (Example(situation="A transfer of 260 euros", outcome="Refused"),),
        )
        Review(workspace).accept(proposal_id, decided_by="a person")

        rules = known_rules(workspace)

        assert rules[0].examples == (("A transfer of 260 euros", "Refused"),)

    def test_the_examples_reach_the_exported_payload(self, workspace) -> None:
        proposal_id = _record(
            workspace,
            (Example(situation="A transfer of 260 euros", outcome="Refused"),),
        )
        Review(workspace).accept(proposal_id, decided_by="a person")

        as_dict = payload_as_dict(export_payload(workspace, REFERENCE).payload)

        assert as_dict["catalogue"][0]["examples"] == (
            ("A transfer of 260 euros", "Refused"),
        )


# -- rendering ----------------------------------------------------------------


class TestRendering:
    def test_examples_render_as_a_table(self) -> None:
        lines = example_table(
            (Example(situation="A transfer of 260 euros", outcome="Refused"),)
        )

        assert "| Situation | Outcome |" in lines
        assert "| A transfer of 260 euros | Refused |" in lines

    def test_no_examples_renders_nothing(self) -> None:
        """Not an empty table with a "none" row: the callers say what an
        absence means, and they do not all mean the same thing."""
        assert example_table(()) == []

    def test_a_pipe_is_escaped_rather_than_breaking_the_row(self) -> None:
        """Otherwise the rest of the sentence moves into a column that does
        not exist, and the page reads as though Constat dropped half of it."""
        lines = example_table(
            (Example(situation="A transfer of 10 | 20 euros", outcome="Refused"),)
        )

        row = [line for line in lines if "transfer" in line][0]
        # Two cells, not three: the escaped pipe stays inside the situation.
        assert len(row.split(" | ")) == 2
        assert "10 \\| 20" in row


class TestGuidance:
    def test_both_prompt_paths_carry_the_same_examples_guidance(self) -> None:
        """A rule proposed over MCP and the same rule proposed by a provider
        must mean the same thing, or the catalogue records which path happened
        to be configured. Asserted on the shared constant and on both
        importers, so improving one prompt alone fails here."""
        import constat.mcp as mcp  # noqa: PLC0415

        assert EXAMPLES in for_system_prompt()
        assert "situation" in for_system_prompt()
        assert mcp.EXAMPLES is EXAMPLES

    def test_the_guidance_says_a_revision_replaces_the_examples(self) -> None:
        prompt = for_system_prompt()

        assert "replaces the rule's examples" in prompt

    def test_the_guidance_never_instructs_acceptance(self) -> None:
        prompt = for_system_prompt().lower()

        assert "accept the rule" not in prompt
        assert "nothing you propose is accepted" in prompt
