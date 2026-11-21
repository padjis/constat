"""Tests for the CLI skeleton.

These assert observable behaviour — exit codes and output — rather than merely
that nothing raised. See CLAUDE.md, testing rules.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

import constat
from constat.store import SCHEMA_VERSION
from helpers import git, seed_rule
from constat.cli import PROG, build_parser, main


def test_version_flag_exits_zero_and_prints_version(capsys):
    """`--version` is a successful exit, not an error, and names the version."""
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0

    out = capsys.readouterr().out
    assert constat.__version__ in out
    assert PROG in out


def test_version_matches_package_metadata():
    """Guard against the CLI version drifting from the installed metadata.

    pyproject.toml derives the version from constat.__version__, so these must
    agree. If they ever differ, the build is reporting something untrue.
    """
    from importlib.metadata import version

    assert version("constat") == constat.__version__


def test_help_flag_exits_zero_and_describes_the_tool(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0

    out = capsys.readouterr().out
    assert PROG in out
    assert "evidence-backed" in out


def test_no_arguments_prints_help_and_succeeds(capsys):
    """Running bare `constat` must explain itself, not silently do nothing."""
    assert main([]) == 0

    out = capsys.readouterr().out
    assert "usage" in out.lower()
    assert PROG in out


def test_unknown_argument_fails_with_usage_error(capsys):
    """Invalid input must fail loudly. Exit 2 is the argparse convention."""
    with pytest.raises(SystemExit) as exc:
        main(["--definitely-not-a-flag"])
    assert exc.value.code == 2

    err = capsys.readouterr().err
    assert "unrecognized arguments" in err


def test_parser_is_constructible_without_running():
    parser = build_parser()
    assert parser.prog == PROG


def test_module_is_runnable_without_installation():
    """`python -m constat` must work, so the CLI is testable before install."""
    result = subprocess.run(
        [sys.executable, "-m", "constat", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert constat.__version__ in result.stdout


class TestInitCommand:
    def test_init_creates_a_workspace(self, tmp_path, capsys):
        assert main(["--workspace", str(tmp_path / "ws"), "init"]) == 0

        out = capsys.readouterr().out
        assert "workspace:" in out
        assert f"schema:     version {SCHEMA_VERSION}" in out
        assert (tmp_path / "ws" / "workspace.db").exists()

    def test_init_reports_the_workspace_it_used(self, tmp_path, capsys):
        """A default location is acceptable; an undisclosed one is not."""
        target = tmp_path / "ws"
        main(["--workspace", str(target), "init"])
        assert str(target) in capsys.readouterr().out

    def test_init_refuses_to_overwrite_and_exits_four(self, tmp_path, capsys):
        """Stored decisions must survive a careless second init."""
        target = str(tmp_path / "ws")
        main(["--workspace", target, "init"])
        capsys.readouterr()

        assert main(["--workspace", target, "init"]) == 4
        captured = capsys.readouterr()
        assert "already exists" in captured.err
        assert captured.out == ""

    def test_workspace_errors_use_their_own_exit_code(self, tmp_path, capsys):
        """2 is malformed input, 3 is the repository, 4 is our own state."""
        target = str(tmp_path / "ws")
        main(["--workspace", target, "init"])
        capsys.readouterr()
        assert main(["--workspace", target, "init"]) == 4


class TestRepoCommands:
    def _ws(self, tmp_path):
        target = str(tmp_path / "ws")
        main(["--workspace", target, "init"])
        return target

    def _clone(self, tmp_path, repo):
        target = tmp_path / "cloned"
        git(tmp_path, "clone", "--quiet", str(repo), str(target))
        return target

    def test_add_then_list(self, tmp_path, repo, capsys):
        ws = self._ws(tmp_path)
        cloned = self._clone(tmp_path, repo)
        capsys.readouterr()

        assert main(["--workspace", ws, "repo", "add", str(cloned), "--name", "s"]) == 0
        assert main(["--workspace", ws, "repo", "list"]) == 0

        out = capsys.readouterr().out
        assert "s" in out
        assert "main" in out

    def test_list_on_an_empty_workspace_says_so(self, tmp_path, capsys):
        ws = self._ws(tmp_path)
        capsys.readouterr()

        assert main(["--workspace", ws, "repo", "list"]) == 0
        assert "No repositories registered" in capsys.readouterr().out

    def test_duplicate_exits_four_with_the_existing_alias(self, tmp_path, repo, capsys):
        ws = self._ws(tmp_path)
        cloned = self._clone(tmp_path, repo)
        main(["--workspace", ws, "repo", "add", str(cloned), "--name", "first"])
        capsys.readouterr()

        assert main(["--workspace", ws, "repo", "add", str(cloned), "--name", "second"]) == 4
        assert "first" in capsys.readouterr().err

    def test_unresolvable_default_branch_exits_three(self, tmp_path, repo, capsys):
        """A repository problem, not a workspace problem."""
        ws = self._ws(tmp_path)
        capsys.readouterr()

        assert main(["--workspace", ws, "repo", "add", str(repo), "--name", "x"]) == 3
        assert "--default-branch" in capsys.readouterr().err

    def test_explicit_default_branch_is_accepted(self, tmp_path, repo, capsys):
        ws = self._ws(tmp_path)
        capsys.readouterr()

        code = main(
            ["--workspace", ws, "repo", "add", str(repo), "--name", "x",
             "--default-branch", "main"]
        )
        assert code == 0
        assert "default branch: main" in capsys.readouterr().out

    def test_remove_reports_the_repository_is_untouched(self, tmp_path, repo, capsys):
        ws = self._ws(tmp_path)
        cloned = self._clone(tmp_path, repo)
        main(["--workspace", ws, "repo", "add", str(cloned), "--name", "s"])
        capsys.readouterr()

        assert main(["--workspace", ws, "repo", "remove", "s"]) == 0
        assert "untouched" in capsys.readouterr().out
        assert cloned.exists()

    def test_removing_an_unknown_alias_exits_four(self, tmp_path, capsys):
        ws = self._ws(tmp_path)
        capsys.readouterr()

        assert main(["--workspace", ws, "repo", "remove", "nope"]) == 4
        assert "nope" in capsys.readouterr().err

    def test_repo_without_an_action_shows_help(self, tmp_path, capsys):
        ws = self._ws(tmp_path)
        capsys.readouterr()

        with pytest.raises(SystemExit):
            main(["--workspace", ws, "repo"])
        assert "add" in capsys.readouterr().out


class TestTicketCommands:
    def _ws(self, tmp_path):
        target = str(tmp_path / "ws")
        main(["--workspace", target, "init"])
        return target

    def test_add_opens_the_ticket_and_fills_its_document(self, tmp_path, capsys):
        """Opening a ticket writes its document immediately; an empty one
        would say nothing and require a second command to be useful."""
        ws = self._ws(tmp_path)
        capsys.readouterr()

        # `--even-if-absent` because this workspace has no repositories and
        # CON-105 refuses a reference nothing could recognise. The subject
        # here is the document, not the guard.
        code = main(
            ["--workspace", ws, "ticket", "add", "622", "--no-provider",
             "--even-if-absent"]
        )

        assert code == 0
        out = capsys.readouterr().out
        assert "opened ticket: 622" in out
        assert "Document written" in out

        capsys.readouterr()
        main(["--workspace", ws, "document", "622", "--show", "--no-provider"])
        assert "# Ticket 622" in capsys.readouterr().out

    def test_add_is_refused_twice(self, tmp_path, capsys):
        ws = self._ws(tmp_path)
        main(
            ["--workspace", ws, "ticket", "add", "622", "--no-provider",
             "--even-if-absent"]
        )
        capsys.readouterr()

        assert main(
            ["--workspace", ws, "ticket", "add", "622", "--no-provider",
             "--even-if-absent"]
        ) == 4
        assert "already exists" in capsys.readouterr().err

    def test_list_and_show(self, tmp_path, capsys):
        ws = self._ws(tmp_path)
        main(
            ["--workspace", ws, "ticket", "add", "622", "--no-provider",
             "--even-if-absent"]
        )
        capsys.readouterr()

        assert main(["--workspace", ws, "ticket", "list"]) == 0
        assert "622" in capsys.readouterr().out

        assert main(["--workspace", ws, "ticket", "show", "622"]) == 0
        shown = capsys.readouterr().out
        assert "document:  filled" in shown
        assert "operations:" in shown

    def test_show_an_unknown_ticket_exits_four(self, tmp_path, capsys):
        ws = self._ws(tmp_path)
        capsys.readouterr()

        assert main(["--workspace", ws, "ticket", "show", "nope"]) == 4
        assert "no ticket" in capsys.readouterr().err

    def test_pending_work_is_reported_as_ahead_of_mainline(self, tmp_path, repo, capsys):
        """The case D-031 expects: merged outside mainline."""
        ws = self._ws(tmp_path)
        clone = tmp_path / "clone"
        git(tmp_path, "clone", "--quiet", str(repo), str(clone))
        git(clone, "checkout", "--quiet", "-b", "develop")
        (clone / "x.txt").write_text("x\n")
        git(clone, "add", "x.txt")
        git(clone, "commit", "-m", "Change a rule (#77)")
        git(clone, "checkout", "--quiet", "main")

        main(["--workspace", ws, "repo", "add", str(clone), "--name", "s"])
        capsys.readouterr()

        assert main(["--workspace", ws, "ticket", "add", "77", "--no-provider"]) == 0
        assert "s: pending — 1 commit(s)" in capsys.readouterr().out

    def test_landed_work_is_distinguished_from_nothing(self, tmp_path, repo, capsys):
        ws = self._ws(tmp_path)
        clone = tmp_path / "clone"
        git(tmp_path, "clone", "--quiet", str(repo), str(clone))
        (clone / "y.txt").write_text("y\n")
        git(clone, "add", "y.txt")
        git(clone, "commit", "-m", "Already shipped (#88)")
        # Mainline is the shared ref (CON-76), so shipped work has to be on
        # it. The tracking ref is moved rather than pushed: the fixture's
        # origin has `main` checked out and git refuses a push into that.
        git(clone, "update-ref", "refs/remotes/origin/main", "HEAD")

        main(["--workspace", ws, "repo", "add", str(clone), "--name", "s"])
        capsys.readouterr()

        main(["--workspace", ws, "ticket", "add", "88", "--no-provider"])
        assert "s: landed" in capsys.readouterr().out

        # Changed by CON-105, and the distinction is sharper for it: landed
        # work opens a ticket, a reference nothing recognises is refused
        # outright rather than opening one that reports `not_found`.
        code = main(["--workspace", ws, "ticket", "add", "99999", "--no-provider"])

        assert code == 4
        assert "matched no commits" in capsys.readouterr().err


class TestDocumentCommand:
    def _setup(self, tmp_path, with_repo=True):
        ws = str(tmp_path / "ws")
        main(["--workspace", ws, "init"])
        if with_repo:
            source = tmp_path / "src"
            source.mkdir()
            git(source, "init", "--initial-branch=main", "--quiet")
            (source / "a.py").write_text("x = 1\n")
            git(source, "add", "a.py")
            git(source, "commit", "-m", "Initial")

            clone = tmp_path / "clone"
            git(tmp_path, "clone", "--quiet", str(source), str(clone))
            git(clone, "checkout", "--quiet", "-b", "develop")
            (clone / "a.py").write_text("x = 2\n")
            git(clone, "add", "a.py")
            git(clone, "commit", "-m", "Change the rule (#622)")
            git(clone, "checkout", "--quiet", "main")
            main(["--workspace", ws, "repo", "add", str(clone), "--name", "billing"])
        main(["--workspace", ws, "ticket", "add", "622", "--no-provider"])
        return ws

    def test_document_gathers_and_reports(self, tmp_path, capsys):
        ws = self._setup(tmp_path)
        capsys.readouterr()

        assert main(["--workspace", ws, "document", "622", "--no-provider"]) == 0
        out = capsys.readouterr().out
        assert "document updated" in out
        assert "billing: pending" in out

    def test_show_prints_the_document(self, tmp_path, capsys):
        ws = self._setup(tmp_path)
        capsys.readouterr()

        assert main(["--workspace", ws, "document", "622", "--show", "--no-provider"]) == 0
        body = capsys.readouterr().out
        assert "# Ticket 622" in body
        assert "a.py" in body
        assert "carries no authority" in body

    def test_an_unknown_ticket_exits_four(self, tmp_path, capsys):
        ws = self._setup(tmp_path, with_repo=False)
        capsys.readouterr()

        assert main(["--workspace", ws, "document", "nope", "--no-provider"]) == 4
        assert "no ticket" in capsys.readouterr().err

    def test_it_says_no_rules_were_identified_and_why(self, tmp_path, capsys):
        """CON-41's done-when at the surface a user actually sees.

        The summary must not let "no rules" read as "nothing is governed
        here" — it is a fact about configuration, and it says so.
        """
        ws = self._setup(tmp_path)
        capsys.readouterr()

        assert main(["--workspace", ws, "document", "622", "--no-provider"]) == 0
        out = capsys.readouterr().out
        assert "no rules identified" in out
        assert "no AI provider is configured" in out
        assert "not about the code" in out

    def test_the_document_carries_the_rules_section(self, tmp_path, capsys):
        ws = self._setup(tmp_path)
        capsys.readouterr()

        main(["--workspace", ws, "document", "622", "--show", "--no-provider"])
        body = capsys.readouterr().out
        assert "## Business rules" in body
        assert "may well exist" in body

    def test_an_unimplemented_provider_exits_five(self, tmp_path, capsys, monkeypatch):
        """A provider fault gets its own exit code.

        Reusing 3 or 4 would tell the user to check a repository or their
        workspace, and both are fine — the environment is not.
        """
        ws = self._setup(tmp_path)
        monkeypatch.setenv("CONSTAT_AI_PROVIDER", "openai")
        capsys.readouterr()

        assert main(["--workspace", ws, "document", "622", "--no-provider"]) == 5
        assert "does not implement" in capsys.readouterr().err

    def test_ticket_add_also_reports_the_rules_state(self, tmp_path, capsys):
        """`ticket add` gathers too.

        A user who only ever opens tickets would otherwise never be told that
        no rules were identified, and silence reads as "there are none".
        """
        ws = str(tmp_path / "ws")
        main(["--workspace", ws, "init"])
        capsys.readouterr()

        # `--even-if-absent` because the workspace has no repositories; the
        # subject is what `ticket add` reports once it has opened one.
        code = main(
            ["--workspace", ws, "ticket", "add", "900", "--no-provider",
             "--even-if-absent"]
        )

        assert code == 0
        assert "no rules identified" in capsys.readouterr().out

    def test_ticket_add_exits_five_on_a_provider_fault(
        self, tmp_path, capsys, monkeypatch
    ):
        ws = str(tmp_path / "ws")
        main(["--workspace", ws, "init"])
        monkeypatch.setenv("CONSTAT_AI_PROVIDER", "openai")
        capsys.readouterr()

        assert main(["--workspace", ws, "ticket", "add", "901", "--no-provider"]) == 5
        assert "does not implement" in capsys.readouterr().err

    def test_the_credential_scan_reports_even_when_clean(self, tmp_path, capsys):
        """A scan that only speaks when it fails cannot be told apart from a
        scan that never ran."""
        ws = self._setup(tmp_path)
        capsys.readouterr()

        assert main(["--workspace", ws, "document", "622", "--no-provider"]) == 0
        out = capsys.readouterr().out
        assert "credential scan: no findings" in out
        assert "known formats only" in out

    def _setup_with_secret(self, tmp_path):
        """A ticket whose pending commit adds an AWS documentation example key."""
        ws = str(tmp_path / "ws")
        main(["--workspace", ws, "init"])
        source = tmp_path / "src"
        source.mkdir()
        git(source, "init", "--initial-branch=main", "--quiet")
        (source / "a.py").write_text("x = 1\n")
        git(source, "add", "a.py")
        git(source, "commit", "-m", "Initial")

        clone = tmp_path / "clone"
        git(tmp_path, "clone", "--quiet", str(source), str(clone))
        git(clone, "checkout", "--quiet", "-b", "develop")
        (clone / "a.py").write_text("KEY = 'AKIAIOSFODNN7EXAMPLE'\n")
        git(clone, "add", "a.py")
        git(clone, "commit", "-m", "Wire up the client (#622)")
        git(clone, "checkout", "--quiet", "main")
        main(["--workspace", ws, "repo", "add", str(clone), "--name", "billing"])
        main(["--workspace", ws, "ticket", "add", "622", "--no-provider"])
        return ws

    def _configure_provider(self, monkeypatch):
        """Put a fake provider in the real registry, as a user would configure
        a real one."""
        from constat.ai import settings
        from test_ai import FakeProvider

        monkeypatch.setitem(settings.PROVIDERS, "fake", lambda env: FakeProvider())
        monkeypatch.setenv("CONSTAT_AI_PROVIDER", "fake")

    def test_a_credential_refuses_the_run_with_the_provider_exit_code(
        self, tmp_path, capsys, monkeypatch
    ):
        ws = self._setup_with_secret(tmp_path)
        self._configure_provider(monkeypatch)
        capsys.readouterr()

        assert main(["--workspace", ws, "document", "622", "--no-provider"]) == 5
        err = capsys.readouterr().err
        assert "refusing to send" in err
        assert "a.py" in err
        assert "--accept-scan-findings" in err

    def test_the_refusal_does_not_print_the_credential(
        self, tmp_path, capsys, monkeypatch
    ):
        """stderr goes into terminal scrollback and CI logs."""
        ws = self._setup_with_secret(tmp_path)
        self._configure_provider(monkeypatch)
        capsys.readouterr()

        main(["--workspace", ws, "document", "622", "--no-provider"])
        captured = capsys.readouterr()
        assert "AKIAIOSFODNN7EXAMPLE" not in captured.err
        assert "AKIAIOSFODNN7EXAMPLE" not in captured.out

    def test_the_override_lets_the_run_through(self, tmp_path, capsys, monkeypatch):
        ws = self._setup_with_secret(tmp_path)
        self._configure_provider(monkeypatch)
        capsys.readouterr()

        code = main(
            ["--workspace", ws, "document", "622", "--accept-scan-findings"]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "1 possible credential(s) found" in out
        assert "accepted via --accept-scan-findings" in out

    def test_with_no_provider_a_credential_does_not_block_the_run(
        self, tmp_path, capsys
    ):
        """Nothing is being sent, so there is nothing to protect."""
        ws = self._setup_with_secret(tmp_path)
        capsys.readouterr()

        assert main(["--workspace", ws, "document", "622", "--no-provider"]) == 0
        out = capsys.readouterr().out
        assert "1 possible credential(s) found" in out
        assert "nothing was sent" in out

    def test_the_provider_exit_code_is_distinct(self):
        """Guard against a future edit collapsing the codes."""
        from constat.cli import (
            EXIT_PROVIDER,
            EXIT_REPOSITORY,
            EXIT_USAGE,
            EXIT_WORKSPACE,
        )

        codes = {EXIT_USAGE, EXIT_REPOSITORY, EXIT_WORKSPACE, EXIT_PROVIDER}
        assert len(codes) == 4


class TestRuleCommands:
    """Read-only after D-048. A rule enters only as an accepted rule proposal
    and can never be removed, so the authoring commands are gone."""

    def _ws(self, tmp_path):
        target = str(tmp_path / "ws")
        main(["--workspace", target, "init"])
        return target

    def _a_rule(self, ws: str) -> None:
        """Seeded through the storage API, because there is no command."""
        from constat.store import Catalogue, Workspace

        with Workspace.open(ws) as workspace:
            catalogue = Catalogue(workspace)
            seed_rule(
                workspace,
                "limit",
                "At most the limit.",
                behaviours=("Refused above.",),
                anchors=("rules.py",),
            )

    def test_show_and_list_still_work(self, tmp_path, capsys):
        ws = self._ws(tmp_path)
        self._a_rule(ws)
        capsys.readouterr()

        assert main(["--workspace", ws, "rule", "show", "limit"]) == 0
        shown = capsys.readouterr().out
        assert "At most the limit." in shown
        assert "Refused above." in shown
        assert "rules.py" in shown

        assert main(["--workspace", ws, "rule", "list"]) == 0
        assert "limit" in capsys.readouterr().out

    @pytest.mark.parametrize(
        "argv",
        [
            ["rule", "add", "limit", "At most."],
            ["rule", "behaviour", "limit", "Refused above."],
            ["rule", "anchor", "limit", "rules.py"],
            ["rule", "remove", "limit"],
        ],
    )
    def test_the_authoring_commands_are_gone(self, tmp_path, argv):
        """D-048: no human-authored path into the catalogue, and no removal.

        argparse rejects the unknown subcommand with exit 2 — the command does
        not exist rather than existing and refusing, so there is nothing to
        rediscover in a later release.
        """
        ws = self._ws(tmp_path)
        with pytest.raises(SystemExit) as exc:
            main(["--workspace", ws, *argv])
        assert exc.value.code == 2

    def test_an_empty_catalogue_explains_the_consequence(self, tmp_path, capsys):
        """No rules must not read as "nothing is affected"."""
        ws = self._ws(tmp_path)
        capsys.readouterr()

        assert main(["--workspace", ws, "rule", "list"]) == 0
        out = capsys.readouterr().out
        assert "No rules in the catalogue" in out
        assert "not the same as" in out

    def test_the_empty_message_says_where_rules_come_from(self, tmp_path, capsys):
        """A reader who cannot find an `add` command needs telling why."""
        ws = self._ws(tmp_path)
        capsys.readouterr()

        main(["--workspace", ws, "rule", "list"])
        assert "accepted rule proposal" in capsys.readouterr().out

    def test_show_an_unknown_rule_exits_four(self, tmp_path, capsys):
        ws = self._ws(tmp_path)
        capsys.readouterr()

        assert main(["--workspace", ws, "rule", "show", "nope"]) == 4
        assert "no rule" in capsys.readouterr().err
