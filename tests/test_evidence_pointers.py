"""A rule records the evidence it was accepted on (CON-79, D-073).

Found by re-reading 615 after it landed. The chain
`rule_version -> rule_proposal -> run -> operation` ended at a summary line
reading `pending: 1 commit(s)`; no table in the workspace held a commit SHA;
and once the ticket landed the document regenerated with no diffs at all. Both
rules in the live catalogue were accepted on evidence the workspace could no
longer produce, which is product rule 2 failing for every rule as soon as its
ticket ships.

The headline test is `test_the_pointer_survives_the_ticket_landing`. Everything
else is detail around it.

**A pointer, not a copy.** The payload is deliberately not stored: a copy in
the governance store becomes a second source of truth that can disagree with
git, and grows without bound. The cost of that choice is that a SHA can dangle
— a squash-merge or force-push destroys the commit — which is why the subject
is stored beside it, so a broken pointer still says what it pointed at.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constat.operations import (
    collect,
    evidence_for_proposal,
    evidence_for_run,
    evidence_for_version,
    gather,
    open_run,
    record_run_evidence,
    submit_reply,
)
from constat.store import Registry, Review, RuleProposals, TicketStore, Workspace
from constat.tickets import TicketStatus
from helpers import commit_file, git


REFERENCE = "615"
ANCHOR = "render.ts"


def _reply(path: str = ANCHOR) -> str:
    return json.dumps(
        {
            "rules": [
                {
                    "name": "no-advertising-on-content-pages",
                    "statement": "Content pages carry no third-party advertising.",
                    "behaviours": ["A content page serves no ad"],
                    "anchors": [{"path_glob": path, "repository_alias": "web"}],
                    "area": "advertising",
                }
            ]
        }
    )


@pytest.fixture
def workspace(tmp_path: Path):
    """A clone whose ticket-615 branch is not yet in mainline."""
    bare = tmp_path / "web.git"
    bare.mkdir()
    git(bare, "init", "--bare", "--quiet", "--initial-branch=main")
    clone = tmp_path / "web"
    git(tmp_path, "clone", "--quiet", str(bare), "web")
    git(clone, "config", "user.name", "Test Fixture")
    git(clone, "config", "user.email", "fixture@example.invalid")
    commit_file(clone, ANCHOR, "ads on\n", "Initial render")
    git(clone, "push", "--quiet", "origin", "main")

    git(clone, "checkout", "--quiet", "-b", "feat/615-no-ads")
    commit_file(clone, ANCHOR, "ads off\n", "Stop loading ads on content pages (615)")
    git(clone, "push", "--quiet", "origin", "feat/615-no-ads")
    git(clone, "checkout", "--quiet", "main")

    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(str(clone), alias="web", default_branch="main")
        TicketStore(ws).add(REFERENCE)
        yield ws, clone, bare


# -- what a run writes down ---------------------------------------------------


class TestRecordingTheEvidence:
    def test_a_submission_records_the_commit_it_read(self, workspace) -> None:
        ws, clone, _bare = workspace

        result = submit_reply(ws, REFERENCE, _reply(), provider="mcp")
        commits = evidence_for_proposal(ws, result.stored[0])

        assert len(commits) == 1
        assert commits[0].sha == git(clone, "rev-parse", "feat/615-no-ads")
        assert commits[0].subject == "Stop loading ads on content pages (615)"
        assert commits[0].repository_alias == "web"

    def test_a_gather_records_it_too(self, workspace) -> None:
        """Both run kinds, because either can be the run a reading points at."""
        ws, clone, _bare = workspace

        result = gather(ws, REFERENCE)

        assert result.run_id is not None
        commits = evidence_for_run(ws, result.run_id)
        assert [c.sha for c in commits] == [git(clone, "rev-parse", "feat/615-no-ads")]

    def test_the_repository_identity_is_the_root_commit(self, workspace) -> None:
        """Not a path and not an alias (D-025), so the pointer survives the
        repository being moved, renamed or re-cloned."""
        ws, clone, _bare = workspace
        result = gather(ws, REFERENCE)

        commits = evidence_for_run(ws, result.run_id)
        roots = git(clone, "rev-list", "--max-parents=0", "HEAD").split()

        assert commits[0].repository_identity in roots

    def test_a_run_that_read_nothing_records_nothing(self, workspace) -> None:
        """An empty pointer set is the honest record of a landed ticket, not a
        gap to be filled."""
        ws, _clone, _bare = workspace
        TicketStore(ws).add("999")

        run_id = open_run(ws, "999", "submit_reply")
        written = record_run_evidence(ws, run_id, collect(ws, "999"))

        assert written == 0
        assert evidence_for_run(ws, run_id) == ()

    def test_the_subject_is_scrubbed(self, workspace) -> None:
        """Identity in a store is a disclosure waiting to happen. Over-masking
        a pointer costs nothing — the SHA is what resolves it."""
        ws, clone, _bare = workspace
        git(clone, "checkout", "--quiet", "feat/615-no-ads")
        commit_file(
            clone, "other.ts", "x\n", "Fix reported by someone@example.com (615)"
        )
        git(clone, "push", "--quiet", "origin", "feat/615-no-ads")
        git(clone, "checkout", "--quiet", "main")

        result = gather(ws, REFERENCE)
        subjects = [c.subject for c in evidence_for_run(ws, result.run_id)]

        assert any("[redacted]" in s for s in subjects)
        assert not any("someone@example.com" in s for s in subjects)

    def test_it_is_a_pointer_and_not_a_copy(self, workspace) -> None:
        """No diff, no payload, no file contents in the governance store."""
        ws, _clone, _bare = workspace
        gather(ws, REFERENCE)

        columns = {row[1] for row in ws.execute("PRAGMA table_info(run_commit)")}

        assert "sha" in columns and "subject" in columns
        assert not columns & {"diff", "payload", "content", "body"}


# -- the failure this ticket exists for ---------------------------------------


class TestItSurvives:
    def test_the_pointer_survives_the_ticket_landing(self, workspace) -> None:
        """The headline. Both live rules were accepted on evidence that had
        become unproducible, because the pointer was never written down.

        Accept while the work is pending, then land it. The ticket then
        contributes no evidence at all — and the accepted version must still
        name the commit it rests on.
        """
        ws, clone, _bare = workspace
        result = submit_reply(ws, REFERENCE, _reply(), provider="mcp")
        accepted = Review(ws).accept(result.stored[0], decided_by="emmanuel")
        sha = git(clone, "rev-parse", "feat/615-no-ads")

        git(clone, "merge", "--quiet", "--no-ff", "-m", "Merge 615", "feat/615-no-ads")
        git(clone, "push", "--quiet", "origin", "main")
        git(clone, "fetch", "--quiet", "origin")

        # The precondition: there is no evidence to gather any more.
        assert all(not f.commits for f in collect(ws, REFERENCE))
        assert collect(ws, REFERENCE)[0].status is TicketStatus.LANDED

        commits = evidence_for_version(ws, accepted.rule_version_id)
        assert [c.sha for c in commits] == [sha]
        assert commits[0].subject == "Stop loading ads on content pages (615)"

    def test_the_pointer_survives_the_repository_disappearing(
        self, workspace
    ) -> None:
        """The record is Constat's, not git's. A repository that has moved
        leaves the claim checkable in principle — by its root commit — rather
        than erasing it."""
        ws, clone, _bare = workspace
        result = submit_reply(ws, REFERENCE, _reply(), provider="mcp")
        accepted = Review(ws).accept(result.stored[0], decided_by="emmanuel")

        clone.rename(clone.parent / "moved-away")

        commits = evidence_for_version(ws, accepted.rule_version_id)
        assert len(commits) == 1
        assert commits[0].repository_identity is not None

    def test_a_dangling_sha_still_says_what_it_pointed_at(self, workspace) -> None:
        """A squash-merge or force-push destroys the commit. The subject is
        stored so the gap is visible rather than blank."""
        ws, clone, _bare = workspace
        result = submit_reply(ws, REFERENCE, _reply(), provider="mcp")
        accepted = Review(ws).accept(result.stored[0], decided_by="emmanuel")

        # The branch is deleted and the commit is unreachable: a squash-merge
        # workflow in one line.
        git(clone, "branch", "-D", "feat/615-no-ads")
        git(clone, "push", "--quiet", "origin", "--delete", "feat/615-no-ads")

        commits = evidence_for_version(ws, accepted.rule_version_id)
        assert commits[0].subject == "Stop loading ads on content pages (615)"


# -- what a reviewer is shown -------------------------------------------------


class TestReporting:
    def test_rule_history_names_the_commits(self, workspace, capsys) -> None:
        from constat.cli import main

        ws, clone, _bare = workspace
        result = submit_reply(ws, REFERENCE, _reply(), provider="mcp")
        accepted = Review(ws).accept(result.stored[0], decided_by="emmanuel")

        capsys.readouterr()
        main(["--workspace", str(clone.parent / "ws"), "rule", "history",
              str(accepted.rule_id)])
        out = capsys.readouterr().out

        assert "read from 1 commit(s)" in out
        assert git(clone, "rev-parse", "feat/615-no-ads")[:12] in out

    def test_a_version_with_no_pointer_says_so(self, workspace, capsys) -> None:
        """A rule accepted before schema 13 has no evidence pointer, and
        nothing is back-filled: the evidence those runs read is gone, and
        inventing a SHA would be the worst possible lie in a governance
        record."""
        from constat.cli import main

        ws, clone, _bare = workspace
        result = submit_reply(ws, REFERENCE, _reply(), provider="mcp")
        accepted = Review(ws).accept(result.stored[0], decided_by="emmanuel")
        ws.execute("DELETE FROM run_commit")

        capsys.readouterr()
        main(["--workspace", str(clone.parent / "ws"), "rule", "history",
              str(accepted.rule_id)])

        assert "evidence: not recorded" in capsys.readouterr().out

    def test_the_queue_says_when_a_run_gathered_nothing(
        self, workspace, capsys
    ) -> None:
        """What made this ticket visible: a reading whose run read nothing
        rests on evidence the workspace cannot show."""
        from constat.cli import main

        ws, clone, _bare = workspace
        git(clone, "merge", "--quiet", "--no-ff", "-m", "Merge 615", "feat/615-no-ads")
        git(clone, "push", "--quiet", "origin", "main")
        git(clone, "fetch", "--quiet", "origin")
        # Grounded in mainline now (D-072), so the submission still lands.
        submit_reply(ws, REFERENCE, _reply(), provider="mcp")

        capsys.readouterr()
        main(["--workspace", str(clone.parent / "ws"), "rule", "proposals", REFERENCE])

        assert "read from no commits — this run gathered none" in capsys.readouterr().out
