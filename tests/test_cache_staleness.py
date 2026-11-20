"""Every document says how current its copy of each repository is (CON-38, D-093).

D-027 put this next to bounded excerpts on purpose: **unstated staleness is the
same class of failure as unstated truncation.** A document that reads as current
while resting on a week-old cache is confidently wrong about the present, which
is the failure product rule 1 exists to prevent.

It was impossible until CON-35, because there was no cache to be stale.

Three properties carry these tests:

1. **Stated for every repository, judged for none.** There is no staleness
   threshold and there should not be: "older than a week is stale" is a
   judgement about somebody's release cadence. D-027 asked for disclosure, and
   CON-76 set the posture — report the count, leave the conclusion to a person.
2. **A local path says so too.** It is read in place, so nothing can be stale —
   and saying that costs one clause and stops a missing fetch time reading as a
   missing field.
3. **An unrecorded fetch is not a recent one.** It reports that the age cannot
   be said, rather than defaulting to current.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from constat.operations import (
    collect,
    describe_age,
    describe_freshness,
    gather,
    product_state,
    render,
    render_state,
)
from constat.store import Registry, TicketStore, Workspace

from helpers import commit_file, git


REFERENCE = "700"


def _origin(tmp_path: Path, name: str) -> Path:
    bare = tmp_path / f"{name}.git"
    bare.mkdir()
    git(bare, "init", "--bare", "--quiet", "--initial-branch=main")
    work = tmp_path / f"{name}-work"
    git(tmp_path, "clone", "--quiet", str(bare), f"{name}-work")
    git(work, "config", "user.name", "Test Fixture")
    git(work, "config", "user.email", "fixture@example.invalid")
    commit_file(work, "rules.py", "LIMIT = 100\n", "Initial")
    git(work, "push", "--quiet", "origin", "main")
    git(work, "checkout", "--quiet", "-b", f"feat/{REFERENCE}-raise")
    commit_file(work, "rules.py", "LIMIT = 250\n", f"{REFERENCE}: raise the limit")
    git(work, "push", "--quiet", "origin", f"feat/{REFERENCE}-raise")
    git(bare, "symbolic-ref", "HEAD", "refs/heads/main")
    return bare


@pytest.fixture
def cached(tmp_path: Path):
    """A workspace whose only repository is a cached remote."""
    origin = _origin(tmp_path, "billing")
    with Workspace.create(tmp_path / "ws") as ws:
        entry = Registry(ws).add(f"file://{origin}")
        TicketStore(ws).add(REFERENCE)
        yield ws, entry


@pytest.fixture
def local(tmp_path: Path):
    """A workspace whose only repository is a local path."""
    origin = _origin(tmp_path, "billing")
    git(tmp_path, "clone", "--quiet", str(origin), "checkout")
    with Workspace.create(tmp_path / "ws") as ws:
        entry = Registry(ws).add(str(tmp_path / "checkout"), alias="billing")
        TicketStore(ws).add(REFERENCE)
        yield ws, entry


# -- the wording --------------------------------------------------------------


class TestDescribeAge:
    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (0, "just now"),
            (30, "just now"),
            (600, "10 minutes ago"),
            (3600, "1 hour ago"),
            (7200, "2 hours ago"),
            (86400, "1 day ago"),
            (86400 * 9, "9 days ago"),
        ],
    )
    def test_it_is_coarse_on_purpose(self, seconds, expected) -> None:
        """The reader's question is "is this old enough to matter". False
        precision invites a confidence the number does not carry."""
        now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
        assert describe_age(now - timedelta(seconds=seconds), now) == expected

    def test_a_future_timestamp_does_not_read_as_negative(self) -> None:
        """A clock skew between machines should not produce "-3 days ago"."""
        now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
        assert describe_age(now + timedelta(hours=5), now) == "just now"


class TestDescribeFreshness:
    def test_a_cache_says_when_it_was_fetched_and_that_nothing_refreshes_it(
        self, cached
    ) -> None:
        _workspace, entry = cached

        said = describe_freshness(entry)

        assert "cache fetched" in said
        assert "just now" in said
        assert "Nothing refreshes it on its own" in said
        assert "repo fetch" in said

    def test_a_local_path_says_it_is_read_in_place(self, local) -> None:
        """So the absence of a fetch time reads as "there is no cache" rather
        than as a missing field."""
        _workspace, entry = local

        said = describe_freshness(entry)

        assert "Read in place" in said
        assert "cache" not in said.lower()

    def test_an_unrecorded_fetch_is_not_reported_as_current(self, cached) -> None:
        """An unknown age is not a recent one. Cannot happen today — no path
        writes a cache without a fetch time — and reported rather than assumed
        because that is the posture D-031 set for exactly this ambiguity."""
        _workspace, entry = cached
        without = entry.model_copy(update={"last_fetched_at": None})

        said = describe_freshness(without)

        assert "never recorded" in said
        assert "cannot be said" in said

    def test_no_threshold_is_applied(self, cached) -> None:
        """Deliberate. "Older than a week is stale" is a judgement about
        somebody's release cadence, and D-027 asked for disclosure rather than
        a verdict — CON-76's posture for mainline drift, applied here."""
        _workspace, entry = cached
        old = entry.model_copy(
            update={
                "last_fetched_at": datetime.now(timezone.utc) - timedelta(days=400)
            }
        )

        said = describe_freshness(old)

        assert "400 days ago" in said
        for verdict in ("stale", "out of date", "too old", "warning"):
            assert verdict not in said.lower()


# -- where it appears ---------------------------------------------------------


class TestTheDocumentSaysIt:
    def test_a_cached_repository_states_its_age(self, cached) -> None:
        workspace, _entry = cached
        gather(workspace, REFERENCE)

        body = render(REFERENCE, collect(workspace, REFERENCE))

        assert "Read from a cache fetched just now" in body
        assert "as old as that" in body

    def test_a_local_repository_states_that_too(self, local) -> None:
        workspace, _entry = local
        gather(workspace, REFERENCE)

        body = render(REFERENCE, collect(workspace, REFERENCE))

        assert "Read in place" in body

    def test_it_sits_beside_what_the_evidence_was_measured_against(
        self, cached
    ) -> None:
        """Both answer "how much should I trust this": one names the ref, the
        other says how old the copy of it is."""
        workspace, _entry = cached
        gather(workspace, REFERENCE)

        body = render(REFERENCE, collect(workspace, REFERENCE))
        measured = body.index("Measured against")
        freshness = body.index("Read from a cache fetched")

        assert 0 < freshness - measured < 200


class TestTheProductStateSaysIt:
    def test_a_cached_repository_is_marked_in_the_state(self, cached) -> None:
        """This view's whole claim is to be of the revisions it names, and a
        picture assembled from a week-old cache is a picture of last week."""
        workspace, _entry = cached

        rendered = render_state(product_state(workspace))

        assert "read from a cache fetched just now" in rendered
        assert "nothing refreshes it on its own" in rendered

    def test_a_local_repository_is_not_marked(self, local) -> None:
        """Nothing to disclose: there is no cache, and a line saying so in a
        list of repositories would be noise rather than honesty."""
        workspace, _entry = local

        rendered = render_state(product_state(workspace))

        assert "read from a cache" not in rendered

    def test_the_state_carries_the_timestamp(self, cached) -> None:
        workspace, _entry = cached

        state = product_state(workspace)

        assert state.repositories[0].fetched_at is not None

    def test_a_local_path_carries_none(self, local) -> None:
        workspace, _entry = local

        state = product_state(workspace)

        assert state.repositories[0].fetched_at is None
