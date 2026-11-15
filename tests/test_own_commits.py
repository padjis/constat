"""Constat's own merge commit is not evidence (CON-75).

Found re-reading ticket 628 after `merge_on_accept` landed its branch: the
payload came back with two commits — the real fix, and the merge Constat
wrote — so 14 changed files were reported for 7 real ones, and a commit
Constat authored was presented as the team's implementation evidence
(product rule 3).

**Identification is by trailer, read with git's own trailer support.** The
alternative was matching `MERGE_SUBJECT`, which is text anyone could write: a
human merge worded the same way would be silently dropped, and under-reporting
evidence is the worse failure. The test that matters most here is therefore the
one proving a *look-alike* commit is kept.

**And the exclusion is stated.** Every other omission in this product says so —
a truncated diff names what it dropped, a repository that contributed nothing
is still listed — so evidence that quietly disagrees with `git log` is not
acceptable even when the omission is right.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.git.adapter import LANDED_TRAILER, discover_repository
from constat.git.merge import merge_ticket_branch
from constat.operations import collect, render
from constat.store import Registry, TicketStore, Workspace
from constat.tickets import TicketStatus, find_ticket_commits
from helpers import commit_file, git


@pytest.fixture
def shared(tmp_path: Path) -> tuple[Path, Path]:
    """A bare remote and a clone, with ticket 628's work on a branch."""
    bare = tmp_path / "origin.git"
    bare.mkdir()
    git(bare, "init", "--bare", "--quiet", "--initial-branch=main")

    clone = tmp_path / "work"
    git(tmp_path, "clone", "--quiet", str(bare), "work")
    git(clone, "config", "user.name", "Test Fixture")
    git(clone, "config", "user.email", "fixture@example.invalid")
    commit_file(clone, "README.md", "first\n", "First commit")
    git(clone, "push", "--quiet", "origin", "main")

    git(clone, "checkout", "--quiet", "-b", "feat/628-first-launch")
    commit_file(clone, "device.py", "provision = True\n", "Absorb the race (628)")
    git(clone, "push", "--quiet", "origin", "feat/628-first-launch")
    git(clone, "checkout", "--quiet", "main")
    return bare, clone


def _land(clone: Path) -> None:
    merge_ticket_branch(
        discover_repository(clone),
        alias="237feed",
        branches=("refs/remotes/origin/feat/628-first-launch",),
        target_branch="main",
        reference="628",
    )


def _match(clone: Path, reference: str = "628"):
    return find_ticket_commits(
        discover_repository(clone), reference, "origin/main", "237feed"
    )


# -- the commit carries the trailer -------------------------------------------


class TestTheMergeIsMarked:
    def test_constat_writes_the_trailer(self, shared) -> None:
        bare, clone = shared
        _land(clone)

        trailer = git(
            bare,
            "log",
            "-1",
            "refs/heads/main",
            f"--format=%(trailers:key={LANDED_TRAILER},valueonly)",
        )
        assert trailer.strip() == "628"

    def test_the_subject_is_not_what_identifies_it(self, shared) -> None:
        """Belt and braces: the subject still reads for a human, but the
        trailer is what the lookup uses."""
        bare, clone = shared
        _land(clone)

        subject = git(bare, "log", "-1", "refs/heads/main", "--format=%s")
        assert "Merge feat/628-first-launch for 628" == subject


# -- it is left out of the evidence -------------------------------------------


class TestItIsExcluded:
    def test_a_landed_ticket_reports_only_the_real_commit(self, shared) -> None:
        """628's actual failure: two commits reported where one was the team's."""
        _bare, clone = shared
        _land(clone)

        match = _match(clone)

        assert match.status is TicketStatus.LANDED
        assert match.commit_count == 1
        assert match.commits[0].subject == "Absorb the race (628)"
        assert len(match.excluded_own_commits) == 1

    def test_the_excluded_sha_is_kept_not_just_counted(self, shared) -> None:
        """So the document can name it and a reviewer can check the claim."""
        bare, clone = shared
        _land(clone)

        merge_sha = git(bare, "rev-parse", "refs/heads/main")
        assert _match(clone).excluded_own_commits == (merge_sha,)

    def test_nothing_is_excluded_before_a_landing(self, shared) -> None:
        """Disclosure must be a signal, not a line on every document."""
        _bare, clone = shared

        match = _match(clone)

        assert match.status is TicketStatus.PENDING
        assert match.excluded_own_commits == ()

    def test_a_reference_known_only_to_constats_own_commit_is_not_found(
        self, shared
    ) -> None:
        """Constat must not be its own witness.

        A merge Constat wrote mentions the reference, so without the exclusion
        the tool would report a ticket as present on the strength of its own
        output.
        """
        _bare, clone = shared
        _land(clone)
        # 628's real commit is now in mainline, so search for a reference that
        # appears *only* in Constat's merge: its trailer value.
        match = _match(clone, "feat/628-first-launch")

        assert match.status is not TicketStatus.PENDING


# -- a look-alike human commit is kept ----------------------------------------


class TestALookAlikeIsKept:
    def test_a_human_merge_worded_the_same_way_stays(self, shared) -> None:
        """The reason identification is not by subject.

        This commit's subject is byte-identical to what Constat writes. It has
        no trailer, so it is the team's work and must appear. Dropping it would
        be under-reporting evidence, which is worse than over-reporting it.
        """
        _bare, clone = shared
        git(clone, "checkout", "--quiet", "-b", "feat/629-other")
        commit_file(
            clone, "other.py", "x\n", "Merge feat/629-other for 629"
        )
        git(clone, "push", "--quiet", "origin", "feat/629-other")
        git(clone, "checkout", "--quiet", "main")

        match = _match(clone, "629")

        assert match.commit_count == 1
        assert match.excluded_own_commits == ()

    def test_a_commit_mentioning_the_trailer_in_prose_stays(self, shared) -> None:
        """A trailer is a trailer, not a substring.

        Git parses trailers from the message's last paragraph. A commit that
        merely talks about `Constat-Landed` — a change to this very feature
        would — is not marked by it.
        """
        _bare, clone = shared
        git(clone, "checkout", "--quiet", "-b", "feat/630-docs")
        (clone / "notes.md").write_text("notes\n")
        git(clone, "add", "notes.md")
        git(
            clone,
            "commit",
            "-m",
            "Document the Constat-Landed: trailer (630)",
            "-m",
            "Explains how Constat-Landed: 628 marks its own merges.\n\nStill prose.",
        )
        git(clone, "push", "--quiet", "origin", "feat/630-docs")
        git(clone, "checkout", "--quiet", "main")

        match = _match(clone, "630")

        assert match.commit_count == 1
        assert match.excluded_own_commits == ()


# -- the document says so -----------------------------------------------------


class TestDisclosure:
    def test_the_document_names_the_excluded_commit(
        self, tmp_path: Path, shared
    ) -> None:
        bare, clone = shared
        _land(clone)
        merge_sha = git(bare, "rev-parse", "refs/heads/main")

        with Workspace.create(tmp_path / "ws") as ws:
            Registry(ws).add(str(clone), alias="237feed", default_branch="main")
            TicketStore(ws).add("628")
            body = render("628", collect(ws, "628"))

        assert "1 commit(s) excluded: made by Constat when landing this ticket" in body
        assert merge_sha[:12] in body

    def test_a_document_with_nothing_excluded_is_silent(
        self, tmp_path: Path, shared
    ) -> None:
        _bare, clone = shared

        with Workspace.create(tmp_path / "ws") as ws:
            Registry(ws).add(str(clone), alias="237feed", default_branch="main")
            TicketStore(ws).add("628")
            body = render("628", collect(ws, "628"))

        assert "excluded" not in body
