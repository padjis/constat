"""Merging a ticket's branch into mainline (D-062).

**This is the only module in `constat/git/` that writes**, and it is separate
from `adapter.py` for that reason alone: `adapter.py` states that it never
writes to a repository, never mutates a working tree and never takes a lock,
and that claim has to stay true for the module a reader checks first.
Everything here is deliberately on the other side of that line.

It exists because accepting a rule proposal can now land the ticket's work
(D-062), which amends product rule 7's read-only posture for this one path.
Reached only when `merge_on_accept` is on; the amendment is narrow, and the
refusals below are what keeps it narrow.

**It never touches the repository you registered.** Like
`publish/targets/git_pages.py`, it works in a throwaway clone of the remote:
the registered path may hold uncommitted work, a half-finished rebase or a
checked-out mainline, and a tool that merges into *that* can destroy work it
never read. So the merge happens in a clone and reaches mainline by pushing.

**Every uncertainty is a refusal, not a resolution.** A conflict is reported
and the merge aborted; two branches naming the ticket are reported rather than
one being picked; a branch absent from the remote is reported rather than
hunted for locally. Nothing is forced, and the only ref ever pushed is
mainline advanced by a merge commit made seconds earlier in this process.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

from ..errors import GitUnavailable
from .adapter import GIT, Repository, remote_url

Outcome = Literal[
    "merged",
    "already_merged",
    "no_branch",
    "ambiguous_branch",
    "branch_not_on_remote",
    "no_remote",
    "no_identity",
    "repository_unreadable",
    "clone_failed",
    "conflict",
    "merge_failed",
    "push_failed",
]

LANDED = "merged"
"""The only outcome that changed mainline. Every other one left it alone, and
that distinction is the point of reporting an outcome rather than a bool."""

MERGE_SUBJECT = "Merge {branch} for {reference}"

MERGE_BODY = (
    "Landed by Constat when a rule proposal read from this work was accepted.\n"
    "The acceptance is the human decision; this merge records that it was made.\n"
    "See `constat rule history` for the rule version it baselined."
)


@dataclass(frozen=True)
class MergeResult:
    """What one repository's merge attempt did, and why.

    `outcome` carries the whole answer and is never inferred from the other
    fields. "Already merged" and "conflict" both leave mainline untouched with
    no merge commit, and a caller that told them apart by inspecting
    `merge_commit` would conflate "nothing to do" with "refused".
    """

    repository_alias: str
    source_branch: str | None
    target_branch: str
    outcome: Outcome
    detail: str
    merge_commit: str | None = None

    @property
    def landed(self) -> bool:
        return self.outcome == LANDED

    @property
    def is_refusal(self) -> bool:
        """Something was wrong and a person has to act.

        `already_merged` and `no_branch` are not refusals: a ticket whose work
        is in mainline already, or which has no branch at all, is a normal
        state of affairs and not a failure of the acceptance.
        """
        return self.outcome not in (LANDED, "already_merged", "no_branch")

    def describe(self) -> str:
        source = self.source_branch or "(no branch)"
        return f"{self.repository_alias}: {source} -> {self.target_branch}: {self.detail}"


def _run(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    identity: tuple[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a git command that may write. Never uses a shell.

    `GIT_OPTIONAL_LOCKS=0` is deliberately *not* set here, unlike the
    read-only path: a write must take git's locks. `GIT_TERMINAL_PROMPT=0`
    makes a missing credential fail at once instead of blocking on a prompt
    nobody is watching — this runs inside `rule accept`, which may be driven
    from a script.
    """
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["GIT_TERMINAL_PROMPT"] = "0"

    config: list[str] = []
    if identity is not None:
        name, email = identity
        # Passed per-invocation rather than written into the clone's config:
        # the identity belongs to this merge, not to a repository.
        config = ["-c", f"user.name={name}", "-c", f"user.email={email}"]

    try:
        return subprocess.run(
            [GIT, *config, *args],
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except FileNotFoundError as exc:
        raise GitUnavailable(
            "the `git` command was not found. Constat shells out to git and "
            "cannot work without it."
        ) from exc


def committer_identity(repo: Repository) -> tuple[str, str] | None:
    """The name and email git would use for a commit made in `repo`.

    Returned as a pair rather than reusing `adapter.configured_identity`, which
    formats one string for a *record of who decided* (D-061). A commit needs
    the two fields separately, and re-splitting that string to recover them
    would break on a name containing an angle bracket.

    None when either is missing. A merge commit attributed to nobody is worse
    than a refused merge: the refusal is fixed in a second, the commit is in
    mainline's history permanently.
    """
    name = _run(["config", "user.name"], cwd=repo.root)
    email = _run(["config", "user.email"], cwd=repo.root)
    if name.returncode != 0 or email.returncode != 0:
        return None
    who, address = name.stdout.strip(), email.stdout.strip()
    if not who or not address:
        return None
    return who, address


def sole_branch(branches: Sequence[str], target: str) -> tuple[str | None, str]:
    """Reduce the refs naming a ticket to the single branch to merge.

    `tickets.branches_naming` returns raw refnames and finds the same branch
    twice — once under `refs/heads/`, once under `refs/remotes/origin/`. Those
    are one branch and collapsing them is correct. Two genuinely different
    names are not: this returns None and the caller refuses, because picking
    one would merge work nobody chose.

    Mainline is dropped. A reference that happens to appear in the mainline
    branch's own name would otherwise ask for mainline to be merged into
    itself.
    """
    short: set[str] = set()
    for ref in branches:
        name = ref
        for prefix in ("refs/heads/", "refs/remotes/"):
            if name.startswith(prefix):
                name = name[len(prefix) :]
                break
        if name.startswith("origin/"):
            name = name[len("origin/") :]
        if not name or name == target or name == "HEAD":
            continue
        short.add(name)

    if not short:
        return None, "no branch names this ticket, so there is nothing to merge"
    if len(short) > 1:
        return None, "several branches name this ticket: " + ", ".join(sorted(short))
    return short.pop(), ""


def merge_ticket_branch(
    repo: Repository,
    alias: str,
    branches: Sequence[str],
    target_branch: str,
    reference: str,
    remote: str = "origin",
) -> MergeResult:
    """Merge the branch naming `reference` into `target_branch` on the remote.

    `branches` is `TicketMatch.branches` — the refs whose name encodes the
    ticket, which is already how D-030 attributes work to a ticket. The branch
    to merge is therefore evidence, not something a user retypes here and
    could mistype.

    Returns a `MergeResult` for every outcome, including the failures. A
    conflict is not exceptional: it is a normal state of a repository, and
    raising for it would make `rule accept` look as though the acceptance
    itself had broken when in fact it is recorded and durable.
    """
    branch, why = sole_branch(branches, target_branch)
    if branch is None:
        outcome: Outcome = "ambiguous_branch" if why.startswith("several") else "no_branch"
        return MergeResult(alias, None, target_branch, outcome, why)

    url = remote_url(repo, remote)
    if url is None:
        return MergeResult(
            alias,
            branch,
            target_branch,
            "no_remote",
            f"{repo.root} has no `{remote}` remote, so there is nowhere to land "
            "the merge. Constat will not merge inside the repository you "
            "registered — it may hold work in progress.",
        )

    identity = committer_identity(repo)
    if identity is None:
        return MergeResult(
            alias,
            branch,
            target_branch,
            "no_identity",
            "git has no user.name and user.email here, so the merge commit "
            "would be attributed to nobody. Set them and merge again.",
        )

    scratch = Path(tempfile.mkdtemp(prefix="constat-merge-"))
    try:
        return _merge_in_clone(
            scratch / "clone",
            url=url,
            alias=alias,
            branch=branch,
            target_branch=target_branch,
            reference=reference,
            remote=remote,
            identity=identity,
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _merge_in_clone(
    clone: Path,
    *,
    url: str,
    alias: str,
    branch: str,
    target_branch: str,
    reference: str,
    remote: str,
    identity: tuple[str, str],
) -> MergeResult:
    def result(outcome: Outcome, detail: str, sha: str | None = None) -> MergeResult:
        return MergeResult(alias, branch, target_branch, outcome, detail, sha)

    # Not shallow. A shallow clone has no merge base, so git would either
    # refuse or merge what look like unrelated histories.
    cloned = _run(["clone", "--quiet", "--branch", target_branch, url, str(clone)])
    if cloned.returncode != 0:
        return result(
            "clone_failed",
            f"could not clone {url} at {target_branch}: "
            f"{cloned.stderr.strip() or 'git clone failed'}. Nothing was merged.",
        )

    source = f"{remote}/{branch}"
    found = _run(["rev-parse", "--verify", "--quiet", f"{source}^{{commit}}"], cwd=clone)
    if found.returncode != 0:
        return result(
            "branch_not_on_remote",
            f"{branch} is not on {remote}. A branch that exists only in a "
            "local clone cannot be merged on the remote; push it first.",
        )

    if _run(["merge-base", "--is-ancestor", source, "HEAD"], cwd=clone).returncode == 0:
        return result(
            "already_merged",
            f"{branch} is already in {target_branch}; nothing to merge.",
        )

    merged = _run(
        [
            "merge",
            "--no-ff",
            "--no-edit",
            "-m",
            MERGE_SUBJECT.format(branch=branch, reference=reference),
            "-m",
            MERGE_BODY,
            source,
        ],
        cwd=clone,
        identity=identity,
    )
    if merged.returncode != 0:
        conflicted = _conflicted_paths(clone)
        # Abort so the clone is left in a defined state. It is about to be
        # deleted either way, but a merge left in progress is a state nothing
        # below should be reading from.
        _run(["merge", "--abort"], cwd=clone)
        if conflicted:
            return result(
                "conflict",
                f"{branch} conflicts with {target_branch} in "
                + ", ".join(conflicted)
                + ". Nothing was pushed. Resolve it and merge in the "
                "repository; the acceptance stands either way.",
            )
        return result(
            "merge_failed",
            f"could not merge {branch} into {target_branch}: "
            f"{merged.stderr.strip() or merged.stdout.strip() or 'git merge failed'}. "
            "Nothing was pushed.",
        )

    head = _run(["rev-parse", "HEAD"], cwd=clone).stdout.strip() or None

    pushed = _run(
        ["push", "--quiet", remote, f"HEAD:refs/heads/{target_branch}"], cwd=clone
    )
    if pushed.returncode != 0:
        return result(
            "push_failed",
            f"merged cleanly but could not push to {url}: "
            f"{pushed.stderr.strip() or 'git push failed'}. {target_branch} is "
            "unchanged — the merge existed only in a temporary clone, which has "
            "been removed.",
            head,
        )

    return result(LANDED, f"merged {branch} into {target_branch} and pushed to {url}", head)


def _conflicted_paths(clone: Path) -> tuple[str, ...]:
    """Paths git reports as unmerged, so the refusal can name them."""
    listed = _run(["diff", "--name-only", "--diff-filter=U"], cwd=clone)
    if listed.returncode != 0:
        return ()
    return tuple(line.strip() for line in listed.stdout.split("\n") if line.strip())
