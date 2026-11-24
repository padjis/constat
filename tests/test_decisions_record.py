"""Recording decisions a reviewer wrote in the published target (CON-58, D-106).

The other half of D-105. Reading was implemented there and recorded nothing,
because D-089 said the amendment to D-055 had to land with the mechanism that
enforces it. This is that mechanism, so these tests are as much about what it
refuses as about what it records.

**The boundary D-055 was protecting is not the channel.** It is that a *model*
must not accept. Every decision recorded here exists because a person committed
a line to a repository, and `TestTheBoundaryThatSurvives` holds the MCP surface
to the same absence it always had.

The properties:

1. **An approval in the target becomes a recorded decision**, with the channel
   and what attested to it.
2. **Identity comes from the commit**, never from the file's text, and a line
   nothing can attribute is refused rather than credited to whoever ran the
   command.
3. **Reading twice records once**, enforced by the database rather than by this
   code remembering to look.
4. **A verdict rewritten in a new commit is reported, not applied.** A recorded
   decision is append-only.
5. **One bad line never swallows a good one**, and every refusal is reported
   with what to do about it — silence would leave a reviewer believing their
   decision had landed.

Every test runs against a bare repository on disk, like D-105's: nothing in the
path knows what a host is.
"""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

import pytest

from constat.cli import EXIT_DECISIONS, EXIT_OK, EXIT_USAGE, main
from constat.operations import open_run, record_read_decisions
from constat.publish.decisions import file_for
from constat.publish import Awaiting
from constat.publish.targets.git_pages import GitPages
from constat.store import Catalogue, Review, RuleProposals, TicketStore, Workspace

from test_acceptance import a_reading, record, register

REFERENCE = "622"
PAGE = "622.md"


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    """A bare repository standing in for any git documentation target."""
    bare = tmp_path / "wiki.git"
    bare.mkdir()
    subprocess.run(
        ["git", "init", "--bare", "--quiet", "--initial-branch=main", str(bare)],
        check=True,
        capture_output=True,
    )
    return bare


@pytest.fixture
def published(wiki: Path) -> GitPages:
    """The target, with the page published once so the decision file exists."""
    target = GitPages(str(wiki))
    target.publish(REFERENCE, f"# Document for {REFERENCE}\n\n- [ ] `#1` a rule\n")
    return target


@pytest.fixture
def workspace(tmp_path: Path):
    """A workspace with a registered repository and ticket 622 open."""
    with Workspace.create(tmp_path / "ws") as ws:
        register(ws, tmp_path)
        yield ws


def a_proposal(workspace, name: str = "daily-limit") -> int:
    return record(workspace, a_reading(name=name))


def decide_in_target(
    tmp_path: Path,
    wiki: Path,
    lines: str,
    *,
    sign: bool = False,
    replace: bool = False,
    who: str = "A Business Reviewer",
) -> str:
    """A reviewer clones, writes decisions and pushes. Returns the commit sha.

    A browser edit on any forge produces the same commit, which is why nothing
    here needs a forge. `replace` rewrites the decisions region instead of
    appending, which is what changing one's mind looks like in a file.
    """
    clone = tmp_path / f"review-{abs(hash((lines, replace, who))) % 100000}"
    subprocess.run(
        ["git", "clone", "--quiet", str(wiki), str(clone)],
        check=True,
        capture_output=True,
    )
    git(clone, "config", "user.name", who)
    git(clone, "config", "user.email", "biz@example.invalid")

    if sign:
        key = tmp_path / "signer"
        if not key.exists():
            subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-N", "", "-q", "-f", str(key)],
                check=True,
                capture_output=True,
            )
        git(clone, "config", "gpg.format", "ssh")
        git(clone, "config", "user.signingkey", str(key) + ".pub")

    file = clone / file_for(PAGE)
    text = file.read_text()
    if replace:
        head, marker, _ = text.partition("## Decisions")
        text = head + marker + "\n\n"
    file.write_text(text + lines)
    git(clone, "add", "-A")
    git(clone, "commit", "--quiet", *(["-S"] if sign else []), "-m", "decide")
    git(clone, "push", "--quiet", "origin", "HEAD")
    return git(clone, "rev-parse", "HEAD")


def decisions_of(workspace, proposal_id: int) -> list[dict]:
    return [
        dict(row)
        for row in workspace.execute(
            "SELECT decision, decided_by, attribution, channel, verification, "
            "       source_commit, source_line, rationale "
            "FROM rule_proposal_decision WHERE rule_proposal_id = ? ORDER BY id",
            (proposal_id,),
        )
    ]


# -- recording ----------------------------------------------------------------


class TestAnApprovalIsRecorded:
    def test_it_becomes_an_accepted_rule_in_the_catalogue(
        self, tmp_path, wiki, published, workspace
    ):
        """The amendment to D-055, in one test: nobody typed `rule accept`."""
        proposal_id = a_proposal(workspace)
        decide_in_target(tmp_path, wiki, f"{proposal_id}: approved\n")

        result = record_read_decisions(workspace, REFERENCE, published)

        assert [o.outcome for o in result.outcomes] == ["accepted"]
        assert [r.name for r in Catalogue(workspace).list()] == ["daily-limit"]
        assert RuleProposals(workspace).find(proposal_id).decision == "accepted"

    def test_the_record_says_where_it_was_decided_and_what_attested_to_it(
        self, tmp_path, wiki, published, workspace
    ):
        proposal_id = a_proposal(workspace)
        sha = decide_in_target(tmp_path, wiki, f"{proposal_id}: approved\n")

        record_read_decisions(workspace, REFERENCE, published)

        (stored,) = decisions_of(workspace, proposal_id)
        assert stored["channel"] == "git_pages"
        assert stored["verification"] == "git_commit"
        assert stored["attribution"] == "commit"
        assert stored["source_commit"] == sha
        assert stored["source_line"] is not None

    def test_the_decider_is_the_commit_author_and_not_a_name_in_the_file(
        self, tmp_path, wiki, published, workspace
    ):
        """The template says *do not write your name*, and this is why: a typed
        name is no better than the CLI's unchecked `--by` (D-061). A name
        written anyway is prose, and the commit author is what is recorded."""
        proposal_id = a_proposal(workspace)
        decide_in_target(
            tmp_path,
            wiki,
            f"Signed off by Someone Else\n{proposal_id}: approved\n",
        )

        record_read_decisions(workspace, REFERENCE, published)

        (stored,) = decisions_of(workspace, proposal_id)
        assert stored["decided_by"] == "A Business Reviewer"
        assert "Someone Else" not in str(stored["decided_by"])

    def test_every_display_site_says_the_decision_came_from_the_target(
        self, tmp_path, wiki, published, workspace
    ):
        """One property rather than a string built per site: a decision nobody
        typed at the command line must not render like one that was."""
        proposal_id = a_proposal(workspace)
        decide_in_target(tmp_path, wiki, f"{proposal_id}: approved\n")

        record_read_decisions(workspace, REFERENCE, published)

        described = RuleProposals(workspace).find(proposal_id).decided_by_description
        assert "A Business Reviewer" in described
        assert "documentation target" in described
        assert "git_commit" in described

    def test_a_signed_commit_records_the_state_git_could_actually_check(
        self, tmp_path, wiki, published, workspace
    ):
        """D-105's finding, carried into the record. The signature verifies on
        the signer's machine and reads as unverifiable through a clone Constat
        made, so `signed_unverified` is what is stored — rounding it up would
        claim a check nobody performed."""
        proposal_id = a_proposal(workspace)
        decide_in_target(tmp_path, wiki, f"{proposal_id}: approved\n", sign=True)

        record_read_decisions(workspace, REFERENCE, published)

        (stored,) = decisions_of(workspace, proposal_id)
        assert stored["verification"] == "signed_unverified"


class TestARejectionIsRecorded:
    def test_it_is_recorded_with_the_reviewer_s_reason(
        self, tmp_path, wiki, published, workspace
    ):
        proposal_id = a_proposal(workspace)
        decide_in_target(
            tmp_path,
            wiki,
            f"{proposal_id}: rejected — the limit is per account, not per customer\n",
        )

        result = record_read_decisions(workspace, REFERENCE, published)

        assert [o.outcome for o in result.outcomes] == ["rejected"]
        (stored,) = decisions_of(workspace, proposal_id)
        assert stored["rationale"] == "the limit is per account, not per customer"

    def test_the_catalogue_is_unchanged_because_rejection_means_inconclusive(
        self, tmp_path, wiki, published, workspace
    ):
        """D-036: a rejection does not say the rule is wrong, so there is
        nothing to unwind and nothing to add."""
        proposal_id = a_proposal(workspace)
        decide_in_target(tmp_path, wiki, f"{proposal_id}: rejected\n")

        record_read_decisions(workspace, REFERENCE, published)

        assert Catalogue(workspace).list() == ()
        assert RuleProposals(workspace).find(proposal_id).decision == "rejected"


# -- reading twice -------------------------------------------------------------


class TestItIsIdempotent:
    def test_reading_the_same_target_twice_records_once(
        self, tmp_path, wiki, published, workspace
    ):
        proposal_id = a_proposal(workspace)
        decide_in_target(tmp_path, wiki, f"{proposal_id}: approved\n")

        first = record_read_decisions(workspace, REFERENCE, published)
        second = record_read_decisions(workspace, REFERENCE, published)

        assert [o.outcome for o in first.outcomes] == ["accepted"]
        assert [o.outcome for o in second.outcomes] == ["already"]
        assert len(decisions_of(workspace, proposal_id)) == 1

    def test_a_second_pass_does_not_baseline_a_second_version(
        self, tmp_path, wiki, published, workspace
    ):
        """The consequence that would hurt: a duplicate decision would freeze a
        second identical version of the rule and make `rule history` report a
        revision nobody made."""
        proposal_id = a_proposal(workspace)
        decide_in_target(tmp_path, wiki, f"{proposal_id}: approved\n")

        record_read_decisions(workspace, REFERENCE, published)
        record_read_decisions(workspace, REFERENCE, published)

        assert len(Catalogue(workspace).list()) == 1
        frozen = workspace.execute(
            "SELECT COUNT(*) AS n FROM rule_version"
        ).fetchone()["n"]
        assert frozen == 1

    def test_a_second_pass_reports_what_already_stood(
        self, tmp_path, wiki, published, workspace
    ):
        proposal_id = a_proposal(workspace)
        decide_in_target(tmp_path, wiki, f"{proposal_id}: approved\n")

        record_read_decisions(workspace, REFERENCE, published)
        (outcome,) = record_read_decisions(workspace, REFERENCE, published).outcomes

        assert "accepted" in outcome.detail
        assert "same commit" in outcome.detail

    def test_the_database_refuses_a_duplicate_even_when_nothing_looks_first(
        self, tmp_path, wiki, published, workspace
    ):
        """Idempotence is a constraint, not a check this code remembers to
        make. A future caller that skips the lookup still cannot write twice."""
        proposal_id = a_proposal(workspace)
        proposals = RuleProposals(workspace)
        proposals.decide(
            proposal_id,
            "accepted",
            "A Business Reviewer",
            channel="git_pages",
            source_commit="abc123",
        )

        with pytest.raises(sqlite3.IntegrityError):
            proposals.decide(
                proposal_id,
                "rejected",
                "A Business Reviewer",
                channel="git_pages",
                source_commit="abc123",
            )

    def test_two_command_line_decisions_are_still_allowed(self, workspace):
        """The constraint must not reach the CLI channel. A null source commit
        is distinct from another null in SQLite, which is what keeps changing
        one's mind at the command line possible (D-061)."""
        proposal_id = a_proposal(workspace)
        proposals = RuleProposals(workspace)

        proposals.decide(proposal_id, "rejected", "A Reviewer")
        proposals.decide(proposal_id, "accepted", "A Reviewer")

        assert len(decisions_of(workspace, proposal_id)) == 2


class TestChangingAVerdictLater:
    def test_a_new_commit_with_a_different_verdict_is_reported_not_applied(
        self, tmp_path, wiki, published, workspace
    ):
        """A recorded decision is append-only. Overturning one is `rule
        retire`'s job — a second quiet write would rewrite the record a
        reviewer was shown."""
        proposal_id = a_proposal(workspace)
        decide_in_target(tmp_path, wiki, f"{proposal_id}: approved\n")
        record_read_decisions(workspace, REFERENCE, published)

        decide_in_target(
            tmp_path, wiki, f"{proposal_id}: rejected\n", replace=True
        )
        result = record_read_decisions(workspace, REFERENCE, published)

        assert [o.outcome for o in result.outcomes] == ["refused"]
        assert "already accepted" in result.outcomes[0].detail
        assert RuleProposals(workspace).find(proposal_id).decision == "accepted"
        assert len(decisions_of(workspace, proposal_id)) == 1


# -- what it refuses -----------------------------------------------------------


class TestWhatItRefuses:
    def test_a_rule_citation_is_not_a_rule_proposal(
        self, tmp_path, wiki, published, workspace
    ):
        """`R-7` names a rule in the catalogue; a decision is taken on the
        proposal that would become a version of it. Recording one would have to
        guess which pending reading was meant."""
        a_proposal(workspace)
        decide_in_target(tmp_path, wiki, "R-7: approved\n")

        result = record_read_decisions(workspace, REFERENCE, published)

        assert [o.outcome for o in result.outcomes] == ["refused"]
        assert "rule citation" in result.outcomes[0].detail
        assert Catalogue(workspace).list() == ()

    def test_an_unknown_proposal_id_is_refused(
        self, tmp_path, wiki, published, workspace
    ):
        a_proposal(workspace)
        decide_in_target(tmp_path, wiki, "4321: approved\n")

        result = record_read_decisions(workspace, REFERENCE, published)

        assert [o.outcome for o in result.outcomes] == ["refused"]
        assert "no rule proposal 4321" in result.outcomes[0].detail

    def test_a_proposal_from_another_ticket_is_refused(
        self, tmp_path, wiki, published, workspace
    ):
        """The decision file is per ticket. A line naming another ticket's
        proposal means somebody is looking at the wrong page, and recording it
        would decide something nobody was reading."""
        TicketStore(workspace).add("623")
        other_run = open_run(workspace, "623", "submit_reply")
        elsewhere = RuleProposals(workspace).record(
            other_run, a_reading(name="other-rule"), provider="claude"
        )
        decide_in_target(tmp_path, wiki, f"{elsewhere}: approved\n")

        result = record_read_decisions(workspace, REFERENCE, published)

        assert [o.outcome for o in result.outcomes] == ["refused"]
        assert "belongs to ticket 623" in result.outcomes[0].detail
        assert RuleProposals(workspace).find(elsewhere).decision is None

    def test_one_proposal_decided_twice_in_one_file_refuses_both(
        self, tmp_path, wiki, published, workspace
    ):
        """Two verdicts for one proposal is an ambiguity, and taking whichever
        came first would choose for the reviewer (product rule 1)."""
        proposal_id = a_proposal(workspace)
        decide_in_target(
            tmp_path,
            wiki,
            f"{proposal_id}: approved\n{proposal_id}: rejected\n",
        )

        result = record_read_decisions(workspace, REFERENCE, published)

        assert [o.outcome for o in result.outcomes] == ["refused", "refused"]
        assert "more than once" in result.outcomes[0].detail
        assert RuleProposals(workspace).find(proposal_id).decision is None

    def test_a_proposal_already_decided_at_the_command_line_is_refused(
        self, tmp_path, wiki, published, workspace
    ):
        proposal_id = a_proposal(workspace)
        Review(workspace).accept(proposal_id, decided_by="Someone At A Terminal")
        decide_in_target(tmp_path, wiki, f"{proposal_id}: rejected\n")

        result = record_read_decisions(workspace, REFERENCE, published)

        assert [o.outcome for o in result.outcomes] == ["refused"]
        assert "already accepted" in result.outcomes[0].detail
        assert "Someone At A Terminal" in result.outcomes[0].detail

    def test_a_bad_line_does_not_swallow_a_good_one(
        self, tmp_path, wiki, published, workspace
    ):
        """Stopping at the first refusal would make one typo discard decisions
        that were perfectly readable."""
        first = a_proposal(workspace, name="first-rule")
        second = a_proposal(workspace, name="second-rule")
        decide_in_target(
            tmp_path,
            wiki,
            f"R-7: approved\n{first}: approved\n9999: rejected\n{second}: rejected\n",
        )

        result = record_read_decisions(workspace, REFERENCE, published)

        assert [o.outcome for o in result.outcomes] == [
            "refused",
            "accepted",
            "refused",
            "rejected",
        ]
        assert [r.name for r in Catalogue(workspace).list()] == ["first-rule"]

    def test_an_unreadable_line_leaves_the_pass_incomplete(
        self, tmp_path, wiki, published, workspace
    ):
        """Even with every readable line recorded. Somebody wrote `1: aproved`
        meaning to decide, and Constat holds no decision for it — reporting
        success would leave them believing it had landed (D-041)."""
        proposal_id = a_proposal(workspace)
        decide_in_target(
            tmp_path, wiki, f"{proposal_id}: approved\n7: aproved\n"
        )

        result = record_read_decisions(workspace, REFERENCE, published)

        assert [o.outcome for o in result.outcomes] == ["accepted"]
        assert result.read.unreadable
        assert result.unrecorded

    def test_a_file_nobody_has_written_in_records_nothing(
        self, published, workspace
    ):
        a_proposal(workspace)

        result = record_read_decisions(workspace, REFERENCE, published)

        assert result.outcomes == ()
        assert result.read.present
        assert not result.unrecorded


# -- the schema -----------------------------------------------------------------


class TestTheMigration:
    """Schema 23 on a workspace that already holds decisions.

    `tests/test_releases.py` compares a migrated workspace's *shape* against a
    fresh one, which catches a column added in one place and not the other.
    These are about the rows: an existing decision has to keep meaning what it
    meant, and the migrated table has to actually work.
    """

    def _rewound(self, tmp_path: Path) -> Path:
        from helpers import rewind_workspace

        home = tmp_path / "old"
        with Workspace.create(home) as ws:
            register(ws, tmp_path)
            proposal_id = record(ws, a_reading())
            Review(ws).accept(proposal_id, decided_by="Someone", attribution="stated")
        rewind_workspace(home / "workspace.db", 22)
        return home

    def test_a_decision_taken_before_this_version_reads_as_the_cli_channel(
        self, tmp_path: Path
    ):
        """A back-fill of fact, not of guesswork. Until schema 23 there was one
        way to decide and `--by` was never checked by anything, so `cli` /
        `asserted` restates what the row already meant."""
        home = self._rewound(tmp_path)

        with Workspace.open(home) as ws:
            (stored,) = decisions_of(ws, 1)

        assert stored["channel"] == "cli"
        assert stored["verification"] == "asserted"
        assert stored["attribution"] == "stated"
        assert stored["source_commit"] is None

    def test_the_uniqueness_survives_the_migration(self, tmp_path: Path):
        """The migration has to produce a working constraint, not just the
        columns. `ALTER TABLE` cannot add a unique constraint inline, so this
        is the half a migration is most likely to leave out."""
        home = self._rewound(tmp_path)

        with Workspace.open(home) as ws:
            second = record(ws, a_reading(name="another-rule"))
            proposals = RuleProposals(ws)
            proposals.decide(
                second,
                "accepted",
                "A Business Reviewer",
                channel="git_pages",
                source_commit="abc123",
            )

            with pytest.raises(sqlite3.IntegrityError):
                proposals.decide(
                    second,
                    "rejected",
                    "A Business Reviewer",
                    channel="git_pages",
                    source_commit="abc123",
                )

    def test_recording_from_a_target_works_on_a_migrated_workspace(
        self, tmp_path, wiki, published
    ):
        home = self._rewound(tmp_path)
        with Workspace.open(home) as ws:
            second = record(ws, a_reading(name="another-rule"))
        decide_in_target(tmp_path, wiki, f"{second}: approved\n")

        with Workspace.open(home) as ws:
            result = record_read_decisions(ws, REFERENCE, published)

            assert [o.outcome for o in result.outcomes] == ["accepted"]
            assert RuleProposals(ws).find(second).decided_channel == "git_pages"


# -- the boundary D-055 was protecting ----------------------------------------


class TestTheBoundaryThatSurvives:
    def test_no_tool_on_the_mcp_surface_can_accept_or_reject(self, tmp_path):
        """D-055 amended, not weakened. The objection was never the channel —
        it was that a model must not accept (D-089). An approval committed by a
        person is a human decision that happened elsewhere; a tool call is not,
        whatever it is named."""
        pytest.importorskip("mcp")
        from constat.mcp import build_server

        home = str(tmp_path / "ws")
        main(["--workspace", home, "init", "--reader", "mcp"])
        server = build_server(home)

        names = {tool.name for tool in server._tool_manager.list_tools()}
        assert not {n for n in names if "accept" in n or "reject" in n}

    def test_a_line_git_cannot_attribute_is_refused(
        self, tmp_path, wiki, published, workspace
    ):
        """No attested decider, no decision. Crediting an unattributable line
        to whoever ran the command would put the CLI's unchecked name on a
        channel whose whole claim is that it does better."""
        from dataclasses import replace as replace_field

        from constat.publish.decisions import DecisionLine, DecisionsRead

        proposal_id = a_proposal(workspace)
        line = DecisionLine(
            reference=str(proposal_id), verdict="approved", reason=None, line_no=1
        )

        class Uncommitted:
            def read_decisions(self, reference):
                return DecisionsRead(
                    reference=reference,
                    location="somewhere",
                    decisions=(replace_field(line, decided_by=None, commit=None),),
                )

        result = record_read_decisions(workspace, REFERENCE, Uncommitted())

        assert [o.outcome for o in result.outcomes] == ["refused"]
        assert "who wrote this line" in result.outcomes[0].detail
        assert RuleProposals(workspace).find(proposal_id).decision is None


# -- the command line ----------------------------------------------------------


class TestTheCommandLine:
    @pytest.fixture
    def home(self, tmp_path: Path) -> str:
        ws = str(tmp_path / "ws")
        main(["--workspace", ws, "init", "--reader", "mcp"])
        with Workspace.open(ws) as workspace:
            register(workspace, tmp_path)
            record(workspace, a_reading())
        return ws

    def _publish(self, home: str, wiki: Path, *flags: str) -> int:
        return main(
            [
                "--workspace",
                home,
                "review",
                REFERENCE,
                "--target",
                str(wiki),
                *flags,
            ]
        )

    def test_recording_from_the_target_exits_zero_and_says_what_it_did(
        self, tmp_path, wiki, published, home, capsys
    ):
        decide_in_target(tmp_path, wiki, "1: approved\n")

        code = self._publish(home, wiki, "--record-decisions")

        out = capsys.readouterr().out
        assert code == EXIT_OK
        assert "1 decision(s) recorded" in out
        assert "A Business Reviewer" in out
        with Workspace.open(home) as ws:
            assert RuleProposals(ws).find(1).decision == "accepted"

    def test_recording_refreshes_the_catalogue_page(
        self, tmp_path, wiki, published, home, capsys
    ):
        """CON-107. Recording accepts rules, so the catalogue changed.

        Leaving the record page stale would publish a catalogue that
        disagrees with the decisions just read from the target it was
        published to — the two pages contradicting each other on the same
        remote.
        """
        decide_in_target(tmp_path, wiki, "1: approved\n")

        self._publish(home, wiki, "--record-decisions")

        assert "catalogue:" in capsys.readouterr().out
        clone = tmp_path / "after-recording"
        git(tmp_path, "clone", "--quiet", str(wiki), str(clone))
        assert (clone / "status.md").exists()

    def test_a_refusal_exits_non_zero_so_a_script_cannot_miss_it(
        self, tmp_path, wiki, published, home, capsys
    ):
        decide_in_target(tmp_path, wiki, "R-7: approved\n")

        code = self._publish(home, wiki, "--record-decisions")

        assert code == EXIT_DECISIONS
        assert "could NOT be recorded" in capsys.readouterr().out

    def test_reading_still_records_nothing(
        self, tmp_path, wiki, published, home, capsys
    ):
        """The reporting path is what a reviewer uses to see what Constat read
        before anything acts on it, so it must stay inert."""
        decide_in_target(tmp_path, wiki, "1: approved\n")

        code = self._publish(home, wiki, "--read-decisions")

        assert code == EXIT_OK
        assert "Nothing here is recorded" in capsys.readouterr().out
        with Workspace.open(home) as ws:
            assert RuleProposals(ws).find(1).decision is None

    def test_asking_for_both_at_once_refuses(self, wiki, published, home, capsys):
        """One flag promises it records nothing and the other records. There is
        no sensible union, and one of the two guesses writes to the
        catalogue."""
        code = self._publish(home, wiki, "--read-decisions", "--record-decisions")

        assert code == EXIT_USAGE
        assert "Pick one" in capsys.readouterr().err

    def test_the_audit_view_says_the_decision_was_not_made_at_a_terminal(
        self, tmp_path, wiki, published, home, capsys
    ):
        """`rule history` is the audit view, and it is where rendering a
        committed decision like a typed `--by` string would hide exactly the
        difference the record exists to keep (product rule 3)."""
        decide_in_target(tmp_path, wiki, "1: approved\n")
        self._publish(home, wiki, "--record-decisions")
        capsys.readouterr()

        main(["--workspace", home, "rule", "history", "R-1"])

        out = capsys.readouterr().out
        assert "accepted by A Business Reviewer" in out
        assert "decided in the documentation target" in out
        assert "git_commit" in out

    def test_recording_twice_from_the_command_line_is_safe(
        self, tmp_path, wiki, published, home, capsys
    ):
        decide_in_target(tmp_path, wiki, "1: approved\n")
        self._publish(home, wiki, "--record-decisions")
        capsys.readouterr()

        code = self._publish(home, wiki, "--record-decisions")

        out = capsys.readouterr().out
        assert code == EXIT_OK
        assert "already recorded" in out
        assert "Reading a target twice is safe" in out


def _awaiting(id: str, previous: str | None = None) -> Awaiting:
    return Awaiting(
        id=id,
        name=f"rule-{id}",
        statement=f"A statement for {id}.",
        previous=previous,
    )


class TestPromptsInTheDecisionsFile:
    """One line per undecided proposal, appended and never altered (CON-115).

    The expectation this came from: *I would have expected to be able to
    approve every rule changed one by one.* The mechanism always allowed it —
    one id, one line — but nothing put the ids in front of the reviewer, who
    had to read them off the review page and retype them into another page.

    Seeding once cannot do it: the queue grows between rounds and D-105 says
    the file is never rewritten. Appending can, and keeps that promise — a
    line already in the file is never read, moved or altered.
    """

    def _file(self, tmp_path: Path, wiki: Path, name: str) -> str:
        clone = tmp_path / name
        git(tmp_path, "clone", "--quiet", str(wiki), str(clone))
        return (clone / "decisions" / f"{REFERENCE}.md").read_text()

    def test_an_undecided_proposal_is_prompted_for(self, tmp_path, wiki):
        target = GitPages(str(wiki))

        target.publish(
            REFERENCE, "# a page\n",
            awaiting=(_awaiting("1"), _awaiting("2")),
        )

        body = self._file(tmp_path, wiki, "prompted")
        assert "\n1: \n" in body
        assert "\n2: \n" in body

    def test_an_unanswered_prompt_is_not_a_refusal(self, tmp_path, wiki):
        """Or every proposal nobody had reached yet would come back as one."""
        target = GitPages(str(wiki))
        target.publish(
            REFERENCE, "# a page\n",
            awaiting=(_awaiting("1"), _awaiting("2")),
        )

        read = target.read_decisions(REFERENCE)

        assert read.decisions == ()
        assert read.unreadable == ()

    def test_a_reviewers_own_line_is_never_touched(self, tmp_path, wiki):
        """The promise D-105 made, kept while the file keeps changing."""
        target = GitPages(str(wiki))
        target.publish(REFERENCE, "# a page\n", awaiting=(_awaiting("1"),))
        decide_in_target(tmp_path, wiki, "1: approved — mine\n")

        target.publish(
            REFERENCE, "# a page, again\n",
            awaiting=(_awaiting("1"), _awaiting("2")),
        )

        body = self._file(tmp_path, wiki, "kept")
        assert "1: approved — mine" in body
        assert "\n2: \n" in body

    def test_an_answered_proposal_is_not_prompted_again(self, tmp_path, wiki):
        target = GitPages(str(wiki))
        target.publish(REFERENCE, "# a page\n", awaiting=(_awaiting("1"),))
        decide_in_target(tmp_path, wiki, "1: approved\n")

        target.publish(REFERENCE, "# a page\n", awaiting=(_awaiting("1"),))

        # A reviewer may fill the prompt in place or append their answer
        # below it. Either way the *prompt* is written once: what must not
        # happen is Constat adding another one on every publish.
        body = self._file(tmp_path, wiki, "once")
        assert body.count("\n1: \n") == 1

    def test_a_generated_page_is_prompted_for_nothing(self, tmp_path, wiki):
        """It has no proposals and no decisions file at all (D-117)."""
        target = GitPages(str(wiki))

        target.publish("index", "# index\n", awaiting=(_awaiting("1"),))

        clone = tmp_path / "generated"
        git(tmp_path, "clone", "--quiet", str(wiki), str(clone))
        assert not (clone / "decisions" / "index.md").exists()

    def test_the_prompt_says_what_is_being_decided(self, tmp_path, wiki):
        """The gap this closed: ids with no content. A reviewer read the
        statements on the review page and wrote verdicts in this one."""
        GitPages(str(wiki)).publish(
            REFERENCE, "# a page\n", awaiting=(_awaiting("7"),)
        )

        body = self._file(tmp_path, wiki, "context")
        assert "    #7 rule-7" in body
        assert "    NEW — A statement for 7." in body

    def test_a_revision_shows_both_statements(self, tmp_path, wiki):
        """"Is this a change, and is the change right" is the reviewer's whole
        question, and the new statement alone cannot answer it."""
        GitPages(str(wiki)).publish(
            REFERENCE, "# a page\n",
            awaiting=(_awaiting("7", previous="The old statement."),),
        )

        body = self._file(tmp_path, wiki, "revision")
        assert "    WAS — The old statement." in body
        assert "    NOW — A statement for 7." in body

    def test_the_context_is_never_read_as_a_verdict(self, tmp_path, wiki):
        """It is indented, which `parse` already skips — the mechanism that
        keeps the template's worked examples from arriving as decisions."""
        target = GitPages(str(wiki))
        target.publish(
            REFERENCE, "# a page\n",
            awaiting=(_awaiting("7", previous="The old statement."),),
        )

        read = target.read_decisions(REFERENCE)

        assert read.decisions == ()
        assert read.unreadable == ()
