"""Read-only Git access.

Everything in this package shells out to the `git` binary rather than
reimplementing Git (D-002), and is strictly read-only (PRODUCT_SPEC.md rule 7).
"""

from .adapter import (
    MainlineRef,
    Repository,
    Revision,
    discover_repository,
    local_branches,
    resolve_default_branch,
    resolve_mainline,
    resolve_revision,
    root_commits,
)
from .branching import BranchingSignal, inspect_branching
from .diff import (
    ChangeSummary,
    ChangeType,
    FileChange,
    StateSummary,
    compare_revisions,
    find_merge_base,
    summarise_state,
)

__all__ = [
    "BranchingSignal",
    "ChangeSummary",
    "MainlineRef",
    "ChangeType",
    "FileChange",
    "Repository",
    "Revision",
    "StateSummary",
    "compare_revisions",
    "discover_repository",
    "local_branches",
    "resolve_default_branch",
    "root_commits",
    "find_merge_base",
    "inspect_branching",
    "resolve_mainline",
    "resolve_revision",
    "summarise_state",
]
