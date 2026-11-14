"""A landed ticket does not keep reading as pending (CON-76).

Found immediately after `merge_on_accept` landed ticket 628: the merge is made
in a throwaway clone and pushed, so the repository someone actually works in
never learned of it, and `237feed`'s local `main` sat two commits behind
`origin/main`. The ticket had shipped and still read `pending` — D-031's
status misreporting the one thing it exists to say.

Three parts, tested separately because they fail separately:

1. **Mainline is the remote-tracking ref**, which is what everyone else pulls,
   rather than one checkout's last pull.
2. **Constat refreshes that ref after its own push**, closing the staleness it
   caused — and nothing more. `.git` refs only, never the working tree.
3. **The rest is disclosed.** A repository someone *else* pushed to is stale
   and no write fixes that; the document says the picture may be old.

`git pull` appears nowhere, for the reason the merge happens in a clone: the
registered repository may hold uncommitted work, sit on another branch, or be
mid-rebase.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.git.adapter import discover_repository, resolve_mainline
from constat.git.merge import merge_ticket_branch, refresh_remote_ref
from constat.operations import collect
from constat.store import Registry, TicketStore, Workspace
from constat.tickets import TicketStatus
from helpers import commit_file, git


# -- fixtures -----------------------------------------------------------------


@pytest.fixture
def shared(tmp_path: Path) -> tuple[Path, Path]:
    """A bare remote, and a clone of it with a branch naming ticket 628.

    Two commits on `main` before branching, so "behind" can be a number other
    than one.
    """
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
    """Land 628 the way Constat does: merge in a separate clone, push."""
    merge_ticket_branch(
        discover_repository(clone),
        alias="237feed",
        branches=("refs/remotes/origin/feat/628-first-launch",),
        target_branch="main",
        reference="628",
    )


# -- 1. mainline is the remote-tracking ref -----------------------------------


class TestResolvingMainline:
    def test_the_remote_tracking_ref_is_preferred(self, shared) -> None:
        _bare, clone = shared

        mainline = resolve_mainline(discover_repository(clone), "main")

        assert mainline.ref == "origin/main"
        assert mainline.from_remote

    def test_a_repository_with_no_remote_falls_back_and_says_so(
        self, tmp_path: Path
    ) -> None:
        """Not an error — a local-only repository is valid. But the document
        must not present one clone's branch as mainline."""
        solo = tmp_path / "solo"
        solo.mkdir()
        git(solo, "init", "--quiet", "--initial-branch=main")
        commit_file(solo, "README.md", "first\n", "First commit")

        mainline = resolve_mainline(discover_repository(solo), "main")

        assert mainline.ref == "main"
        assert mainline.from_remote is False
        assert "only as current as this clone" in mainline.describe()

    def test_the_drift_is_counted(self, shared) -> None:
        bare, clone = shared
        _land(clone)
        # The refresh taught the clone about the merge, so origin/main is now
        # ahead of the local branch by the commit and its merge.
        mainline = resolve_mainline(discover_repository(clone), "main")

        assert mainline.behind == 2
        assert mainline.is_stale
        assert "the local `main` is 2 behind" in mainline.describe()

    def test_unpushed_local_work_is_counted_the_other_way(self, shared) -> None:
        """The drift nobody expects, and the one that changed behaviour.

        Two existing tests failed when mainline became the shared ref: both
        committed "already shipped" work to a local `main` and never pushed it.
        Measuring against `origin/main` makes that work read as not yet landed
        — true of the mainline everyone pulls, and surprising to whoever
        committed it. So the number is reported rather than left to be
        inferred from a status that looks wrong.
        """
        _bare, clone = shared
        commit_file(clone, "local.py", "x\n", "Committed here, never pushed")

        mainline = resolve_mainline(discover_repository(clone), "main")

        assert mainline.ahead == 1
        assert mainline.has_unpushed
        assert mainline.is_stale is False
        assert "1 local commit(s) are not on it" in mainline.describe()

    def test_both_directions_at_once(self, shared) -> None:
        """A clone can be behind and ahead, and the two are not alternatives."""
        _bare, clone = shared
        _land(clone)
        commit_file(clone, "local.py", "x\n", "Committed here, never pushed")

        mainline = resolve_mainline(discover_repository(clone), "main")

        assert (mainline.behind, mainline.ahead) == (2, 1)
        described = mainline.describe()
        assert "2 behind" in described and "1 local commit(s)" in described

    def test_no_drift_when_they_agree(self, shared) -> None:
        _bare, clone = shared

        mainline = resolve_mainline(discover_repository(clone), "main")

        assert mainline.behind == 0
        assert mainline.is_stale is False
        assert mainline.describe() == "`origin/main`"


# -- the failure this ticket exists for ---------------------------------------


class TestAShippedTicketReadsAsLanded:
    """The headline. Measured against the local branch, 628 read `pending`
    after shipping; measured against `origin/main` it reads `landed`."""

    @pytest.fixture
    def workspace(self, tmp_path: Path, shared):
        _bare, clone = shared
        with Workspace.create(tmp_path / "ws") as ws:
            Registry(ws).add(str(clone), alias="237feed", default_branch="main")
            TicketStore(ws).add("628")
            yield ws

    def test_before_landing_it_is_pending(self, workspace, shared) -> None:
        findings = collect(workspace, "628")

        assert findings[0].status is TicketStatus.PENDING

    def test_after_landing_it_is_not_pending(self, workspace, shared) -> None:
        """The whole point. The local branch still does not have the merge."""
        _bare, clone = shared
        _land(clone)

        findings = collect(workspace, "628")

        assert findings[0].status is TicketStatus.LANDED
        assert git(clone, "rev-parse", "main") != git(clone, "rev-parse", "origin/main")

    def test_the_finding_carries_the_ref_it_measured_against(
        self, workspace, shared
    ) -> None:
        """Carried rather than re-derived at render time: the document has to
        report the ref the comparison actually used."""
        findings = collect(workspace, "628")

        assert findings[0].mainline is not None
        assert findings[0].mainline.ref == "origin/main"


# -- 2. Constat refreshes the ref it made stale -------------------------------


class TestRefreshAfterItsOwnPush:
    def test_the_clone_learns_of_the_merge(self, shared) -> None:
        bare, clone = shared
        _land(clone)

        assert git(clone, "rev-parse", "origin/main") == git(
            bare, "rev-parse", "refs/heads/main"
        )

    def test_the_working_tree_and_local_branch_are_untouched(self, shared) -> None:
        """A fetch of one ref, not a pull. The registered repository may hold
        work in progress, which is why the merge happened elsewhere."""
        _bare, clone = shared
        local_before = git(clone, "rev-parse", "main")
        head_before = git(clone, "rev-parse", "HEAD")

        _land(clone)

        assert git(clone, "rev-parse", "main") == local_before
        assert git(clone, "rev-parse", "HEAD") == head_before
        assert not (clone / "device.py").exists()
        assert git(clone, "status", "--short") == ""

    def test_a_landed_merge_reports_the_refresh(self, shared) -> None:
        _bare, clone = shared

        result = merge_ticket_branch(
            discover_repository(clone),
            alias="237feed",
            branches=("refs/remotes/origin/feat/628-first-launch",),
            target_branch="main",
            reference="628",
        )

        assert result.landed
        assert result.refreshed is True

    def test_nothing_landed_means_nothing_to_refresh(self, shared) -> None:
        """`None`, not False. "Not applicable" and "tried and failed" are
        different states and a reader must be able to tell them apart."""
        _bare, clone = shared

        result = merge_ticket_branch(
            discover_repository(clone),
            alias="237feed",
            branches=(),
            target_branch="main",
            reference="999",
        )

        assert result.outcome == "no_branch"
        assert result.refreshed is None

    def test_a_failed_refresh_is_not_a_failed_landing(self, shared) -> None:
        """The merge is on the remote either way.

        The remote is removed after the push would have happened, so the
        refresh cannot work — standing in for a network that dropped between
        the two operations.
        """
        bare, clone = shared
        before = git(bare, "rev-parse", "refs/heads/main")
        git(clone, "remote", "set-url", "origin", str(bare))
        _land(clone)
        assert git(bare, "rev-parse", "refs/heads/main") != before

        # Now break the remote and prove the refresh alone reports False.
        git(clone, "remote", "set-url", "origin", str(bare / "gone"))
        assert refresh_remote_ref(discover_repository(clone), "main") is False


# -- 3. the rest is disclosed -------------------------------------------------


class TestDisclosure:
    def test_the_document_names_the_ref_and_the_drift(
        self, tmp_path: Path, shared
    ) -> None:
        from constat.operations import render

        bare, clone = shared
        _land(clone)
        # Wind the clone's knowledge forward but leave the local branch behind,
        # which is exactly the state landing a ticket produces.
        with Workspace.create(tmp_path / "ws") as ws:
            Registry(ws).add(str(clone), alias="237feed", default_branch="main")
            TicketStore(ws).add("628")
            body = render("628", collect(ws, "628"))

        assert "Measured against `origin/main`" in body
        assert "has not caught up" in body

    def test_unpushed_work_is_explained_in_the_document(
        self, tmp_path: Path, shared
    ) -> None:
        """A reader has to be told why their own commit reads as unlanded."""
        from constat.operations import render

        _bare, clone = shared
        commit_file(clone, "local.py", "x\n", "Local work (628)")
        with Workspace.create(tmp_path / "ws") as ws:
            Registry(ws).add(str(clone), alias="237feed", default_branch="main")
            TicketStore(ws).add("628")
            body = render("628", collect(ws, "628"))

        assert "are not on `origin/main`" in body
        assert "reads below as not yet landed" in body

    def test_a_current_clone_says_nothing_about_staleness(
        self, tmp_path: Path, shared
    ) -> None:
        """Disclosure must be a signal, not boilerplate on every document."""
        from constat.operations import render

        _bare, clone = shared
        with Workspace.create(tmp_path / "ws") as ws:
            Registry(ws).add(str(clone), alias="237feed", default_branch="main")
            TicketStore(ws).add("628")
            body = render("628", collect(ws, "628"))

        assert "Measured against `origin/main`" in body
        assert "has not caught up" not in body
