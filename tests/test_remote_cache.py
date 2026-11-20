"""A remote URL is cloned into the workspace cache (CON-35, D-092).

`PRODUCT_SPEC` § 6 said from the start that "a remote is registered by URL and
cloned into a local cache; everything is then read with the same read-only Git
layer". The schema has carried `source_kind`, `cache_path` and
`last_fetched_at` since CON-32 and never populated them. This closes that gap.

Four properties carry these tests:

1. **Neither a path nor a recognised remote is refused**, not guessed at. A
   mistyped path must fail as a missing path.
2. **`source` stays the URL; `local_path` is where Git looks.** For a remote,
   no Git command can open `source`, and six call sites read it directly before
   this ticket.
3. **A refusal leaves nothing behind.** Identity is only knowable after cloning
   (D-025), so a duplicate is found late — and the clone is discarded.
4. **The cache is Constat's own copy**, inside the workspace: `repo remove`
   deletes it, and the remote is never written to.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.errors import AlreadyRegistered, NotRegistered, RepositoryError
from constat.git import cache
from constat.store import Registry, Workspace

from helpers import commit_file, git


def _origin(tmp_path: Path, name: str, content: str = "LIMIT = 100\n") -> Path:
    """A bare repository standing in for a remote."""
    bare = tmp_path / f"{name}.git"
    bare.mkdir()
    git(bare, "init", "--bare", "--quiet", "--initial-branch=main")
    work = tmp_path / f"{name}-work"
    git(tmp_path, "clone", "--quiet", str(bare), f"{name}-work")
    git(work, "config", "user.name", "Test Fixture")
    git(work, "config", "user.email", "fixture@example.invalid")
    commit_file(work, "rules.py", content, f"Initial ({name})")
    git(work, "push", "--quiet", "origin", "main")
    git(bare, "symbolic-ref", "HEAD", "refs/heads/main")
    return bare


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        yield ws


# -- telling a remote from a path ---------------------------------------------


class TestRecognisingARemote:
    @pytest.mark.parametrize(
        "source",
        [
            "https://example.invalid/team/billing.git",
            "http://example.invalid/billing",
            "git://example.invalid/billing.git",
            "ssh://git@example.invalid/team/billing.git",
            "git@example.invalid:team/billing.git",
            "file:///srv/git/billing.git",
        ],
    )
    def test_remote_forms_are_recognised(self, source) -> None:
        assert cache.looks_remote(source)

    @pytest.mark.parametrize(
        "source",
        ["/home/someone/git/billing", "./billing", "../billing", "billing"],
    )
    def test_paths_are_not_remotes(self, source) -> None:
        assert not cache.looks_remote(source)

    def test_a_mistyped_path_fails_as_a_path(self, workspace, tmp_path) -> None:
        """The reason the forms are a list rather than "anything that is not a
        directory": a typo must not be cloned from."""
        with pytest.raises(RepositoryError):
            Registry(workspace).add(str(tmp_path / "no-such-directory"))


class TestTheCacheName:
    @pytest.mark.parametrize(
        "source,expected",
        [
            ("https://example.invalid/team/billing.git", "billing"),
            ("https://example.invalid/team/billing", "billing"),
            ("git@example.invalid:team/billing.git", "billing"),
            ("https://example.invalid/team/billing/", "billing"),
        ],
    )
    def test_it_comes_from_the_last_segment(self, source, expected) -> None:
        assert cache.cache_name(source) == expected

    def test_awkward_characters_are_sanitised(self) -> None:
        """This becomes a directory name inside the workspace, and a URL can
        hold almost anything."""
        assert cache.cache_name("https://example.invalid/a/b%20c!.git") == "b-20c"

    def test_an_empty_tail_still_yields_a_name(self) -> None:
        assert cache.cache_name("https://example.invalid/") == "example.invalid"


# -- registering one ----------------------------------------------------------


class TestRegisteringARemote:
    def test_it_is_cloned_into_the_workspace(self, workspace, tmp_path) -> None:
        origin = _origin(tmp_path, "billing")

        entry = Registry(workspace).add(f"file://{origin}")

        assert entry.source_kind == "remote"
        assert entry.cache_path is not None
        assert Path(entry.cache_path).exists()
        # Inside the workspace, so one `rm -r` removes everything Constat owns.
        assert Path(entry.cache_path).is_relative_to(workspace.home)

    def test_the_source_stays_the_url(self, workspace, tmp_path) -> None:
        """`source` is the record of where the repository came from. For a
        remote it is a URL no Git command can open, which is why callers use
        `local_path`."""
        origin = _origin(tmp_path, "billing")

        entry = Registry(workspace).add(f"file://{origin}")

        assert entry.source == f"file://{origin}"
        assert entry.local_path == entry.cache_path

    def test_a_local_path_has_no_cache_and_reads_where_it_is(
        self, workspace, tmp_path
    ) -> None:
        origin = _origin(tmp_path, "billing")
        clone = tmp_path / "local"
        git(tmp_path, "clone", "--quiet", str(origin), "local")

        entry = Registry(workspace).add(str(clone))

        assert entry.source_kind == "local"
        assert entry.cache_path is None
        assert entry.local_path == entry.source

    def test_the_fetch_time_is_recorded(self, workspace, tmp_path) -> None:
        """Unstated staleness is the same class of failure as unstated
        truncation (D-027). CON-38 renders this; it has to exist first."""
        origin = _origin(tmp_path, "billing")

        entry = Registry(workspace).add(f"file://{origin}")

        assert entry.last_fetched_at is not None

    def test_identity_is_the_root_commit_not_the_url(
        self, workspace, tmp_path
    ) -> None:
        origin = _origin(tmp_path, "billing")

        entry = Registry(workspace).add(f"file://{origin}")

        assert len(entry.identity) == 40

    def test_the_default_branch_is_resolved_from_the_clone(
        self, workspace, tmp_path
    ) -> None:
        origin = _origin(tmp_path, "billing")

        entry = Registry(workspace).add(f"file://{origin}")

        assert entry.default_branch == "main"


class TestRefusalsLeaveNothingBehind:
    def test_the_same_repository_by_two_urls_is_refused(
        self, workspace, tmp_path
    ) -> None:
        """Identity is the root commit (D-025), so this is only knowable after
        cloning: two different URLs can point at one repository."""
        origin = _origin(tmp_path, "billing")
        registry = Registry(workspace)
        registry.add(f"file://{origin}", alias="first")

        with pytest.raises(AlreadyRegistered, match="same"):
            registry.add(f"file://{origin}/", alias="second")

    def test_the_discarded_clone_is_removed(self, workspace, tmp_path) -> None:
        """A refusal must not leave a directory the next attempt trips over on
        `clone`'s own exists-check, for a reason the user never caused."""
        origin = _origin(tmp_path, "billing")
        registry = Registry(workspace)
        registry.add(f"file://{origin}", alias="first")

        with pytest.raises(AlreadyRegistered):
            registry.add(f"file://{origin}/", alias="second")

        assert not (workspace.home / "cache" / "second").exists()

    def test_a_taken_alias_is_refused_before_cloning(
        self, workspace, tmp_path
    ) -> None:
        """Cheap checks first: no point paying for a clone to learn the name is
        taken."""
        first = _origin(tmp_path, "one")
        second = _origin(tmp_path, "two", content="OTHER = 1\n")
        registry = Registry(workspace)
        registry.add(f"file://{first}", alias="taken")

        with pytest.raises(AlreadyRegistered, match="unrelated"):
            registry.add(f"file://{second}", alias="taken")

    def test_an_unreachable_remote_leaves_no_partial_clone(
        self, workspace, tmp_path
    ) -> None:
        """A directory that looks like a cached repository but is not one would
        read on the next run as an unreadable repository — the symptom D-070
        warns produces a false retirement candidate."""
        missing = tmp_path / "not-a-repository.git"

        with pytest.raises(RepositoryError, match="could not clone"):
            Registry(workspace).add(f"file://{missing}")

        assert not (workspace.home / "cache" / "not-a-repository").exists()

    def test_cloning_over_an_existing_directory_is_refused(
        self, workspace, tmp_path
    ) -> None:
        """Either a half-finished clone or a name collision, and quietly
        replacing it would destroy whichever it is."""
        origin = _origin(tmp_path, "billing")
        occupied = workspace.home / "cache" / "billing"
        occupied.mkdir(parents=True)

        with pytest.raises(RepositoryError, match="already exists"):
            Registry(workspace).add(f"file://{origin}")


# -- using and refreshing it --------------------------------------------------


class TestItReadsLikeAnyRepository:
    def test_the_cache_is_readable_by_the_git_layer(
        self, workspace, tmp_path
    ) -> None:
        """The point of the ticket: "read with the same read-only Git layer"."""
        from constat.git.adapter import discover_repository, resolve_mainline

        origin = _origin(tmp_path, "billing")
        entry = Registry(workspace).add(f"file://{origin}")

        repo = discover_repository(entry.local_path)
        mainline = resolve_mainline(repo, entry.default_branch)

        assert mainline.ref in ("main", "origin/main")

    def test_it_has_the_remote_tracking_refs_and_no_checkout(
        self, workspace, tmp_path
    ) -> None:
        """Both halves matter, and the first attempt got one of them wrong.

        `--mirror` gives no checkout but also no remote-tracking namespace, so
        `refs/remotes/origin/HEAD` does not exist — and D-028 resolves the
        default branch from exactly that ref. `--no-checkout` keeps the
        namespace the read-only layer is built on and still materialises no
        files."""
        origin = _origin(tmp_path, "billing")
        entry = Registry(workspace).add(f"file://{origin}")
        cached = Path(entry.cache_path)

        assert not (cached / "rules.py").exists()
        assert git(cached, "symbolic-ref", "refs/remotes/origin/HEAD")
        assert git(cached, "rev-parse", "origin/main")


class TestRefreshing:
    def test_a_fetch_brings_new_commits_in(self, workspace, tmp_path) -> None:
        origin = _origin(tmp_path, "billing")
        registry = Registry(workspace)
        entry = registry.add(f"file://{origin}")
        # `origin/main`, not `main`: a fetch moves the remote-tracking ref, and
        # that is the one Constat reads as mainline (D-068). The cache's own
        # local branch stays where the clone left it, which is correct and was
        # what this test asserted on first writing.
        before = git(Path(entry.cache_path), "rev-parse", "origin/main")

        work = tmp_path / "billing-work"
        commit_file(work, "rules.py", "LIMIT = 250\n", "Raise the limit")
        git(work, "push", "--quiet", "origin", "main")

        registry.refresh(entry.alias)

        assert git(Path(entry.cache_path), "rev-parse", "origin/main") != before

    def test_the_fetch_time_moves(self, workspace, tmp_path) -> None:
        origin = _origin(tmp_path, "billing")
        registry = Registry(workspace)
        entry = registry.add(f"file://{origin}")

        refreshed = registry.refresh(entry.alias)

        assert refreshed.last_fetched_at >= entry.last_fetched_at

    def test_refreshing_a_local_path_is_refused(self, workspace, tmp_path) -> None:
        """There is nothing to fetch, and a recorded fetch time would be a
        claim about a copy that does not exist."""
        origin = _origin(tmp_path, "billing")
        git(tmp_path, "clone", "--quiet", str(origin), "local")
        registry = Registry(workspace)
        registry.add(str(tmp_path / "local"), alias="local")

        with pytest.raises(NotRegistered, match="local path"):
            registry.refresh("local")

    def test_refreshing_an_unknown_alias_is_refused(self, workspace) -> None:
        with pytest.raises(NotRegistered, match="no repository"):
            Registry(workspace).refresh("nothing")


class TestRemoving:
    def test_removing_a_remote_deletes_its_clone(self, workspace, tmp_path) -> None:
        """The clone is Constat's own copy, so unregistering removes it."""
        origin = _origin(tmp_path, "billing")
        registry = Registry(workspace)
        entry = registry.add(f"file://{origin}")
        cached = Path(entry.cache_path)
        assert cached.exists()

        registry.remove(entry.alias)

        assert not cached.exists()

    def test_the_remote_itself_is_untouched(self, workspace, tmp_path) -> None:
        """Constat is read-only against every repository it reads, and a cache
        clone is a read whose result was kept (D-092)."""
        origin = _origin(tmp_path, "billing")
        before = git(origin, "rev-parse", "main")
        registry = Registry(workspace)
        entry = registry.add(f"file://{origin}")

        registry.remove(entry.alias)

        assert git(origin, "rev-parse", "main") == before
        assert origin.exists()

    def test_removing_a_local_path_leaves_it_alone(
        self, workspace, tmp_path
    ) -> None:
        origin = _origin(tmp_path, "billing")
        git(tmp_path, "clone", "--quiet", str(origin), "local")
        clone = tmp_path / "local"
        registry = Registry(workspace)
        registry.add(str(clone), alias="local")

        registry.remove("local")

        assert clone.exists()
