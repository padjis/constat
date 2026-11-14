"""The MCP loop can start from the agent (CON-64, D-063).

`gather_evidence` used to raise `no ticket '622'` unless a person had already
run `constat ticket add 622` at the command line. The agent's own workflow
therefore failed at its first step on a clean workspace, and nothing in the
interface mentioned the prerequisite.

Two properties are in tension here, and both are tested:

- a reference the repositories **recognise** opens a ticket, so the loop runs;
- a reference that matches **nothing anywhere** is still refused, so a typo
  does not become a permanent empty ticket the workspace then declines to open
  again.

The third property is an absence, as in `test_mcp.py`: the tool list did not
grow. That is the whole argument for this change being compatible with D-055 —
a precondition was removed from a tool that already gathered, rather than a
capability added to the four.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from constat.cli import main
from constat.errors import NotRegistered, ReferenceMatchedNothing
from constat.operations import collect, gather
from constat.store import Registry, TicketStore, Workspace

from helpers import commit_file, git
from test_runs import distinct_subject

pytest.importorskip("mcp", reason="the MCP server is an optional extra")

from constat.mcp import EXPOSED_TOOLS, build_server  # noqa: E402
from test_mcp import call, json_of, text_of  # noqa: E402


def refusal(home: str, tool: str, **arguments) -> str:
    """Call a tool expecting it to refuse, and return the message.

    In process a tool raises `ToolError`; a real client receives `is_error`
    with the same text. `test_mcp.py` covers that equivalence end to end, so
    asserting on the message here is asserting on what a client would read.
    """
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError) as exc:
        call(home, tool, **arguments)
    return str(exc.value)


@pytest.fixture
def clean(tmp_path: Path) -> str:
    """A workspace with one repository and **no tickets at all**.

    The difference from `test_mcp.py`'s `home` is the point: that fixture runs
    `ticket add` first, which is exactly the step this ticket removes.
    """
    ws = str(tmp_path / "ws")
    main(["--workspace", ws, "init"])
    clone = distinct_subject(tmp_path, "billing", "LIMIT = 250\n")
    main(["--workspace", ws, "repo", "add", str(clone), "--name", "billing"])
    return ws


@pytest.fixture
def landed_only(tmp_path: Path) -> str:
    """A workspace where reference 700 exists only on mainline.

    `LANDED` contributes no evidence and is still a match (D-031). A ticket for
    already-shipped work is about something real.
    """
    ws = str(tmp_path / "ws")
    main(["--workspace", ws, "init"])

    source = tmp_path / "shipped-src"
    source.mkdir()
    git(source, "init", "--initial-branch=main", "--quiet")
    commit_file(source, "rules.py", "LIMIT = 100\n", "Initial (shipped)")
    commit_file(source, "rules.py", "LIMIT = 250\n", "Raise the limit (#700)")

    # Explicit, because this one is not a clone and so has no origin/HEAD to
    # derive the default branch from. Constat refuses to guess it (D-016).
    main(
        [
            "--workspace", ws, "repo", "add", str(source),
            "--name", "shipped", "--default-branch", "main",
        ]
    )
    return ws


def tickets(home: str) -> list[str]:
    with Workspace.open(home) as workspace:
        return [t.reference for t in TicketStore(workspace).list()]


class TestAReferenceTheRepositoriesRecogniseOpensATicket:
    def test_gather_evidence_opens_a_ticket_that_does_not_exist(self, clean: str):
        assert tickets(clean) == []

        result = call(clean, "gather_evidence", reference="622")

        assert not result.is_error, text_of(result)
        assert tickets(clean) == ["622"]

    def test_the_caller_is_told_the_ticket_was_opened(self, clean: str):
        """Silently acquiring a ticket is not something to leave unsaid."""
        body = json_of(call(clean, "gather_evidence", reference="622"))
        assert body["ticket_opened"] is True

    def test_the_evidence_is_gathered_and_not_merely_the_ticket_opened(
        self, clean: str
    ):
        body = json_of(call(clean, "gather_evidence", reference="622"))

        assert body["repositories_contributing"] == 1
        assert body["repositories"][0]["commits"] == 1

    def test_the_opened_ticket_has_a_filled_document(self, clean: str):
        """An opened ticket with an empty document says nothing. The CLI's
        `ticket add` gathers immediately for the same reason."""
        call(clean, "gather_evidence", reference="622")

        with Workspace.open(clean) as workspace:
            assert TicketStore(workspace).document("622").body != ""

    def test_the_payload_is_readable_straight_afterwards(self, clean: str):
        """The loop's second step, with no command-line detour in between —
        which is the done-when criterion for the ticket."""
        call(clean, "gather_evidence", reference="622")

        result = call(clean, "get_payload", reference="622")

        assert not result.is_error, text_of(result)

    def test_a_landed_only_reference_opens_a_ticket(self, landed_only: str):
        """Found in mainline, contributing no evidence, and still a match."""
        body = json_of(call(landed_only, "gather_evidence", reference="700"))

        assert body["repositories"][0]["status"] == "landed"
        assert body["ticket_opened"] is True
        assert tickets(landed_only) == ["700"]


class TestAnExistingTicketIsNotReopened:
    def test_a_known_ticket_is_used_rather_than_opened(self, clean: str):
        main(["--workspace", clean, "ticket", "add", "622", "--no-provider"])

        body = json_of(call(clean, "gather_evidence", reference="622"))

        assert body["ticket_opened"] is False
        assert tickets(clean) == ["622"]

    def test_gathering_twice_does_not_refuse_the_second_time(self, clean: str):
        """`TicketStore.add` raises `AlreadyRegistered`. Reaching it on the
        second run would turn a working tool into a single-use one."""
        first = call(clean, "gather_evidence", reference="622")
        second = call(clean, "gather_evidence", reference="622")

        assert not first.is_error, text_of(first)
        assert not second.is_error, text_of(second)
        assert json_of(second)["ticket_opened"] is False
        assert tickets(clean) == ["622"]


class TestAReferenceMatchingNothingIsStillRefused:
    def test_an_unknown_reference_is_refused(self, clean: str):
        assert "matched no commits" in refusal(
            clean, "gather_evidence", reference="999"
        )

    def test_the_refusal_leaves_no_ticket_behind(self, clean: str):
        """The reason the refusal has to survive at all. An empty ticket for a
        typo cannot be opened again — `ticket add` refuses a duplicate — so it
        is worse than no ticket."""
        refusal(clean, "gather_evidence", reference="999")

        assert tickets(clean) == []

    def test_the_refusal_says_how_to_open_one_deliberately(self, clean: str):
        """A refusal that names no way forward is the D-060 failure."""
        assert "ticket add 999" in refusal(
            clean, "gather_evidence", reference="999"
        )

    def test_the_refusal_names_how_many_repositories_were_searched(
        self, clean: str
    ):
        """"Nothing matched" is a claim about coverage, so the coverage is
        stated rather than implied (D-038)."""
        assert "searched 1 repository(ies)" in refusal(
            clean, "gather_evidence", reference="999"
        )


class TestAnUnreadableRepositoryIsNotEvidenceOfAbsence:
    """A repository that cannot be read reports `NOT_FOUND` with an `error`
    set, which is indistinguishable by status from a genuine miss. Treating it
    as a miss would open a ticket on an assumption about the one repository
    nobody looked in (product rule 1)."""

    @pytest.fixture
    def broken(self, tmp_path: Path) -> str:
        ws = str(tmp_path / "ws")
        main(["--workspace", ws, "init"])
        clone = distinct_subject(tmp_path, "billing", "LIMIT = 250\n")
        main(["--workspace", ws, "repo", "add", str(clone), "--name", "billing"])
        shutil.rmtree(clone)
        return ws

    def test_a_reference_is_refused_when_the_only_repository_is_unreadable(
        self, broken: str
    ):
        refusal(broken, "gather_evidence", reference="622")

        assert tickets(broken) == []

    def test_the_refusal_says_the_reference_may_not_be_absent(
        self, broken: str
    ):
        """The honest version of "nothing matched" when something could not be
        read: the repository is named, and the claim is withdrawn rather than
        asserted over a gap (product rule 1)."""
        message = refusal(broken, "gather_evidence", reference="622")

        assert "1 could not be read" in message
        assert "billing" in message
        assert "not a statement that the reference is absent" in message

    def test_a_match_elsewhere_still_opens_the_ticket(self, tmp_path: Path):
        """Unreadability blocks only the refusal's assumption. A repository
        that did recognise the reference settles the question."""
        ws = str(tmp_path / "ws")
        main(["--workspace", ws, "init"])
        good = distinct_subject(tmp_path, "billing", "LIMIT = 250\n")
        gone = distinct_subject(tmp_path, "shipping", "LIMIT = 250\n")
        main(["--workspace", ws, "repo", "add", str(good), "--name", "billing"])
        main(["--workspace", ws, "repo", "add", str(gone), "--name", "shipping"])
        shutil.rmtree(gone)

        body = json_of(call(ws, "gather_evidence", reference="622"))

        assert body["ticket_opened"] is True
        assert tickets(ws) == ["622"]


class TestTheChangeIsNarrow:
    """Everything this deliberately did not widen."""

    def test_the_tool_list_did_not_grow(self, clean: str):
        """The argument for compatibility with D-055, asserted rather than
        stated. Opening a ticket is reachable because an existing tool needed
        it, not because a new tool was added."""
        import asyncio

        server = build_server(clean)
        names = sorted(t.name for t in asyncio.run(server.list_tools()))

        assert names == sorted(EXPOSED_TOOLS)
        assert len(EXPOSED_TOOLS) == 4

    def test_get_payload_does_not_open_a_ticket(self, clean: str):
        """Only the step that gathers may open one. `get_payload` exports
        evidence and has no business creating anything."""
        refusal(clean, "get_payload", reference="622")

        assert tickets(clean) == []

    def test_list_rule_proposals_does_not_open_a_ticket(self, clean: str):
        call(clean, "list_rule_proposals", reference="622")

        assert tickets(clean) == []

    def test_the_cli_still_refuses_an_unknown_ticket(self, clean: str):
        """Off by default. A person who mistypes a reference should be told,
        not handed a new ticket — and `constat document` is where that
        happens."""
        code = main(["--workspace", clean, "document", "999", "--no-provider"])

        assert code == 4
        assert tickets(clean) == []

    def test_gather_refuses_an_unknown_ticket_by_default(self, clean: str):
        """The library default, independent of any command."""
        with Workspace.open(clean) as workspace:
            with pytest.raises(NotRegistered):
                gather(workspace, "622")

        assert tickets(clean) == []

    def test_collect_requires_a_ticket_by_default(self, clean: str):
        with Workspace.open(clean) as workspace:
            with pytest.raises(NotRegistered):
                collect(workspace, "622")

    def test_collect_without_the_guard_writes_nothing(self, clean: str):
        """Searching for an unknown reference is read-only. The guard decides
        who may act on the result, not whether looking is safe."""
        with Workspace.open(clean) as workspace:
            findings = collect(workspace, "622", require_ticket=False)

            assert len(findings) == 1
            assert TicketStore(workspace).find("622") is None


class TestTheLibraryContract:
    def test_the_refusal_is_a_ReferenceMatchedNothing(self, clean: str):
        with Workspace.open(clean) as workspace:
            with pytest.raises(ReferenceMatchedNothing):
                gather(workspace, "999", open_if_absent=True)

    def test_it_is_still_a_NotRegistered(self, clean: str):
        """Subclassed deliberately: the CLI's exit code and every existing
        handler keep working, and a caller that wants the distinction can have
        it without one being forced on callers that do not."""
        with Workspace.open(clean) as workspace:
            with pytest.raises(NotRegistered):
                gather(workspace, "999", open_if_absent=True)

    def test_the_result_reports_that_it_opened_the_ticket(self, clean: str):
        with Workspace.open(clean) as workspace:
            result = gather(workspace, "622", open_if_absent=True)

            assert result.ticket_opened is True

    def test_the_result_defaults_to_the_quieter_claim(self, clean: str):
        main(["--workspace", clean, "ticket", "add", "622", "--no-provider"])

        with Workspace.open(clean) as workspace:
            assert gather(workspace, "622").ticket_opened is False

    def test_nothing_is_accepted_by_opening_a_ticket(self, clean: str):
        """A ticket is a container for a document and carries no authority.
        Opening one must not put anything in the catalogue."""
        from constat.store import Catalogue

        call(clean, "gather_evidence", reference="622")

        with Workspace.open(clean) as workspace:
            assert Catalogue(workspace).list() == ()


class TestTheRegistryIsStillRequired:
    def test_a_workspace_with_no_repositories_refuses(self, tmp_path: Path):
        """Nothing to recognise the reference, so nothing to open a ticket
        on. Reported as a miss rather than crashing on an empty search."""
        ws = str(tmp_path / "ws")
        main(["--workspace", ws, "init"])

        message = refusal(ws, "gather_evidence", reference="622")

        assert "matched no commits" in message
        assert "searched 0 repository(ies)" in message
        assert tickets(ws) == []

    def test_the_registry_is_untouched_by_a_refusal(self, clean: str):
        refusal(clean, "gather_evidence", reference="999")

        with Workspace.open(clean) as workspace:
            assert len(Registry(workspace).list()) == 1
