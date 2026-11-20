"""What branching model a repository looks like it uses (CON-97, D-076).

Constat supports **trunk-based development**: one mainline per repository, and
that mainline is the product as shipped. D-076 named that assumption and left
the limit documented rather than detected, with one consequence written down
for later — this module.

The assumption is one line of configuration away from a confident wrong answer.
Under Git Flow, if the default branch is `develop` then "already landed" means
*merged to develop*, and `constat state` renders unreleased behaviour as the
product's current behaviour. If the default branch is `master` instead, the
whole `develop` tree reads as never landed. The same project yields either
answer depending on a repository setting, which is why saying nothing is not
an option.

**A signal, never a verdict, and never a refusal.** What is detectable here is
a naming convention, and a naming convention is evidence about a team's habits
rather than a fact about their release process. A repository with a branch
called `production` may be trunk-based with a deployment pointer; a repository
whose default is `develop` may ship from it. So this reports what it saw and
what Constat will therefore treat as shipped, and leaves the conclusion to the
person registering it. Refusing on a word would reject a legitimate setup.

Read-only, like the rest of `constat/git/` apart from `merge.py`: it resolves
refs the repository already has and never fetches.
"""

from __future__ import annotations

from dataclasses import dataclass

from .adapter import Repository, resolve_mainline, run_git

#: A default branch with one of these names is the Git Flow integration branch,
#: which means mainline is *not* the shipped product.
INTEGRATION_NAMES = ("develop", "development")

#: Names a team gives the branch it releases from. Only interesting when such a
#: branch exists *and* is ahead of the default — a `master` that mainline
#: already contains says nothing at all.
#:
#: D-076 named `master`, `main` and `production`; `prod` is the same word. A
#: first draft also had `release` and `stable`, which was wrong: **D-031 says
#: in terms that work ahead of mainline may sit on `release/*`**, so warning
#: about a branch called `release` would warn about the supported case. The
#: list stays at what the decision named.
RELEASE_NAMES = ("master", "main", "production", "prod")


@dataclass(frozen=True)
class BranchingSignal:
    """What was seen, separated from what it might mean."""

    default_branch: str
    #: The ref Constat measures against — `origin/main`, or the local branch
    #: when no remote-tracking ref exists (D-028, D-068).
    mainline: str
    from_remote: bool
    #: True when the default branch is itself an integration branch.
    integration_is_default: bool
    #: Branches with a release-sounding name carrying commits mainline does
    #: not, each with that count.
    ahead_of_mainline: tuple[tuple[str, int], ...] = ()

    @property
    def looks_like_git_flow(self) -> bool:
        """Either signal on its own is enough to be worth saying out loud."""
        return self.integration_is_default or bool(self.ahead_of_mainline)


def _branch_names(repo: Repository, remote: str) -> tuple[str, ...]:
    """Every branch name in the repository, local and remote-tracking.

    Both, because a cached remote is cloned with `--no-checkout` (D-092) and
    has exactly one entry under `refs/heads/` — reading local branches alone
    would make every cached repository look trunk-based by construction.
    """
    result = run_git(
        [
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/heads/",
            f"refs/remotes/{remote}/",
        ],
        cwd=repo.root,
    )
    if result.returncode != 0:
        return ()

    names: set[str] = set()
    for line in result.stdout.split("\n"):
        name = line.strip()
        if not name:
            continue
        short = name[len(remote) + 1 :] if name.startswith(f"{remote}/") else name
        if short and short != "HEAD":
            names.add(short)
    return tuple(sorted(names))


def _ref_for(
    repo: Repository, name: str, remote: str, allow_local: bool
) -> str | None:
    """The remote-tracking form of a branch, or the local one, or nothing.

    Remote-tracking for the same reason D-068 chose it for mainline: it is what
    the team shares, where a local branch is one person's position.

    **`allow_local` is set only when mainline itself is local**, and that is
    the whole subtlety. Falling back unconditionally would compare a local
    branch against a shared ref — so a developer with an old local `master`
    ahead of `origin/main` would be told their repository is not trunk-based,
    which is a statement about their machine rather than their project. When
    the repository has no remote at all, local refs are all there is and
    comparing them is the only honest thing available.
    """
    candidates = [f"refs/remotes/{remote}/{name}"]
    if allow_local:
        candidates.append(f"refs/heads/{name}")
    for candidate in candidates:
        found = run_git(
            ["rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"],
            cwd=repo.root,
        )
        if found.returncode == 0:
            return candidate
    return None


def _commits_ahead(repo: Repository, mainline: str, ref: str) -> int:
    """How many commits `ref` carries that `mainline` does not.

    Zero on any failure. A count that cannot be taken is reported as nothing to
    report rather than as a signal: this feeds a warning, and a warning raised
    by a failed subprocess is worse than silence.
    """
    counted = run_git(["rev-list", "--count", f"{mainline}..{ref}"], cwd=repo.root)
    if counted.returncode != 0:
        return 0
    text = counted.stdout.strip()
    return int(text) if text.isdigit() else 0


def inspect_branching(
    repo: Repository, default_branch: str, remote: str = "origin"
) -> BranchingSignal:
    """Resolve the mainline and look for the two Git Flow shapes D-076 named.

    The comparison is against the **mainline ref**, not the local default
    branch, because mainline is what every other answer in Constat is measured
    against. A `master` ahead of a stale local `main` but not ahead of
    `origin/main` is not a second release line; it is one fetch behind.
    """
    resolved = resolve_mainline(repo, default_branch, remote)

    integration = default_branch.lower() in INTEGRATION_NAMES

    ahead: list[tuple[str, int]] = []
    for name in _branch_names(repo, remote):
        # No `name != default_branch` guard, and that is deliberate rather
        # than an omission. `main` is in RELEASE_NAMES, so a repository whose
        # default *is* `main` reaches the comparison — and resolves to the
        # same ref on both sides, giving a count of zero. A guard would be
        # dead code, which is the mistake D-087 found with `cat-file -e`: a
        # branch that cannot be taken reads as a protection that exists.
        if name.lower() not in RELEASE_NAMES:
            continue
        ref = _ref_for(repo, name, remote, allow_local=not resolved.from_remote)
        if ref is None:  # pragma: no cover - only if a ref vanishes mid-read
            continue
        count = _commits_ahead(repo, resolved.ref, ref)
        if count:
            ahead.append((name, count))

    return BranchingSignal(
        default_branch=default_branch,
        mainline=resolved.ref,
        from_remote=resolved.from_remote,
        integration_is_default=integration,
        ahead_of_mainline=tuple(sorted(ahead)),
    )
