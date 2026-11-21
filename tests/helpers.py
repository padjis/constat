"""Helpers for building throwaway repositories and catalogue state in tests.

Kept out of conftest.py so they can be imported explicitly rather than arriving
as fixtures. Tests must not depend on the real subject repositories being
present, or on anything about the machine running them.

**Why the catalogue seeding lives here.** `Catalogue` used to carry
`add_rule`, `add_behaviour` and `add_anchor`. No CLI or MCP path ever reached
them — a rule is created only by `Review.accept` (D-048) — so they were a
writable door into the governance store that production could not use and
nothing guarded. They now live here, where a writable door is harmless, and
`Catalogue` is read-only.

Seeding writes rows directly, on purpose. A test about `rules_matching` or
`unmatched_paths` does not care how the rule got there, and routing every
fixture through a rule proposal and an acceptance would make those tests
slower and about something else. Tests that *are* about how a rule comes to
exist use `Review.accept`, which is the real path.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# Committing requires an identity, and the machine's own config must not leak
# into fixtures. Passed per-invocation rather than written to a config file.
IDENTITY = [
    "-c",
    "user.name=Test Fixture",
    "-c",
    "user.email=fixture@example.invalid",
    "-c",
    "commit.gpgsign=false",
]


def git(repo: Path, *args: str) -> str:
    """Run git in `repo` and return stdout, raising on failure."""
    result = subprocess.run(
        ["git", *IDENTITY, *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def commit_file(repo: Path, name: str, content: str, message: str) -> str:
    """Write a file, commit it, and return the commit SHA."""
    (repo / name).write_text(content)
    git(repo, "add", name)
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


# -- catalogue seeding --------------------------------------------------------


def seed_rule(
    workspace,
    name: str,
    statement: str = "A seeded business rule.",
    behaviours: tuple[str, ...] = (),
    anchors: tuple = (),
) -> int:
    """Put a rule in the catalogue directly, and return its id.

    `anchors` takes either a glob or a `(glob, repository_alias)` pair. An
    unknown alias is stored as an unscoped anchor rather than refused: this is
    a fixture, and validating a test's own input is not its job.
    """
    cursor = workspace.execute(
        "INSERT INTO rule (name, statement, created_at) VALUES (?, ?, ?)",
        (name, statement, _now()),
    )
    rule_id = int(cursor.lastrowid)

    for description in behaviours:
        seed_behaviour(workspace, name, description)
    for anchor in anchors:
        if isinstance(anchor, str):
            seed_anchor(workspace, name, anchor)
        else:
            seed_anchor(workspace, name, *anchor)
    return rule_id


def seed_behaviour(workspace, rule_name: str, description: str) -> None:
    """Add one behaviour to a seeded rule."""
    workspace.execute(
        "INSERT INTO behaviour (rule_id, description, created_at) VALUES (?, ?, ?)",
        (_rule_id(workspace, rule_name), description, _now()),
    )


def seed_anchor(
    workspace, rule_name: str, path_glob: str, repository_alias: str | None = None
) -> None:
    """Add one anchor to a seeded rule, optionally scoped to a repository."""
    repository_id = None
    if repository_alias is not None:
        row = workspace.execute(
            "SELECT id FROM repository WHERE alias = ?", (repository_alias,)
        ).fetchone()
        repository_id = int(row["id"]) if row is not None else None
    workspace.execute(
        "INSERT INTO anchor (rule_id, repository_id, path_glob, created_at) "
        "VALUES (?, ?, ?, ?)",
        (_rule_id(workspace, rule_name), repository_id, path_glob, _now()),
    )


def _rule_id(workspace, name: str) -> int:
    row = workspace.execute(
        "SELECT id FROM rule WHERE name = ? ORDER BY id DESC LIMIT 1", (name,)
    ).fetchone()
    if row is None:
        raise AssertionError(f"test fixture error: no seeded rule named {name!r}")
    return int(row["id"])


def _now() -> str:
    from constat.store.workspace import utc_now

    return utc_now()


# -- winding a workspace back for migration tests -----------------------------

APPEND_ONLY_TRIGGERS = {
    "rule_proposal": (
        "rule_proposal_is_append_only_update",
        "BEFORE UPDATE ON rule_proposal BEGIN "
        "SELECT RAISE(ABORT, 'rule_proposal is append-only: a reading "
        "cannot be edited'); END",
    ),
}
"""Triggers that must come off before a column can be dropped, and go back on
after. Only the ones a rewind actually trips."""

INTRODUCED_AT: dict[int, tuple[tuple[str, str], ...]] = {
    21: (("rule_version", "release_id"),),
    8: (("rule_proposal_decision", "attribution"),),
    10: (("rule_proposal", "relation"),),
    11: (
        ("rule_proposal", "area"),
        ("rule", "area"),
        ("rule_version", "area"),
    ),
    12: (
        ("rule_proposal_anchor", "grounded_in"),
        ("anchor", "grounded_in"),
        ("rule_version_anchor", "grounded_in"),
    ),
    17: (("rule", "ref"),),
    15: (
        ("behaviour", "behaviour_no"),
        ("example", "example_no"),
        ("rule_version_behaviour", "behaviour_no"),
        ("rule_version_example", "example_no"),
    ),
}
"""Columns each schema version added, keyed by the version they first exist in.

**Add an entry here when you add a migration.** A migration test builds a real
workspace and winds it back, because hand-written DDL for an old schema tests
the transcription rather than the migration — but winding back means undoing
every later addition, and three separate tests were each doing that by hand.
The third new migration in a row broke all of them, which is what this exists
to stop."""

TABLES_INTRODUCED_AT: dict[int, tuple[str, ...]] = {
    22: ("requirement",),
    21: ("release",),
    8: ("setting",),
    13: ("run_commit",),
    14: ("rule_proposal_example", "rule_version_example", "example"),
    16: ("area",),
    20: ("checkpoint_rule", "checkpoint"),
    19: ("rule_retirement",),
    18: (
        "message",
        "rule_message",
        "rule_proposal_message",
        "rule_version_message",
    ),
}


def rewind_workspace(db: Path, to_version: int) -> None:
    """Make a current workspace look like one created at `to_version`.

    Drops every column and table introduced after that version and sets
    `schema_meta`, so opening it runs the real migrations.
    """
    import sqlite3

    connection = sqlite3.connect(db)
    try:
        dropped_triggers: set[str] = set()
        for version, columns in sorted(INTRODUCED_AT.items(), reverse=True):
            if version <= to_version:
                continue
            for table, column in columns:
                if table in APPEND_ONLY_TRIGGERS and table not in dropped_triggers:
                    name, _ = APPEND_ONLY_TRIGGERS[table]
                    connection.execute(f"DROP TRIGGER IF EXISTS {name}")
                    dropped_triggers.add(table)
                # SQLite refuses to drop an indexed column, so any index
                # mentioning it comes off first. Discovered rather than listed:
                # a map of index names would be one more thing to remember on
                # the next migration, which is what this helper exists to stop.
                for (index_name,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index' "
                    "AND tbl_name = ? AND sql LIKE ?",
                    (table, f"%{column}%"),
                ).fetchall():
                    connection.execute(f"DROP INDEX IF EXISTS {index_name}")
                connection.execute(f"ALTER TABLE {table} DROP COLUMN {column}")

        for version, tables in sorted(TABLES_INTRODUCED_AT.items(), reverse=True):
            if version <= to_version:
                continue
            for table in tables:
                connection.execute(f"DROP TABLE IF EXISTS {table}")

        for table in dropped_triggers:
            name, body = APPEND_ONLY_TRIGGERS[table]
            connection.execute(f"CREATE TRIGGER {name} {body}")

        connection.execute(
            "UPDATE schema_meta SET schema_version = ? WHERE id = 1", (to_version,)
        )
        connection.commit()
    finally:
        connection.close()
