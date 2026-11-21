"""`ticket add` refuses a reference no repository knows (CON-105).

D-063 gave the reasoning when it let the *agent* open a ticket: a reference
matching nothing "is more often a typo than a ticket", and an empty ticket is
worse than none because the workspace then refuses to open it again. It put
the guard on `gather_evidence` and said the CLI keeps its refusal, "because a
person who mistypes a reference should be told rather than handed a new
ticket".

The CLI had no such refusal. `constat ticket add 99998` opened a ticket at
exit 0 for a reference nothing recognised — so the terminal, the one place the
argument was about, was the one place not asking. Found by running it, and it
left two junk tickets in a live workspace to prove it: there is no
`ticket remove`, and the store is append-only.

Four properties carry these tests:

1. **A reference nothing recognises is refused**, and the refusal leaves no
   ticket behind — a half-opened ticket would be the exact harm.
2. **Recognition includes landed work.** The work was found, in mainline; that
   is a different answer from "no such reference" (D-031).
3. **The deliberate case survives**, behind `--even-if-absent`. Work that has
   not started, or is tracked where Constat cannot see, is real, and `USAGE.md`
   has always pointed at `ticket add` for it.
4. **The CLI and the agent path now agree.** Two answers to one question was
   the defect.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.cli import main
from constat.errors import ReferenceMatchedNothing
from constat.operations import gather
from constat.store import Registry, Settings, TicketStore, Workspace

from helpers import commit_file, git
from test_runs import distinct_subject


def _workspace_with(tmp_path: Path, reference: str | None) -> Path:
    """A workspace over one repository, whose history may name a reference.

    Returns the directory `--workspace` takes, which is the one holding
    `workspace.db`.
    """
    home = tmp_path / "home"
    subject = distinct_subject(tmp_path, "billing", "LIMIT = 250\n")
    if reference is not None:
        commit_file(subject, "limits.py", "LIMIT = 300\n", f"{reference}: raise it")
    with Workspace.create(home / "ws") as ws:
        Registry(ws).add(str(subject), alias="billing")
        # The reading happens through an agent, so `ticket add` does not refuse
        # for want of a provider (D-059) before reaching what is under test.
        Settings(ws).set_reader("mcp")
    return home / "ws"


def _tickets(home: Path) -> list[str]:
    with Workspace.open(home) as ws:
        return [t.reference for t in TicketStore(ws).list()]


# -- the refusal --------------------------------------------------------------


class TestAReferenceNothingKnows:
    def test_it_is_refused(self, tmp_path, capsys) -> None:
        home = _workspace_with(tmp_path, reference=None)
        capsys.readouterr()

        code = main(["--workspace", str(home), "ticket", "add", "99998"])

        assert code == 4
        assert "matched no commits" in capsys.readouterr().err

    def test_no_ticket_is_left_behind(self, tmp_path, capsys) -> None:
        """The harm the refusal exists to prevent.

        A ticket opened for a typo cannot be removed — the store is
        append-only and there is no `ticket remove` — so a refusal that
        half-opened one would be worse than no refusal at all.
        """
        home = _workspace_with(tmp_path, reference=None)
        capsys.readouterr()

        main(["--workspace", str(home), "ticket", "add", "99998"])

        assert _tickets(home) == []

    def test_the_refusal_names_the_way_through(self, tmp_path, capsys) -> None:
        """A refusal that does not say what to do instead is a dead end."""
        home = _workspace_with(tmp_path, reference=None)
        capsys.readouterr()

        main(["--workspace", str(home), "ticket", "add", "99998"])

        assert "--even-if-absent" in capsys.readouterr().err

    def test_it_says_how_much_was_searched(self, tmp_path, capsys) -> None:
        home = _workspace_with(tmp_path, reference=None)
        capsys.readouterr()

        main(["--workspace", str(home), "ticket", "add", "99998"])

        assert "repository(ies)" in capsys.readouterr().err


# -- what counts as recognition ----------------------------------------------


class TestAReferenceTheRepositoriesKnow:
    def test_it_opens(self, tmp_path, capsys) -> None:
        home = _workspace_with(tmp_path, reference="622")
        capsys.readouterr()

        code = main(["--workspace", str(home), "ticket", "add", "622"])

        assert code == 0
        assert _tickets(home) == ["622"]

    def test_landed_work_counts_as_recognition(self, tmp_path, capsys) -> None:
        """D-031: work already in mainline contributes no evidence, and that
        is not the same as the reference being unknown.

        Built the way `test_agent_opens_ticket.py` builds it — a repository
        where the reference exists only on mainline — so the CLI is asked the
        same question the agent path already answers.
        """
        home = tmp_path / "home" / "ws"
        main(["--workspace", str(home), "init"])
        with Workspace.open(home) as ws:
            Settings(ws).set_reader("mcp")

        source = tmp_path / "shipped-src"
        source.mkdir()
        git(source, "init", "--initial-branch=main", "--quiet")
        commit_file(source, "rules.py", "LIMIT = 100\n", "Initial (shipped)")
        commit_file(source, "rules.py", "LIMIT = 250\n", "Raise the limit (#700)")
        main(
            [
                "--workspace", str(home), "repo", "add", str(source),
                "--name", "shipped", "--default-branch", "main",
            ]
        )
        capsys.readouterr()

        code = main(["--workspace", str(home), "ticket", "add", "700"])

        assert code == 0
        assert "landed" in capsys.readouterr().out
        assert _tickets(home) == ["700"]

    def test_opening_it_twice_is_refused(self, tmp_path, capsys) -> None:
        """Unchanged, and checked before the search so the message does not
        depend on which path the reference would have taken."""
        home = _workspace_with(tmp_path, reference="622")
        main(["--workspace", str(home), "ticket", "add", "622"])
        capsys.readouterr()

        code = main(["--workspace", str(home), "ticket", "add", "622"])

        assert code == 4
        assert "already exists" in capsys.readouterr().err


# -- the deliberate case ------------------------------------------------------


class TestOpeningOneAnyway:
    def test_the_flag_opens_an_unmatched_reference(self, tmp_path, capsys) -> None:
        home = _workspace_with(tmp_path, reference=None)
        capsys.readouterr()

        code = main(
            ["--workspace", str(home), "ticket", "add", "99998", "--even-if-absent"]
        )

        assert code == 0
        assert _tickets(home) == ["99998"]

    def test_it_still_gathers(self, tmp_path, capsys) -> None:
        """Opening without filling would leave an empty document saying
        nothing, which is why `ticket add` gathers at all."""
        home = _workspace_with(tmp_path, reference=None)
        capsys.readouterr()

        main(
            ["--workspace", str(home), "ticket", "add", "99998", "--even-if-absent"]
        )

        assert "repository(ies) searched" in capsys.readouterr().out

    def test_the_flag_does_not_bypass_the_duplicate_guard(
        self, tmp_path, capsys
    ) -> None:
        home = _workspace_with(tmp_path, reference=None)
        main(
            ["--workspace", str(home), "ticket", "add", "99998", "--even-if-absent"]
        )
        capsys.readouterr()

        code = main(
            ["--workspace", str(home), "ticket", "add", "99998", "--even-if-absent"]
        )

        assert code == 4
        assert "already exists" in capsys.readouterr().err


# -- the two paths agree ------------------------------------------------------


class TestTheCliAndTheAgentPathAgree:
    """The defect was two answers to one question, so the fix is tested as
    agreement rather than as two separate behaviours."""

    def test_both_refuse_the_same_reference(self, tmp_path, capsys) -> None:
        home = _workspace_with(tmp_path, reference=None)
        capsys.readouterr()

        cli_code = main(["--workspace", str(home), "ticket", "add", "99998"])

        with Workspace.open(home) as ws:
            with pytest.raises(ReferenceMatchedNothing):
                gather(ws, "99998", open_if_absent=True)

        assert cli_code == 4
        assert _tickets(home) == []

    def test_both_open_the_same_reference(self, tmp_path, capsys) -> None:
        home = _workspace_with(tmp_path, reference="622")
        capsys.readouterr()

        with Workspace.open(home) as ws:
            gather(ws, "622", open_if_absent=True)

        assert _tickets(home) == ["622"]
