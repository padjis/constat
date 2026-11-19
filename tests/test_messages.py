"""A user-facing message is a catalogue entry a rule refers to (CON-82, D-082).

A message is the **most checkable thing a rule can carry**. A business reader
may be unsure whether a limit is really enforced; they are never unsure whether
the screen says what the catalogue claims it says. That is the whole value, and
everything here protects it.

Four properties carry these tests:

1. **Verbatim.** The code-leakage gate (D-066) deliberately does not apply: a
   message is a *quotation*, and real user-facing text contains file names,
   error codes and product names. Refusing those would leave a reader with a
   sanitised approximation, which is worse than nothing because it still looks
   like evidence.
2. **Stored once.** One message belongs to several rules, and a second copy is
   how two wordings come to disagree. Matching is on exact text.
3. **Cited, in the scheme D-081 settled.** `M-7`, flat, never reused.
4. **Minted at acceptance, never at submission.** A reading proposes text; a
   message enters the catalogue only when a human accepts the rule that shows
   it (D-048).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constat.ai.guidance import MESSAGES, for_baseline, for_system_prompt
from constat.ai.parsing import MAX_MESSAGE, parse
from constat.ai.statements import code_leakage
from constat.ai.redaction import (
    CommitContext,
    FileChange,
    ProviderPayload,
    RepositoryContext,
)
from constat.models import Anchor, Message, RuleProposal
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
REFUSAL = "Failed to start upload"


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
                        files=(FileChange(path="rules.py", change_type="modified", diff="d"),),
                    ),
                ),
            ),
        ),
    )


def _reply(messages=None, name: str = "daily-limit") -> str:
    rule = {
        "name": name,
        "statement": "A transfer above the daily limit is refused.",
        "anchors": [{"path_glob": "rules.py", "repository_alias": "billing"}],
    }
    if messages is not None:
        rule["messages"] = messages
    return json.dumps({"rules": [rule]})


def _accept(workspace, messages: tuple[str, ...], name: str = "daily-limit") -> int:
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    proposal_id = RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name=name,
            statement="A transfer above the daily limit is refused.",
            messages=tuple(Message(text=m) for m in messages),
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            area="payments",
        ),
        provider="mcp",
    )
    return Review(workspace).accept(proposal_id, decided_by="a person").rule_id


# -- verbatim -----------------------------------------------------------------


class TestAMessageIsAQuotation:
    def test_a_message_is_parsed(self) -> None:
        result = parse(_reply([REFUSAL]), _payload())

        assert result.rejections == ()
        assert [m.text for m in result.proposals[0].messages] == [REFUSAL]

    @pytest.mark.parametrize(
        "text",
        [
            "No ExcelMappingType was found in the workbook",
            "Could not read render.ts",
            "HTTP 503: the service is unavailable",
            "Check the value of billing_account_id and try again",
            "POST failed: please try again",
        ],
    )
    def test_the_code_leakage_gate_does_not_apply(self, text) -> None:
        """The property this ticket most depends on.

        **Every one of these trips `code_leakage`** — asserted below, not
        assumed — and every one is a real thing a product says to a user.
        Refusing them would leave a reviewer with a tidied approximation, which
        is worse than nothing because it still looks like evidence. D-066
        protects sentences *Constat* writes; this is a sentence the product
        writes itself.

        The first version of this test used four plausible-looking messages of
        which only one tripped the gate, so a mutation applying `code_leakage`
        to messages failed a single case. The assertion below is why that
        cannot happen again: a text that stops tripping the gate fails here
        rather than quietly weakening the exemption it is meant to pin.
        """
        assert code_leakage(text) is not None

        result = parse(_reply([text]), _payload())

        assert result.rejections == ()
        assert result.proposals[0].messages[0].text == text

    def test_the_statement_gate_still_applies(self) -> None:
        """The exemption is for the message field only. A statement naming a
        file is still refused, or the gate would be hollow."""
        reply = json.dumps(
            {
                "rules": [
                    {
                        "name": "daily-limit",
                        "statement": "A transfer is refused by limits.py.",
                        "messages": [REFUSAL],
                        "anchors": [
                            {"path_glob": "rules.py", "repository_alias": "billing"}
                        ],
                    }
                ]
            }
        )

        result = parse(reply, _payload())

        assert result.proposals == ()
        assert "D-066" in result.rejections[0].reason

    def test_whitespace_is_trimmed_but_inner_text_is_untouched(self) -> None:
        result = parse(_reply(["  Transfer declined — daily limit reached  "]), _payload())

        assert (
            result.proposals[0].messages[0].text
            == "Transfer declined — daily limit reached"
        )


class TestRefusals:
    def test_an_empty_message_is_refused(self) -> None:
        result = parse(_reply(["   "]), _payload())

        assert result.proposals == ()
        assert "empty" in result.rejections[0].reason

    def test_a_non_string_message_is_refused(self) -> None:
        result = parse(_reply([{"text": REFUSAL}]), _payload())

        assert result.proposals == ()
        assert "not a string" in result.rejections[0].reason

    def test_an_over_long_message_is_refused(self) -> None:
        result = parse(_reply(["x" * (MAX_MESSAGE + 1)]), _payload())

        assert result.proposals == ()
        assert str(MAX_MESSAGE) in result.rejections[0].reason

    def test_a_repeated_message_is_refused(self) -> None:
        result = parse(_reply([REFUSAL, REFUSAL]), _payload())

        assert result.proposals == ()
        assert "repeats" in result.rejections[0].reason

    def test_messages_are_optional(self) -> None:
        """Most rules show the user nothing."""
        result = parse(_reply(), _payload())

        assert result.rejections == ()
        assert result.proposals[0].messages == ()

    def test_a_bad_message_rejects_the_whole_reading(self) -> None:
        result = parse(_reply([REFUSAL, "   "]), _payload())

        assert result.proposals == ()
        assert len(result.rejections) == 1


# -- stored once, cited -------------------------------------------------------


class TestAMessageLivesOnce:
    def test_accepting_mints_a_citation(self, workspace) -> None:
        _accept(workspace, (REFUSAL,))

        rule = Catalogue(workspace).find("daily-limit")
        assert [m.ref for m in rule.messages] == ["M-1"]
        assert rule.messages[0].text == REFUSAL

    def test_the_same_text_under_two_rules_is_one_message(self, workspace) -> None:
        """The reason a message is global rather than owned by a rule: the
        same refusal covers a size limit and a format check, and two copies are
        how two wordings come to disagree."""
        _accept(workspace, (REFUSAL,), name="daily-limit")
        _accept(workspace, (REFUSAL,), name="monthly-limit")

        rows = workspace.execute("SELECT ref, text FROM message").fetchall()
        assert len(rows) == 1
        assert rows[0]["ref"] == "M-1"

        both = {
            rule.name: [m.ref for m in rule.messages]
            for rule in Catalogue(workspace).list()
        }
        assert both == {"daily-limit": ["M-1"], "monthly-limit": ["M-1"]}

    def test_different_text_gets_its_own_citation(self, workspace) -> None:
        _accept(workspace, (REFUSAL, "Transfer declined"))

        refs = [m.ref for m in Catalogue(workspace).find("daily-limit").messages]
        assert refs == ["M-1", "M-2"]

    def test_a_near_match_is_a_different_message(self, workspace) -> None:
        """Exact text, because that is what a message *is*. Treating a
        near-match as the same one would be a judgement no gate here is
        entitled to make — and it would silently rewrite what a user sees."""
        _accept(workspace, (REFUSAL,), name="daily-limit")
        _accept(workspace, (REFUSAL + ".",), name="monthly-limit")

        assert len(workspace.execute("SELECT id FROM message").fetchall()) == 2

    def test_a_citation_is_not_reused(self, workspace) -> None:
        _accept(workspace, (REFUSAL,), name="daily-limit")
        workspace.execute(
            "INSERT INTO message (ref, text, created_at) "
            "VALUES ('M-9', 'An imported message.', '2026-01-01T00:00:00Z')"
        )

        _accept(workspace, ("A brand new message",), name="monthly-limit")

        refs = {
            row["ref"] for row in workspace.execute("SELECT ref FROM message").fetchall()
        }
        assert refs == {"M-1", "M-9", "M-10"}


class TestNothingIsMintedBeforeAcceptance:
    def test_submitting_creates_no_message(self, workspace) -> None:
        """A message enters the catalogue only through a human decision
        (D-048), like everything else in it."""
        run_id = open_run(workspace, REFERENCE, "submit_reply")
        RuleProposals(workspace).record(
            run_id,
            RuleProposal(
                name="daily-limit",
                statement="A transfer above the daily limit is refused.",
                messages=(Message(text=REFUSAL),),
                anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            ),
            provider="mcp",
        )

        assert workspace.execute("SELECT id FROM message").fetchall() == []

    def test_a_pending_reading_carries_the_text_with_no_citation(
        self, workspace
    ) -> None:
        run_id = open_run(workspace, REFERENCE, "submit_reply")
        proposal_id = RuleProposals(workspace).record(
            run_id,
            RuleProposal(
                name="daily-limit",
                statement="A transfer above the daily limit is refused.",
                messages=(Message(text=REFUSAL),),
                anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            ),
            provider="mcp",
        )

        stored = next(
            p
            for p in RuleProposals(workspace).for_ticket(REFERENCE)
            if p.id == proposal_id
        )
        assert stored.proposal.messages[0].text == REFUSAL
        assert stored.proposal.messages[0].ref is None


# -- frozen and rendered ------------------------------------------------------


class TestVersionsAndRendering:
    def test_a_version_records_the_messages_it_was_accepted_with(
        self, workspace
    ) -> None:
        rule_id = _accept(workspace, (REFUSAL,))

        version = Review(workspace).versions(rule_id)[0]

        assert [m.ref for m in version["messages"]] == ["M-1"]

    def test_the_product_state_shows_the_message(self, workspace) -> None:
        _accept(workspace, (REFUSAL,))

        rendered = render_state(product_state(workspace))

        assert "`M-1`" in rendered
        assert REFUSAL in rendered

    def test_rule_show_quotes_it(self, workspace, capsys) -> None:
        from constat.cli import main

        _accept(workspace, (REFUSAL,))
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

        out = capsys.readouterr().out
        assert f'M-1  "{REFUSAL}"' in out


class TestGuidance:
    def test_every_prompt_path_carries_the_same_block(self) -> None:
        """A rule proposed over MCP, by a provider, or from a baseline goes in
        one catalogue and must mean the same thing (D-045, CON-66)."""
        import constat.mcp as mcp

        assert MESSAGES in for_system_prompt()
        assert MESSAGES in for_baseline("advertising")
        assert mcp.MESSAGES is MESSAGES

    def test_it_asks_for_the_text_verbatim(self) -> None:
        assert "quote it **exactly**" in MESSAGES
        assert "approximation is worse than nothing" in MESSAGES


class TestMigrationFromSchema17:
    def _at_schema_17(self, home: Path, tmp_path: Path) -> None:
        with Workspace.create(home) as ws:
            Registry(ws).add(
                str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")),
                alias="billing",
            )
            TicketStore(ws).add(REFERENCE)
            _accept(ws, (REFUSAL,))

        rewind_workspace(home / "workspace.db", 17)

    def test_it_migrates_on_open(self, tmp_path: Path) -> None:
        self._at_schema_17(tmp_path / "ws", tmp_path)

        with Workspace.open(tmp_path / "ws") as ws:
            assert ws.schema_version == SCHEMA_VERSION
            assert ws.execute("SELECT COUNT(*) AS n FROM message").fetchone()["n"] == 0

    def test_an_older_rule_has_no_messages_rather_than_mined_ones(
        self, tmp_path: Path
    ) -> None:
        """Nothing is back-filled, and nothing could be: no reading before this
        could propose a message, and mining quoted strings out of existing
        statements would be Constat inventing the evidence a reviewer is meant
        to check — D-046's failure, performed by a migration."""
        self._at_schema_17(tmp_path / "ws", tmp_path)

        with Workspace.open(tmp_path / "ws") as ws:
            assert Catalogue(ws).find("daily-limit").messages == ()
