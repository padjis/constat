"""The repository registry (D-027, CON-32, CON-35).

Add, list and remove the repositories a workspace knows about. Registration
resolves and stores two things that must not be re-guessed later: the
repository's durable identity (D-025) and its default branch (D-028).

**A remote is cloned into the workspace's own cache** (CON-35, D-092). `source`
stays the URL the user typed — the record of where the repository came from —
and `cache_path` is where it lives on disk. Callers open `local_path`, never
`source`, because for a remote no Git command can open the latter.

**Identity is only knowable after the clone**, since it is the root commit
(D-025). So a duplicate remote is detected *after* cloning and the clone is
then discarded, which costs a clone to learn something no URL comparison could
tell: two different URLs can be the same repository, and the same URL can be
typed two ways.
"""

from __future__ import annotations

from datetime import datetime

from pathlib import Path

from ..errors import AlreadyRegistered, NotRegistered
from ..git.adapter import Repository, discover_repository, resolve_default_branch, root_commits
from ..git.adapter import Revision
from ..git import cache
from ..git.branching import BranchingSignal, inspect_branching
from ..models import RegisteredRepository
from .workspace import Workspace, utc_now

CACHE_DIRECTORY = "cache"
"""Where clones live, inside the workspace directory.

Inside rather than beside, so one `rm -r` removes everything Constat owns and
nothing it does not. A cache in a separate location would outlive the workspace
that knows about it, leaving clones nobody can account for.
"""


def _row_to_model(row) -> RegisteredRepository:
    return RegisteredRepository(
        alias=row["alias"],
        source=row["source"],
        source_kind=row["source_kind"],
        identity=row["identity"],
        default_branch=row["default_branch"],
        added_at=datetime.fromisoformat(row["added_at"]),
        cache_path=row["cache_path"],
        last_fetched_at=(
            datetime.fromisoformat(row["last_fetched_at"])
            if row["last_fetched_at"]
            else None
        ),
    )


def _identity_of(repo: Repository, default_branch: str) -> str:
    """The repository's durable identity, read from the default branch."""
    tip = Revision(symbolic=default_branch, sha=_resolve(repo, default_branch))
    return min(root_commits(repo, tip))


def _resolve(repo: Repository, symbolic: str) -> str:
    from ..git.adapter import resolve_revision

    return resolve_revision(repo, symbolic).sha


class Registry:
    """Repositories known to a workspace."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def add(
        self,
        path: str,
        alias: str | None = None,
        default_branch: str | None = None,
    ) -> RegisteredRepository:
        """Register a local path or a remote URL.

        Raises the existing repository errors for a bad path, so "that is not a
        repository" is reported the same way everywhere. A remote is cloned
        into the workspace cache first (CON-35); anything that is neither an
        openable path nor a recognised remote form is refused rather than
        guessed at.
        """
        if cache.looks_remote(path):
            return self._add_remote(path, alias, default_branch)

        repo = discover_repository(path)
        branch = default_branch or resolve_default_branch(repo)
        identity = _identity_of(repo, branch)
        name = alias or repo.root.name

        existing = self.find_by_identity(identity)
        if existing is not None:
            raise AlreadyRegistered(
                f"this repository is already registered as {existing.alias!r} "
                f"({existing.source}). It is the same repository: both share "
                f"root commit {identity[:12]}. Remove the existing entry first "
                "if you mean to re-register it."
            )
        if self.find(name) is not None:
            raise AlreadyRegistered(
                f"an unrelated repository is already registered as {name!r}. "
                "Choose another alias with --name."
            )

        self._workspace.execute(
            "INSERT INTO repository "
            "(alias, source, source_kind, cache_path, identity, "
            " default_branch, added_at) "
            "VALUES (?, ?, 'local', NULL, ?, ?, ?)",
            (name, str(repo.root), identity, branch, utc_now()),
        )
        found = self.find(name)
        assert found is not None  # just inserted
        return found

    def _add_remote(
        self, url: str, alias: str | None, default_branch: str | None
    ) -> RegisteredRepository:
        """Clone a remote into the cache and register it.

        The ordering is the design, and it mirrors D-062's: the clone happens
        first because nothing about the repository — not its identity, not its
        default branch — can be known without it, and the clone is **discarded
        again** if registration is then refused. A refusal must not leave a
        directory behind that the next attempt trips over.
        """
        name = alias or cache.cache_name(url)
        if self.find(name) is not None:
            raise AlreadyRegistered(
                f"an unrelated repository is already registered as {name!r}. "
                "Choose another alias with --name."
            )

        destination = Path(self._workspace.home) / CACHE_DIRECTORY / name
        cache.clone(url, destination)

        try:
            repo = discover_repository(str(destination))
            branch = default_branch or resolve_default_branch(repo)
            identity = _identity_of(repo, branch)

            existing = self.find_by_identity(identity)
            if existing is not None:
                raise AlreadyRegistered(
                    f"this repository is already registered as "
                    f"{existing.alias!r} ({existing.source}). It is the same "
                    f"repository: both share root commit {identity[:12]}. Two "
                    "different URLs can point at one repository, which is why "
                    "this is only knowable after cloning."
                )
        except Exception:
            # Including the duplicate above. The clone was made to learn the
            # identity; if the answer is "we already have this", the copy has
            # served its purpose and keeping it would be a directory nobody
            # can account for.
            cache.discard(destination)
            raise

        now = utc_now()
        self._workspace.execute(
            "INSERT INTO repository "
            "(alias, source, source_kind, cache_path, identity, "
            " default_branch, added_at, last_fetched_at) "
            "VALUES (?, ?, 'remote', ?, ?, ?, ?, ?)",
            (name, url, str(destination), identity, branch, now, now),
        )
        found = self.find(name)
        assert found is not None  # just inserted
        return found

    def branching_of(self, entry: RegisteredRepository) -> BranchingSignal:
        """What branching model a registered repository looks like it uses.

        Deliberately **not** folded into `add`'s return value (CON-97). Adding
        a second field there would change the type every caller already
        depends on, for a signal only registration reads — and it is a read,
        so a caller that wants it can ask later. `repo list` is the obvious
        second caller and is not one yet.

        Opened through `local_path`, never `source`: the cache for a remote,
        the registered path for a local one (D-092).
        """
        repo = discover_repository(entry.local_path)
        return inspect_branching(repo, entry.default_branch)

    def refresh(self, alias: str) -> RegisteredRepository:
        """Fetch a cached remote again, and record when.

        Refuses for a local path rather than pretending to succeed: there is no
        cache to refresh, and a recorded fetch time would be a claim about a
        copy that does not exist.
        """
        found = self.find(alias)
        if found is None:
            known = ", ".join(r.alias for r in self.list()) or "none"
            raise NotRegistered(
                f"no repository registered as {alias!r}. Registered: {known}."
            )
        if found.cache_path is None:
            raise NotRegistered(
                f"{alias!r} is a local path ({found.source}), not a cached "
                "remote. There is nothing to fetch: it is read where it is."
            )

        cache.fetch(found.cache_path)
        self._workspace.execute(
            "UPDATE repository SET last_fetched_at = ? WHERE alias = ?",
            (utc_now(), alias),
        )
        refreshed = self.find(alias)
        assert refreshed is not None
        return refreshed

    def find(self, alias: str) -> RegisteredRepository | None:
        row = self._workspace.execute(
            "SELECT * FROM repository WHERE alias = ?", (alias,)
        ).fetchone()
        return _row_to_model(row) if row else None

    def find_by_identity(self, identity: str) -> RegisteredRepository | None:
        row = self._workspace.execute(
            "SELECT * FROM repository WHERE identity = ?", (identity,)
        ).fetchone()
        return _row_to_model(row) if row else None

    def list(self) -> tuple[RegisteredRepository, ...]:
        rows = self._workspace.execute(
            "SELECT * FROM repository ORDER BY alias"
        ).fetchall()
        return tuple(_row_to_model(row) for row in rows)

    def remove(self, alias: str) -> RegisteredRepository:
        """Unregister a repository.

        Removes Constat's knowledge of it and nothing else: the repository on
        disk is untouched, because Constat is read-only against it.
        """
        found = self.find(alias)
        if found is None:
            known = ", ".join(r.alias for r in self.list()) or "none"
            raise NotRegistered(
                f"no repository registered as {alias!r}. Registered: {known}."
            )
        self._workspace.execute("DELETE FROM repository WHERE alias = ?", (alias,))
        if found.cache_path is not None:
            # The clone is Constat's own copy, so removing the registration
            # removes it. A local path is untouched for the opposite reason:
            # it is not ours.
            cache.discard(found.cache_path)
        return found
