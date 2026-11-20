"""Cloning a remote into the workspace's own cache (CON-35, D-092).

**Why this is a separate module.** `adapter.py` must keep its read-only
guarantee (D-002, D-062) and `merge.py` is the only writer *to a subject
repository*. Cloning writes too, but somewhere else entirely: inside Constat's
own workspace directory. Three writers with three different reaches is only
legible if each lives in its own file, so the next person reading
`constat/git/` can see the reach from the layout.

**This does not widen the subject-repository guarantee.** ARCHITECTURE § 6 says
Constat is read-only against every repository it reads, with one opt-in
exception for publishing (D-058) and one for `merge_on_accept` (D-062). A cache
clone writes *nothing* to the remote: it is a read, with the result kept. The
remote is never pushed to, never fetched into, never modified.

**A clone with no checkout — and not a mirror, which was the first attempt.**
`--mirror` looks like the obvious choice: every ref, no working tree, smallest
cache. It breaks Constat. A mirror puts the remote's branches straight into
`refs/heads/*` and has no remote-tracking namespace at all, so
`refs/remotes/origin/HEAD` does not exist — and D-028 resolves the default
branch from exactly that ref, while D-068 resolves mainline from
`origin/<branch>`. Fourteen tests failed on the first run for this one reason.

`--no-checkout` gives both halves: a normal clone, with `origin/HEAD` and the
remote-tracking refs the read-only layer expects, and an unmaterialised working
tree so a large repository costs its history and not its files. The cache then
behaves *exactly* like a local clone, which is what § 6 promised — "read with
the same read-only Git layer".

**No credentials are stored, ever.** The clone uses git's own helpers, exactly
as `merge.py` does for its push. A URL that needs authentication Constat cannot
supply fails as a clone failure, with git's own message, and nothing is
remembered.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from ..errors import RepositoryError
from .adapter import run_git

REMOTE_FORMS = (
    re.compile(r"^https?://"),
    re.compile(r"^(?:git|ssh)://"),
    re.compile(r"^file://"),
    # scp-like: git@host:owner/repo
    re.compile(r"^[\w.-]+@[\w.-]+:"),
)
"""The forms a remote may take.

Deliberately a list rather than "anything that is not a directory": a mistyped
path must fail as a missing path, not be cloned from as a URL. Recognising
nothing is the refusal, which is the posture D-020 set for an ambiguous
revision — refuse rather than guess.
"""


def looks_remote(source: str) -> bool:
    """Whether `source` is a remote URL rather than a path on disk."""
    return any(form.match(source) for form in REMOTE_FORMS)


def cache_name(source: str) -> str:
    """A directory name for a remote, derived from its URL.

    The last path segment without `.git` — `billing` for
    `https://example.invalid/team/billing.git`. Sanitised to the characters a
    directory name can safely hold, because a URL can contain almost anything
    and this becomes a path inside the workspace.

    The name is a convenience, never an identity: identity is the root commit
    (D-025), read after the clone.
    """
    tail = source.rstrip("/").rsplit("/", 1)[-1]
    tail = tail.rsplit(":", 1)[-1]
    if tail.endswith(".git"):
        tail = tail[: -len(".git")]
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", tail).strip("-._")
    return cleaned or "repository"


def clone(source: str, into: Path) -> Path:
    """Clone `source` into `into` without a checkout, and return the directory.

    Refuses rather than overwriting when the target exists: a directory already
    there means either a half-finished clone from a failed run or a name
    collision, and quietly replacing it would destroy whichever it is.

    On failure the partial clone is removed. A directory that looks like a
    cached repository but is not one would be read on the next run as an
    unreadable repository, which reads as rules whose anchors have vanished —
    the symptom D-070 warns produces a false retirement candidate.
    """
    if into.exists():
        raise RepositoryError(
            f"{into} already exists, so the clone would overwrite it. Remove it "
            "by hand if it is left over from a failed registration."
        )

    into.parent.mkdir(parents=True, exist_ok=True)
    result = run_git(
        ["clone", "--no-checkout", "--quiet", source, str(into)], cwd=into.parent
    )
    if result.returncode != 0:
        shutil.rmtree(into, ignore_errors=True)
        raise RepositoryError(
            f"could not clone {source}: {result.stderr.strip() or 'git failed'}. "
            "Nothing was registered, and no partial clone was kept. Credentials "
            "come from git's own helpers — Constat stores none."
        )
    return into


def discard(cache_path: str | Path) -> None:
    """Delete a cached clone.

    Used when registration is refused after cloning — a duplicate identity, for
    instance, which cannot be known until the clone exists. Leaving the
    directory behind would make the next attempt fail on `clone`'s own
    exists-check for a reason the user never caused.
    """
    shutil.rmtree(Path(cache_path), ignore_errors=True)


def fetch(cache_path: str | Path) -> None:
    """Refresh a cached clone from its remote.

    Updates the remote-tracking refs, which is what Constat reads: mainline is
    `origin/<branch>` (D-068), so the cache's own local branches are not the
    picture and are deliberately left where they are. Failure raises: a cache that silently did not refresh would present
    stale evidence as current, and CON-38 exists to disclose cache age for
    exactly this reason.
    """
    path = Path(cache_path)
    result = run_git(["fetch", "--prune", "--quiet", "origin"], cwd=path)
    if result.returncode != 0:
        raise RepositoryError(
            f"could not refresh the cache at {path}: "
            f"{result.stderr.strip() or 'git failed'}. The cached copy is "
            "unchanged, so what it holds is as old as its last successful fetch."
        )
