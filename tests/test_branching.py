"""Registration says what it will treat as shipped, and warns (CON-97, D-076).

D-076 named the assumption and left it documented rather than detected, with
one consequence written down for later: `repo add` should say which mainline it
resolved and warn on a Git Flow shape. This is that.

The properties these tests carry:

1. **A warning, never a refusal.** Exit 0 every time. The signal is a naming
   convention, and refusing on a convention would reject a legitimate
   repository that happens to use the word.
2. **Silence when it looks trunk-based.** A reassuring paragraph on every
   `repo add` is how a warning stops being read.
3. **Ahead of *mainline*, not ahead of the local default branch.** A `master`
   ahead of a stale local `main` is one fetch behind, not a second release
   line.
4. **`release/*` must not warn.** D-031 says in terms that work ahead of
   mainline may sit there, so warning about it would warn about the supported
   case. A first draft of `RELEASE_NAMES` got this wrong.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from constat.cli import main
from constat.git import inspect_branching
from constat.git.adapter import discover_repository
from constat.operations import describe_branching


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def build(tmp_path: Path, name: str, default: str) -> Path:
    """A repository with a remote, so remote-tracking refs exist as they do in
    real use (D-068) rather than only local branches."""
    remote = tmp_path / f"{name}.git"
    remote.mkdir()
    subprocess.run(
        ["git", "init", "--bare", "--quiet", f"--initial-branch={default}", str(remote)],
        check=True,
        capture_output=True,
    )
    work = tmp_path / name
    subprocess.run(
        ["git", "clone", "--quiet", str(remote), str(work)],
        check=True,
        capture_output=True,
    )
    git(work, "config", "user.email", "d@e.invalid")
    git(work, "config", "user.name", "Demo")
    (work / "app.py").write_text("v1\n")
    git(work, "add", "-A")
    git(work, "commit", "--quiet", "-m", "v1")
    git(work, "branch", "--quiet", "-M", default)
    git(work, "push", "--quiet", "-u", "origin", default)
    git(work, "remote", "set-head", "origin", "-a")
    # The bare side needs its HEAD set too, or cloning *it* — which is what
    # registering a remote does (D-092) — yields no `origin/HEAD` to resolve.
    subprocess.run(
        ["git", "symbolic-ref", "HEAD", f"refs/heads/{default}"],
        cwd=remote,
        check=True,
        capture_output=True,
    )
    return work


def branch_ahead(work: Path, name: str, default: str) -> None:
    """A branch carrying one commit the default does not, pushed."""
    git(work, "checkout", "--quiet", "-b", name)
    (work / "app.py").write_text(f"v2 on {name}\n")
    git(work, "commit", "--quiet", "-am", f"work on {name}")
    git(work, "push", "--quiet", "-u", "origin", name)
    git(work, "checkout", "--quiet", default)


# -- the signal ---------------------------------------------------------------


class TestWhatTheSignalSees:
    def test_a_trunk_based_repository_raises_nothing(self, tmp_path: Path):
        work = build(tmp_path, "app", "main")

        signal = inspect_branching(discover_repository(work), "main")

        assert signal.looks_like_git_flow is False
        assert signal.mainline == "origin/main"

    def test_a_develop_default_is_the_integration_shape(self, tmp_path: Path):
        work = build(tmp_path, "app", "develop")

        signal = inspect_branching(discover_repository(work), "develop")

        assert signal.integration_is_default is True
        assert signal.looks_like_git_flow is True

    def test_development_counts_too(self, tmp_path: Path):
        work = build(tmp_path, "app", "development")

        signal = inspect_branching(discover_repository(work), "development")

        assert signal.integration_is_default is True

    def test_the_name_is_matched_regardless_of_case(self, tmp_path: Path):
        work = build(tmp_path, "app", "Develop")

        signal = inspect_branching(discover_repository(work), "Develop")

        assert signal.integration_is_default is True

    def test_a_release_named_branch_ahead_of_mainline_is_seen(self, tmp_path: Path):
        work = build(tmp_path, "app", "develop")
        branch_ahead(work, "master", "develop")

        signal = inspect_branching(discover_repository(work), "develop")

        assert signal.ahead_of_mainline == (("master", 1),)

    def test_production_is_one_of_the_names(self, tmp_path: Path):
        work = build(tmp_path, "app", "main")
        branch_ahead(work, "production", "main")

        signal = inspect_branching(discover_repository(work), "main")

        assert signal.ahead_of_mainline == (("production", 1),)
        assert signal.looks_like_git_flow is True

    def test_a_feature_branch_ahead_is_not_a_signal(self, tmp_path: Path):
        """The supported case, and the one that would make this unusable if it
        warned: D-031's window is everything ahead of mainline, so a repository
        with open work is the normal state."""
        work = build(tmp_path, "app", "main")
        branch_ahead(work, "feat/402-raise-the-limit", "main")

        signal = inspect_branching(discover_repository(work), "main")

        assert signal.looks_like_git_flow is False

    def test_a_release_branch_is_not_a_signal(self, tmp_path: Path):
        """D-031 says in terms that work ahead of mainline may sit on
        `release/*`. A first draft of `RELEASE_NAMES` included `release` and
        would have warned about the supported case."""
        # Two repositories, because git will not hold a branch called
        # `release` alongside `release/1.2` — the ref paths collide.
        slashed = build(tmp_path, "slashed", "main")
        branch_ahead(slashed, "release/1.2", "main")
        plain = build(tmp_path, "plain", "main")
        branch_ahead(plain, "release", "main")

        for work in (slashed, plain):
            signal = inspect_branching(discover_repository(work), "main")
            assert signal.looks_like_git_flow is False

    def test_a_release_named_branch_mainline_contains_says_nothing(
        self, tmp_path: Path
    ):
        """A `master` that mainline already contains is a tag by another name,
        not a second line. The count is what makes the name interesting."""
        work = build(tmp_path, "app", "main")
        git(work, "branch", "master")
        git(work, "push", "--quiet", "origin", "master")

        signal = inspect_branching(discover_repository(work), "main")

        assert signal.ahead_of_mainline == ()
        assert signal.looks_like_git_flow is False

    def test_a_default_branch_called_main_does_not_warn_about_itself(
        self, tmp_path: Path
    ):
        """`main` is in the release-name list, so a repository whose default
        *is* `main` reaches the comparison. It resolves to the same ref on both
        sides and counts zero, which is why there is no exclusion guard: one
        would be dead code."""
        work = build(tmp_path, "app", "main")

        signal = inspect_branching(discover_repository(work), "main")

        assert [name for name, _ in signal.ahead_of_mainline] == []

    def test_it_measures_against_mainline_not_the_local_branch(
        self, tmp_path: Path
    ):
        """A `master` ahead of a stale local `main` but not ahead of
        `origin/main` is one fetch behind, not a release line. The whole
        product measures against the remote-tracking ref (D-028, D-068) and
        this must agree with it."""
        work = build(tmp_path, "app", "main")
        branch_ahead(work, "master", "main")
        # Mainline catches up with master; the local `main` is left behind.
        git(work, "push", "--quiet", "origin", "master:main")
        git(work, "fetch", "--quiet", "origin")

        signal = inspect_branching(discover_repository(work), "main")

        assert git(work, "rev-parse", "main") != git(work, "rev-parse", "origin/main")
        assert signal.ahead_of_mainline == ()

    def test_an_unpushed_release_branch_is_one_persons_work(self, tmp_path: Path):
        """The candidate side of the same rule as mainline's. A `master` that
        exists only locally is one person's position, not something the team
        releases from — D-068 chose remote-tracking refs for exactly this
        reason, and both sides of the comparison have to agree on it."""
        work = build(tmp_path, "app", "main")
        git(work, "checkout", "--quiet", "-b", "master")
        (work / "app.py").write_text("unpushed\n")
        git(work, "commit", "--quiet", "-am", "not pushed anywhere")
        git(work, "checkout", "--quiet", "main")

        signal = inspect_branching(discover_repository(work), "main")

        assert signal.ahead_of_mainline == ()

    def test_with_no_remote_a_local_release_branch_does_count(
        self, tmp_path: Path
    ):
        """The other side of the rule above. With no remote there is nothing
        shared to compare against, so local refs are all there is — and
        refusing to look at them would make the signal silent in exactly the
        repository where every ref is local."""
        work = tmp_path / "solo"
        work.mkdir()
        git(work, "init", "--quiet", "--initial-branch=develop")
        git(work, "config", "user.email", "d@e.invalid")
        git(work, "config", "user.name", "Demo")
        (work / "app.py").write_text("v1\n")
        git(work, "add", "-A")
        git(work, "commit", "--quiet", "-m", "v1")
        git(work, "checkout", "--quiet", "-b", "master")
        (work / "app.py").write_text("released\n")
        git(work, "commit", "--quiet", "-am", "released")
        git(work, "checkout", "--quiet", "develop")

        signal = inspect_branching(discover_repository(work), "develop")

        assert signal.from_remote is False
        assert signal.ahead_of_mainline == (("master", 1),)

    def test_a_repository_with_no_remote_reports_a_local_mainline(
        self, tmp_path: Path
    ):
        """`resolve_mainline` falls back to the local branch and records that
        it did. The signal passes it through rather than presenting a local
        position as the shared one."""
        work = tmp_path / "solo"
        work.mkdir()
        git(work, "init", "--quiet", "--initial-branch=main")
        git(work, "config", "user.email", "d@e.invalid")
        git(work, "config", "user.name", "Demo")
        (work / "app.py").write_text("v1\n")
        git(work, "add", "-A")
        git(work, "commit", "--quiet", "-m", "v1")

        signal = inspect_branching(discover_repository(work), "main")

        assert signal.from_remote is False
        assert signal.mainline == "main"


# -- the wording --------------------------------------------------------------


class TestWhatIsSaid:
    def test_a_trunk_based_repository_is_told_nothing(self, tmp_path: Path):
        """Silence is the design. A paragraph of reassurance on every `repo
        add` is how a warning stops being read."""
        work = build(tmp_path, "app", "main")

        signal = inspect_branching(discover_repository(work), "main")

        assert describe_branching(signal) == ()

    def test_it_names_what_will_be_treated_as_shipped(self, tmp_path: Path):
        work = build(tmp_path, "app", "develop")

        said = " ".join(describe_branching(inspect_branching(discover_repository(work), "develop")))

        assert "origin/develop as the product as shipped" in said

    def test_it_names_the_consequence_not_just_the_observation(
        self, tmp_path: Path
    ):
        """The part that makes the warning worth reading. "Your default branch
        is called develop" is a fact about naming; "state would present
        unreleased behaviour as current behaviour" is why it matters."""
        work = build(tmp_path, "app", "develop")

        said = " ".join(describe_branching(inspect_branching(discover_repository(work), "develop")))

        assert "shipped when it has only been integrated" in said
        assert "unreleased behaviour as the product's current behaviour" in said

    def test_it_names_the_escape_hatch(self, tmp_path: Path):
        work = build(tmp_path, "app", "develop")

        said = " ".join(describe_branching(inspect_branching(discover_repository(work), "develop")))

        assert "--default-branch" in said

    def test_it_counts_the_commits_rather_than_saying_ahead(self, tmp_path: Path):
        """A count is checkable; "ahead" is a word."""
        work = build(tmp_path, "app", "develop")
        branch_ahead(work, "master", "develop")

        said = " ".join(describe_branching(inspect_branching(discover_repository(work), "develop")))

        assert "carries 1 commit(s)" in said


# -- registration -------------------------------------------------------------


class TestRegistration:
    def _home(self, tmp_path: Path) -> str:
        ws = str(tmp_path / "ws")
        main(["--workspace", ws, "init"])
        return ws

    def test_a_git_flow_repository_registers_and_warns(
        self, tmp_path: Path, capsys
    ):
        """The property this ticket exists for: a warning, never a refusal
        (D-076). Registration succeeds and the repository is usable."""
        work = build(tmp_path, "app", "develop")
        branch_ahead(work, "master", "develop")
        ws = self._home(tmp_path)
        capsys.readouterr()

        code = main(["--workspace", ws, "repo", "add", str(work), "--name", "app"])

        out = capsys.readouterr().out
        assert code == 0
        assert "may not be trunk-based" in out
        assert "registered: app" in out

    def test_a_trunk_based_repository_gets_no_warning(self, tmp_path: Path, capsys):
        work = build(tmp_path, "app", "main")
        ws = self._home(tmp_path)
        capsys.readouterr()

        main(["--workspace", ws, "repo", "add", str(work), "--name", "app"])

        out = capsys.readouterr().out
        assert "trunk-based" not in out

    def test_naming_the_branch_explicitly_silences_it(self, tmp_path: Path, capsys):
        """The escape hatch the warning advertises has to work, or the advice
        is wrong. A Git Flow repository registered against `master` is being
        read the way its team releases."""
        work = build(tmp_path, "app", "develop")
        branch_ahead(work, "master", "develop")
        ws = self._home(tmp_path)
        capsys.readouterr()

        main(
            [
                "--workspace",
                ws,
                "repo",
                "add",
                str(work),
                "--name",
                "app",
                "--default-branch",
                "master",
            ]
        )

        out = capsys.readouterr().out
        assert "may not be trunk-based" not in out

    def test_it_names_the_resolved_mainline_for_every_repository(
        self, tmp_path: Path, capsys
    ):
        """Half of CON-97's done-when, and it applies to the quiet case too.
        "default branch: main" is configuration; the mainline ref is what every
        answer about shipped behaviour is measured against."""
        work = build(tmp_path, "app", "main")
        ws = self._home(tmp_path)
        capsys.readouterr()

        main(["--workspace", ws, "repo", "add", str(work), "--name", "app"])

        out = capsys.readouterr().out
        assert "mainline:       origin/main" in out
        assert "trunk-based" not in out

    def test_a_local_mainline_is_marked_as_one(self, tmp_path: Path, capsys):
        """A fallback to a local branch is a weaker claim than a shared ref,
        and the output says so rather than printing a bare branch name that
        reads like the remote one."""
        work = tmp_path / "solo"
        work.mkdir()
        git(work, "init", "--quiet", "--initial-branch=main")
        git(work, "config", "user.email", "d@e.invalid")
        git(work, "config", "user.name", "Demo")
        (work / "app.py").write_text("v1\n")
        git(work, "add", "-A")
        git(work, "commit", "--quiet", "-m", "v1")
        ws = self._home(tmp_path)
        capsys.readouterr()

        main(
            [
                "--workspace",
                ws,
                "repo",
                "add",
                str(work),
                "--name",
                "solo",
                "--default-branch",
                "main",
            ]
        )

        out = capsys.readouterr().out
        assert "mainline:       main" in out
        assert "no remote-tracking ref" in out

    def test_the_warning_is_wrapped(self, tmp_path: Path, capsys):
        """Hand-wrapped literals are the convention everywhere else in this
        output, and these sentences interpolate branch names and counts so they
        cannot be. Wrapped at print time instead."""
        work = build(tmp_path, "app", "develop")
        ws = self._home(tmp_path)
        capsys.readouterr()

        main(["--workspace", ws, "repo", "add", str(work), "--name", "app"])

        out = capsys.readouterr().out
        assert out.splitlines()
        assert max(len(line) for line in out.splitlines()) < 100

    def test_it_is_read_through_the_cache_for_a_remote(self, tmp_path: Path):
        """`branching_of` opens `local_path`, never `source` — the cache for a
        remote, the registered path for a local one (D-092). Reading `source`
        for a URL would try to open a URL as a directory."""
        from constat.store import Registry, Workspace

        work = build(tmp_path, "app", "develop")
        branch_ahead(work, "master", "develop")
        ws = self._home(tmp_path)

        with Workspace.open(ws) as workspace:
            registry = Registry(workspace)
            entry = registry.add(f"file://{tmp_path / 'app.git'}", alias="app")
            signal = registry.branching_of(entry)

        assert entry.cache_path is not None
        # `ahead_of_mainline` specifically, not `looks_like_git_flow`: the
        # default being `develop` would satisfy the latter on its own and the
        # assertion would pass without ever reading a remote-tracking ref —
        # which is the only kind a `--no-checkout` clone has beyond its one
        # local branch.
        assert signal.ahead_of_mainline == (("master", 1),)
