"""A branch's commits are not all its ticket's (CON-121).

Branch-name attribution takes everything a named branch adds to mainline.
That is right when the branch was cut from mainline, and wrong the moment it
was cut from an integration branch: the branch then carries that branch's
unmerged work, and all of it is attributed to this ticket.

Found on the live repository. `feat/630-interest-filter-phase0` was branched
from a `develop` that already held 632's work, so `gather_evidence("630")`
returned five commits of which **four were 632's**. Rules written from that
payload would have been anchored to `DeleteScheduler.java` and presented as
what 630 changed — **wrong evidence**, which is worse than a wrong summary
and is what product rule 2 exists to prevent.

So where the branch says one thing and the commit says another, the commit
wins: a commit whose message names a different ticket is not attributed here
by branch name alone.

Three properties carry these tests:

1. **The exclusion fires on an inherited commit** and not on the ticket's own.
2. **It is narrow.** A message says "30 days" and "22,100 articles" far more
   often than it names a ticket, and a pattern that guessed there would drop
   real evidence.
3. **It is reported, never silent.** The rule is a heuristic — a commit of
   this ticket's own work that mentions another in passing is excluded too —
   and a gap a reader can see is a different thing from one they cannot.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.git.adapter import discover_repository
from constat.tickets import claims_another_ticket, find_ticket_commits

from helpers import commit_file, git


@pytest.fixture
def git_flow(tmp_path: Path) -> Path:
    """A branch cut from an integration branch that already holds other work.

    The shape that produced the defect: `develop` carries 632's merge, and
    630's branch is taken from it, so 630's branch "adds" 632's work to main.
    """
    repo = tmp_path / "subject"
    repo.mkdir()
    git(repo, "init", "--quiet", "--initial-branch=main")
    git(repo, "config", "user.name", "Test Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    commit_file(repo, "a.py", "x = 1\n", "Initial")

    # 632's work, merged onto develop.
    git(repo, "checkout", "--quiet", "-b", "feat/632-other-work")
    commit_file(repo, "other.py", "y = 2\n", "Do the other thing. Finishes #632")
    git(repo, "checkout", "--quiet", "-b", "develop", "main")
    git(repo, "merge", "--no-ff", "--quiet", "-m",
        "Merge feat/632-other-work for 632", "feat/632-other-work")

    # 630's branch, taken from develop, inheriting all of it.
    git(repo, "checkout", "--quiet", "-b", "feat/630-this-work")
    commit_file(repo, "this.py", "z = 3\n", "Do this thing. Phase 0 for #630")
    git(repo, "checkout", "--quiet", "main")
    return repo


class TestTheExclusion:
    def test_only_this_tickets_commits_are_attributed(self, git_flow) -> None:
        match = find_ticket_commits(
            discover_repository(str(git_flow)), "630", "main", "subject"
        )

        subjects = [c.subject for c in match.commits]
        assert subjects == ["Do this thing. Phase 0 for #630"]

    def test_the_inherited_work_is_reported(self, git_flow) -> None:
        """Named, because the rule that excluded them is a heuristic and a
        reader must be able to disagree with it."""
        match = find_ticket_commits(
            discover_repository(str(git_flow)), "630", "main", "subject"
        )

        # Both of 632's commits: the work and the merge that carried it.
        assert {other for _sha, _subject, other in match.claimed_by_another} == {
            "632"
        }
        assert len(match.claimed_by_another) == 2

    def test_the_other_ticket_still_gets_its_own(self, git_flow) -> None:
        """The exclusion must not make a commit unattributable to anyone."""
        match = find_ticket_commits(
            discover_repository(str(git_flow)), "632", "main", "subject"
        )

        assert any("632" in c.subject for c in match.commits)

    def test_a_commit_is_reported_once_per_sha(self, git_flow) -> None:
        """A ticket usually has a local and a remote branch naming it, and
        the attribution loop walks each."""
        git(git_flow, "branch", "feat/630-this-work-copy", "feat/630-this-work")

        match = find_ticket_commits(
            discover_repository(str(git_flow)), "630", "main", "subject"
        )

        shas = [sha for sha, _subject, _other in match.claimed_by_another]
        assert len(shas) == len(set(shas))


class TestWhatCountsAsNamingAnotherTicket:
    @pytest.mark.parametrize(
        "message, expected",
        [
            ("Merge feat/632-archive-one-way-trap for 632", "632"),
            ("Finishes 237feed-ai #632", "632"),
            ("ABC-123: do a thing", "ABC-123"),
            # Narrow on purpose: these are not ticket references.
            ("Archived 22,100 articles past the 30 day threshold", None),
            ("Raise the limit to 500", None),
            ("Work for 630 itself, see #630", None),
        ],
    )
    def test_the_pattern(self, message: str, expected: str | None) -> None:
        assert claims_another_ticket(message, "630") == expected

    def test_this_tickets_own_mention_is_not_another(self) -> None:
        assert claims_another_ticket("Phase 0 for #630", "630") is None

    def test_a_bare_number_is_not_read_as_a_ticket(self) -> None:
        """A known limit, chosen deliberately. "for 632" with no `#` and no
        `feat/` is not excluded, so such a commit stays attributed to this
        ticket and is visible in the document.

        Under-excluding leaves evidence a reader can see and argue with;
        over-excluding drops real evidence silently. Given a pattern that
        cannot be right in both directions, this one errs towards keeping.
        """
        assert claims_another_ticket("Merge the work for 632", "630") is None
