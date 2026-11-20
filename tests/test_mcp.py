"""Tests for the MCP server (CON-50).

The most important test here asserts an **absence**: there is no tool that can
accept a rule proposal. A model that could accept would make "no proposal
becomes official without an explicit human decision" unenforceable, and the
hard prohibition in `CLAUDE.md` is that Constat must never mark a proposal
approved without a recorded human decision.

An absence is the easiest thing to lose. A later release adding one tool "for
convenience" would do it silently, so the tool list is asserted rather than
trusted.

The rest check that the gates hold through this door too — identity (D-040),
the credential refusal (D-047) and anchor grounding (D-052) — which they do by
construction, because every tool calls the same function the CLI does.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from constat.cli import main
from constat.store import Catalogue, Registry, RuleProposals, TicketStore, Workspace

from test_runs import distinct_subject
from test_scanning import AWS_KEY

pytest.importorskip("mcp", reason="the MCP server is an optional extra")

from constat.mcp import (  # noqa: E402  (after importorskip)
    EXPOSED_TOOLS,
    FORBIDDEN_TOOLS,
    build_server,
)


@pytest.fixture
def home(tmp_path: Path) -> str:
    """A workspace with one repository and ticket 622 pending."""
    ws = str(tmp_path / "ws")
    main(["--workspace", ws, "init"])
    clone = distinct_subject(tmp_path, "billing", "LIMIT = 250\n")
    main(["--workspace", ws, "repo", "add", str(clone), "--name", "billing"])
    main(["--workspace", ws, "ticket", "add", "622", "--no-provider"])
    return ws


@pytest.fixture
def leaky_home(tmp_path: Path) -> str:
    """A workspace whose evidence contains a credential."""
    ws = str(tmp_path / "ws")
    main(["--workspace", ws, "init"])
    clone = distinct_subject(tmp_path, "billing", f"K = '{AWS_KEY}'\n")
    main(["--workspace", ws, "repo", "add", str(clone), "--name", "billing"])
    main(["--workspace", ws, "ticket", "add", "622", "--no-provider"])
    return ws


def call(home: str, tool: str, **arguments):
    """Invoke one tool, as a client would, and return its text result."""
    server = build_server(home)
    result = asyncio.run(server.call_tool(tool, arguments))
    return result


def text_of(result) -> str:
    return result.content[0].text


def json_of(result):
    return json.loads(text_of(result))


class TestAcceptanceIsNotExposed:
    """The test this file exists for."""

    def test_the_tool_list_is_exactly_the_four(self, home: str):
        server = build_server(home)
        names = sorted(t.name for t in asyncio.run(server.list_tools()))
        assert names == sorted(EXPOSED_TOOLS)

    def test_no_tool_can_accept_or_reject(self, home: str):
        """Asserted on the live tool list, not on the source: a tool added by
        a decorator anywhere would show up here."""
        server = build_server(home)
        names = [t.name for t in asyncio.run(server.list_tools())]

        for forbidden in FORBIDDEN_TOOLS:
            assert not any(forbidden in name for name in names), (
                f"a tool matching {forbidden!r} is exposed; acceptance must "
                "stay a human act outside the agent's reach"
            )

    def test_the_instructions_say_nothing_is_accepted(self, home: str):
        """A model that does not know its output is provisional will present it
        as settled."""
        from constat.mcp import INSTRUCTIONS

        assert "Nothing you submit is accepted" in INSTRUCTIONS
        assert "no tool here that can make one" in INSTRUCTIONS

    def test_submitting_reports_that_nothing_was_accepted(self, home: str):
        reply = json.dumps(
            {
                "rules": [
                    {
                        "name": "daily-limit",
                        "statement": "A transfer over the limit is refused.",
                        "anchors": [
                            {"path_glob": "rules.py", "repository_alias": "billing"}
                        ],
                    }
                ]
            }
        )
        call(home, "gather_evidence", reference="622")
        result = json_of(call(home, "submit_rules", reference="622", reply=reply))

        assert result["accepted"] is False
        assert "no tool that can accept" in result["note"]

    def test_the_catalogue_stays_empty_however_much_is_submitted(self, home: str):
        reply = json.dumps(
            {
                "rules": [
                    {
                        "name": f"rule-{n}",
                        "statement": "Something holds.",
                        "anchors": [{"path_glob": "rules.py"}],
                    }
                    for n in range(3)
                ]
            }
        )
        call(home, "submit_rules", reference="622", reply=reply)

        with Workspace.open(home) as workspace:
            assert Catalogue(workspace).list() == ()
            assert len(RuleProposals(workspace).undecided("622")) == 3


class TestTheToolsWork:
    def test_gather_reports_every_repository(self, home: str):
        result = json_of(call(home, "gather_evidence", reference="622"))

        assert result["reference"] == "622"
        assert result["repositories_searched"] == 1
        assert result["repositories_contributing"] == 1
        assert result["run_id"] is not None

    def test_the_payload_carries_evidence_and_the_catalogue(self, home: str):
        payload = json_of(call(home, "get_payload", reference="622"))

        assert payload["reference"] == "622"
        assert sum(len(r["commits"]) for r in payload["repositories"]) == 1
        assert "catalogue" in payload

    def test_the_payload_carries_no_identity(self, home: str):
        """D-040 holds here because `get_payload` calls `export_payload`."""
        from test_ai import FIXTURE_EMAIL

        assert FIXTURE_EMAIL not in text_of(call(home, "get_payload", reference="622"))

    def test_submitting_stores_and_reports_discards(self, home: str):
        reply = json.dumps(
            {
                "rules": [
                    {
                        "name": "daily-limit",
                        "statement": "A transfer over the limit is refused.",
                        "anchors": [
                            {"path_glob": "rules.py", "repository_alias": "billing"}
                        ],
                    },
                    {
                        "name": "invented",
                        "statement": "Nothing supports this.",
                        "anchors": ["src/nope.py"],
                    },
                ]
            }
        )
        result = json_of(call(home, "submit_rules", reference="622", reply=reply))

        assert len(result["stored"]) == 1
        assert [d["name"] for d in result["discarded"]] == ["invented"]
        assert "grounded" in result["discarded"][0]["reason"]

    def test_the_queue_is_readable(self, home: str):
        reply = json.dumps(
            {
                "rules": [
                    {
                        "name": "daily-limit",
                        "statement": "A transfer over the limit is refused.",
                        "anchors": [{"path_glob": "rules.py"}],
                    }
                ]
            }
        )
        call(home, "submit_rules", reference="622", reply=reply, provider="claude")
        queue = json_of(call(home, "list_rule_proposals", reference="622"))

        assert len(queue) == 1
        assert queue[0]["name"] == "daily-limit"
        assert queue[0]["decision"] is None
        assert queue[0]["read_by"] == "claude"

    def test_the_queue_marks_the_model_as_self_reported(self, home: str):
        """D-045: nothing verifies what produced a reading, and a client
        reading this must not take it for an observed fact."""
        reply = json.dumps(
            {
                "rules": [
                    {
                        "name": "daily-limit",
                        "statement": "Something holds.",
                        "anchors": [{"path_glob": "rules.py"}],
                    }
                ]
            }
        )
        call(home, "submit_rules", reference="622", reply=reply, model="opus-5")
        queue = json_of(call(home, "list_rule_proposals", reference="622"))

        assert queue[0]["model"] == "opus-5"
        assert queue[0]["model_is_self_reported"] is True

    def test_an_empty_queue_is_an_empty_list(self, home: str):
        assert json_of(call(home, "list_rule_proposals", reference="622")) == []


class TestTheGatesHoldThroughThisDoor:
    """In-process a tool raises `ToolError`; a client receives `isError` with
    the same message. Both are checked — the second is the real contract."""

    def test_a_credential_refuses_the_payload(self, leaky_home: str):
        """D-047's gate fires here, because `get_payload` is `export_payload`.

        An MCP client is outside the process, so this is egress.
        """
        from mcp.server.mcpserver.exceptions import ToolError

        with pytest.raises(ToolError) as exc:
            call(leaky_home, "get_payload", reference="622")

        message = str(exc.value)
        assert "refusing to send" in message
        assert "rules.py" in message  # where to look
        assert AWS_KEY not in message  # never the secret itself

    def test_gathering_still_works_with_a_credential_present(self, leaky_home: str):
        """Nothing is transmitted by gathering, so a false positive must not
        block it (D-044's asymmetry)."""
        result = json_of(call(leaky_home, "gather_evidence", reference="622"))
        assert result["credential_scan_findings"] == 1

    def test_an_unusable_reply_is_an_error_not_an_empty_result(self, home: str):
        """D-046 through MCP: a caller's bad JSON must not read as "no rules
        were identified"."""
        from mcp.server.mcpserver.exceptions import ToolError

        with pytest.raises(ToolError, match="not valid JSON"):
            call(home, "submit_rules", reference="622", reply="I found none.")

    def test_an_unknown_ticket_is_an_error(self, home: str):
        """Still true after CON-64, for a different reason.

        This used to fail because no ticket existed; `gather_evidence` now
        opens one. It fails because `nope` matches no commits in any
        repository — which is the half of the old refusal that was doing the
        work, and `test_agent_opens_ticket.py` is where that is covered
        properly.
        """
        from mcp.server.mcpserver.exceptions import ToolError

        with pytest.raises(ToolError):
            call(home, "gather_evidence", reference="nope")

    def test_a_refusal_keeps_its_reason_rather_than_becoming_generic(
        self, leaky_home: str
    ):
        """The reason is the only part worth sending.

        These messages are the product's voice — "remove the credential and
        rotate it". A `ConstatError` left to escape is wrapped as an unexpected
        crash and the client sees only "Error executing tool get_payload",
        which a caller cannot act on.
        """
        from mcp.server.mcpserver.exceptions import ToolError

        with pytest.raises(ToolError) as exc:
            call(leaky_home, "get_payload", reference="622")
        assert "rotate it" in str(exc.value)


class TestTheCommandLineEntryPoint:
    def test_the_mcp_subcommand_exists(self):
        from constat.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["mcp"])
        assert args.command == "mcp"

    def test_the_help_says_acceptance_is_not_exposed(self):
        from constat.cli import build_parser

        parser = build_parser()
        action = next(
            a for a in parser._actions if getattr(a, "choices", None) and "mcp" in a.choices
        )
        description = action.choices["mcp"].description
        assert "not exposed" in description
        assert "Nothing listens" in description

    def test_a_missing_dependency_is_reported_clearly(self, monkeypatch, capsys):
        """The extra is opt-in, so the failure has to name the fix."""
        import builtins

        real_import = builtins.__import__

        def fail_on_mcp(name, *args, **kwargs):
            if name == "mcp" or name.startswith("mcp."):
                raise ImportError("no mcp")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fail_on_mcp)
        monkeypatch.delitem(__import__("sys").modules, "constat.mcp", raising=False)

        code = main(["mcp"])
        assert code == 2
        assert "constat[mcp]" in capsys.readouterr().err


class TestThroughARealClient:
    """One end-to-end pass over stdio. Slower, and the only place the actual
    client contract is exercised rather than the in-process shortcut."""

    def _session(self, home: str):
        import shutil

        from mcp import StdioServerParameters

        constat = shutil.which("constat") or str(
            Path(__file__).resolve().parent.parent / ".venv" / "bin" / "constat"
        )
        return StdioServerParameters(
            command=constat, args=["--workspace", home, "mcp"]
        )

    def test_the_loop_runs_and_nothing_is_accepted(self, home: str):
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async def run():
            async with stdio_client(self._session(home)) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()

                    listed = await session.list_tools()
                    names = sorted(t.name for t in listed.tools)

                    await session.call_tool("gather_evidence", {"reference": "622"})
                    reply = json.dumps(
                        {
                            "rules": [
                                {
                                    "name": "daily-limit",
                                    "statement": "A transfer over the limit is refused.",
                                    "anchors": [{"path_glob": "rules.py"}],
                                }
                            ]
                        }
                    )
                    submitted = await session.call_tool(
                        "submit_rules", {"reference": "622", "reply": reply}
                    )
                    return names, json.loads(submitted.content[0].text)

        names, submitted = asyncio.run(run())

        assert names == sorted(EXPOSED_TOOLS)
        assert submitted["accepted"] is False
        assert len(submitted["stored"]) == 1

    def test_a_refusal_arrives_as_an_error_with_its_message(self, leaky_home: str):
        """The real contract: `isError`, and the reason intact."""
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async def run():
            async with stdio_client(self._session(leaky_home)) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    return await session.call_tool(
                        "get_payload", {"reference": "622"}
                    )

        result = asyncio.run(run())

        assert result.is_error
        text = " ".join(c.text for c in result.content if hasattr(c, "text"))
        assert "refusing to send" in text
        assert AWS_KEY not in text


class TestMcpIsExemptFromTheProviderGate:
    """D-059 exempts this path, and the exemption is the design (D-045).

    On MCP the **host** supplies the model, so Constat having no provider is
    correct rather than a misconfiguration. If `gather_evidence` refused the
    way the CLI does, the entire intended workflow would stop working on a
    machine with no API key — which is the machine it was designed for.
    """

    def test_gathering_works_with_no_provider_configured(self, home, monkeypatch):
        monkeypatch.delenv("CONSTAT_AI_PROVIDER", raising=False)
        result = json_of(call(home, "gather_evidence", reference="622"))

        assert result["repositories_searched"] >= 1

    def test_the_payload_is_readable_with_no_provider_configured(
        self, home, monkeypatch
    ):
        """The whole point of the MCP path: the evidence goes out, the host's
        model reads it, and Constat never needed a key."""
        monkeypatch.delenv("CONSTAT_AI_PROVIDER", raising=False)
        call(home, "gather_evidence", reference="622")
        payload = json_of(call(home, "get_payload", reference="622"))

        assert payload["reference"] == "622"

    def test_no_tool_mentions_the_provider_gate(self):
        """A `--no-provider` equivalent would be meaningless here, so there
        must not be one to pass."""
        from constat.mcp import EXPOSED_TOOLS

        assert "no_provider" not in " ".join(EXPOSED_TOOLS)


class TestDocumentingAnAreaOverMcp:
    """CON-101. The tool D-080 left unbuilt.

    That decision chose the agent-driven shape for a baseline *because* an
    agent already has the repository and can read it directly — and then left
    the only door at the command line, so the reasoning and the surface
    disagreed. The tool closes that, and adds nothing else: every refusal
    below is `operations.baseline_area` behaving exactly as the CLI makes it
    behave (D-098).
    """

    REPLY = json.dumps(
        {
            "rules": [
                {
                    "name": "daily-limit",
                    "statement": "A transfer above the daily limit is refused.",
                    "anchors": [{"path_glob": "rules.py"}],
                    "area": "payments",
                }
            ]
        }
    )

    def test_it_is_in_the_exposed_list(self):
        assert "baseline_area_tool" in EXPOSED_TOOLS

    def test_a_reading_is_stored_and_not_accepted(self, home):
        result = json_of(
            call(home, "baseline_area_tool", area="payments", reply=self.REPLY)
        )

        assert len(result["stored"]) == 1
        assert result["accepted"] is False

    def test_it_needs_no_ticket(self, home):
        """The cold start this exists for. A baseline is not a unit of work, so
        requiring a reference would mean inventing one by hand first."""
        result = json_of(
            call(home, "baseline_area_tool", area="payments", reply=self.REPLY)
        )

        assert result["reference"] == "baseline-payments"
        assert result["opened_reference"] is True

    def test_the_invented_reference_is_reported_as_opened(self, home):
        """Because it turns up in `ticket list`, and a reference appearing
        there unannounced reads as work somebody forgot about."""
        first = json_of(
            call(home, "baseline_area_tool", area="payments", reply=self.REPLY)
        )
        second = json_of(
            call(home, "baseline_area_tool", area="payments", reply=self.REPLY)
        )

        assert first["opened_reference"] is True
        assert second["opened_reference"] is False

    def test_it_says_which_revision_it_described(self, home):
        """A baseline has no diff, so the only thing locating it in history is
        the mainline commit it was read at (D-080)."""
        result = json_of(
            call(home, "baseline_area_tool", area="payments", reply=self.REPLY)
        )

        described = result["described_at"]
        assert [d["repository"] for d in described] == ["billing"]
        assert len(described[0]["revision"]) == 40

    def test_a_second_call_adds_rather_than_replaces(self, home):
        """Incremental by construction: proposals are append-only, so running
        it twice cannot quietly drop the first reading."""
        call(home, "baseline_area_tool", area="payments", reply=self.REPLY)
        call(
            home,
            "baseline_area_tool",
            area="payments",
            reply=json.dumps(
                {
                    "rules": [
                        {
                            "name": "a-refusal-names-the-limit",
                            "statement": "A refused transfer tells the customer the limit.",
                            "anchors": [{"path_glob": "rules.py"}],
                            "area": "payments",
                        }
                    ]
                }
            ),
        )

        with Workspace.open(home) as workspace:
            waiting = RuleProposals(workspace).across_workspace("awaiting")

        assert {p.proposal.name for p in waiting} == {
            "daily-limit",
            "a-refusal-names-the-limit",
        }

    def test_a_reading_of_another_area_is_kept_apart_from_a_refusal(self, home):
        """An out-of-area reading is a correct reading of the wrong area, not a
        malformed one, and reporting the two together mislabelled it (D-080)."""
        result = json_of(
            call(
                home,
                "baseline_area_tool",
                area="payments",
                reply=json.dumps(
                    {
                        "rules": [
                            {
                                "name": "sign-in-locks",
                                "statement": "An account locks after five failed sign-ins.",
                                "anchors": [{"path_glob": "rules.py"}],
                                "area": "access",
                            }
                        ]
                    }
                ),
            )
        )

        assert [r["name"] for r in result["out_of_area"]] == ["sign-in-locks"]
        assert result["discarded"] == []
        assert result["stored"] == []

    def test_an_ungrounded_anchor_is_still_discarded(self, home):
        """The gate that makes a baseline worth reading. Nothing supplies
        evidence here, so an anchor is checked against mainline instead — and
        an invented path fails the same way it does on the ticket path."""
        result = json_of(
            call(
                home,
                "baseline_area_tool",
                area="payments",
                reply=json.dumps(
                    {
                        "rules": [
                            {
                                "name": "invented",
                                "statement": "Something happens somewhere.",
                                "anchors": [{"path_glob": "no/such/file.py"}],
                                "area": "payments",
                            }
                        ]
                    }
                ),
            )
        )

        assert result["stored"] == []
        assert [r["name"] for r in result["discarded"]] == ["invented"]

    def test_a_statement_that_leaks_code_is_refused(self, home):
        """One door, one set of gates (D-045)."""
        result = call(
            home,
            "baseline_area_tool",
            area="payments",
            reply=json.dumps(
                {
                    "rules": [
                        {
                            "name": "leaky",
                            "statement": "A transfer is refused by rules.py.",
                            "anchors": [{"path_glob": "rules.py"}],
                            "area": "payments",
                        }
                    ]
                }
            ),
        )

        assert [r["name"] for r in json_of(result)["discarded"]] == ["leaky"]

    def test_coining_an_area_is_reported_and_not_declared(self, home):
        """D-079 declares an area **by acceptance**, and a baseline must not be
        the exception: a proposal that invents "payments" tells the reviewer it
        did, and the catalogue still has no such area until somebody accepts.
        Otherwise an agent could populate the structure coverage is measured
        against without a decision."""
        result = json_of(
            call(home, "baseline_area_tool", area="payments", reply=self.REPLY)
        )

        coined = list(result["new_areas"].values())
        assert [c["area"] for c in coined] == ["payments"]
        with Workspace.open(home) as workspace:
            assert Catalogue(workspace).areas() == ()

    def test_it_works_with_no_provider_configured(self, home, monkeypatch):
        """The machine this path was designed for. The host supplies the model,
        so there is nothing for Constat to be configured with (D-045, D-059)."""
        monkeypatch.delenv("CONSTAT_AI_PROVIDER", raising=False)

        result = json_of(
            call(home, "baseline_area_tool", area="payments", reply=self.REPLY)
        )

        assert len(result["stored"]) == 1


class TestTheBaselinePromptNamesTheAreasThatExist:
    """The gap the tool opened, and the reason to check it separately.

    `baseline_area` builds a payload carrying the whole catalogue, but uses it
    only to ground anchors and spot duplicates — it never returns it. So an
    agent documenting an area could not see which areas already existed, and
    D-079's defence against "ads" arriving beside "advertising" depends on
    exactly that. The ticket path gets it from `get_payload`; this path had
    nothing until the prompt said it.
    """

    def rendered(self, home: str, area: str = "payments") -> str:
        got = asyncio.run(build_server(home).get_prompt("baseline", {"area": area}))
        return got.messages[0].content.text

    def _declare(self, home: str, *areas: str) -> None:
        from constat.store.areas import Areas

        with Workspace.open(home) as workspace:
            for area in areas:
                Areas(workspace).declare(area, declared_by="a person")

    def test_the_declared_areas_are_named(self, home):
        self._declare(home, "advertising", "access")

        text = self.rendered(home)

        assert "advertising" in text and "access" in text

    def test_it_asks_for_a_synonym_to_be_called_out(self, home):
        self._declare(home, "advertising")

        text = self.rendered(home, "ads")

        assert "under another name" in text

    def test_an_area_only_proposed_is_named_as_awaiting(self, home):
        """The hole the declared-areas list alone leaves. An area is declared
        by acceptance (D-079), so two baselines run back to back would both be
        told "no areas yet" and the second would coin the very synonym the
        first had already avoided."""
        call(
            home,
            "baseline_area_tool",
            area="payments",
            reply=TestDocumentingAnAreaOverMcp.REPLY,
        )

        text = self.rendered(home, "ads")

        assert "awaiting a decision in **payments**" in text
        assert "no areas yet" not in text

    def test_a_declared_area_is_not_also_listed_as_awaiting(self, home):
        """Or the same name appears twice in one sentence, which reads as two
        areas rather than one."""
        self._declare(home, "payments")
        call(
            home,
            "baseline_area_tool",
            area="payments",
            reply=TestDocumentingAnAreaOverMcp.REPLY,
        )

        text = self.rendered(home, "ads")

        assert text.count("**payments**") == 1
        assert "awaiting a decision" not in text

    def test_an_empty_catalogue_says_so_rather_than_listing_nothing(self, home):
        """"The catalogue already has these areas:" followed by nothing reads
        as a bug, and an agent cannot tell it from a failed lookup."""
        text = self.rendered(home)

        assert "no areas yet" in text
        assert "already has these areas" not in text

    def test_it_still_renders_without_a_workspace(self, tmp_path):
        """A prompt that refused because `constat init` had not been run would
        be worse than one with a sentence missing: the rest is still correct."""
        text = asyncio.run(
            build_server(str(tmp_path / "absent")).get_prompt(
                "baseline", {"area": "payments"}
            )
        ).messages[0].content.text

        assert "payments" in text


class TestThePrompts:
    """CON-66. A tool is what the model chooses to call; a prompt is what the
    *user* invokes, and clients surface it as a slash command.

    An MCP server cannot initiate anything — it only answers. So the user has
    to start the loop, and before these existed that meant describing it in a
    sentence every time. Friction with no principle behind it.
    """

    def prompts(self):
        import asyncio

        return asyncio.run(build_server("/tmp").list_prompts())

    #: The one argument each prompt takes. A baseline has no ticket, so there
    #: is no reference to give it (CON-101, D-098).
    ARGUMENT = {"document": "reference", "review": "reference", "baseline": "area"}

    def rendered(self, name: str, value: str = "622") -> str:
        import asyncio

        argument = self.ARGUMENT[name]
        if name == "baseline" and value == "622":
            value = "payments"
        got = asyncio.run(
            build_server("/tmp").get_prompt(name, {argument: value})
        )
        return got.messages[0].content.text

    def test_the_prompt_list_is_what_it_claims(self):
        """Asserted like the tool list, for the same reason: the shape of
        these lists is the governance model, not an implementation detail."""
        from constat.mcp import EXPOSED_PROMPTS

        assert tuple(sorted(p.name for p in self.prompts())) == tuple(
            sorted(EXPOSED_PROMPTS)
        )

    def test_each_takes_exactly_one_argument(self):
        """And it is the one thing the user already knows: the ticket
        reference, or — for a baseline, which has no ticket — the area. A
        prompt that needed two would be a form, and a slash command is not a
        form."""
        for prompt in self.prompts():
            assert [a.name for a in prompt.arguments or []] == [
                self.ARGUMENT[prompt.name]
            ]

    def test_the_document_prompt_drives_the_whole_loop(self):
        text = self.rendered("document")

        for tool in ("gather_evidence", "get_payload", "submit_rules"):
            assert tool in text
        assert "622" in text

    def test_it_carries_the_guidance_the_provider_path_has(self):
        """The real gap this closed. Tool descriptions can say what a tool
        does; they are a poor place to explain what a business rule is, and
        nothing on the MCP path was explaining it at all."""
        from constat.ai.guidance import WHAT_A_RULE_IS

        assert WHAT_A_RULE_IS in self.rendered("document")

    def test_the_guidance_is_shared_with_the_provider(self):
        """A rule proposed over MCP and the same rule proposed by a provider
        must mean the same thing, or the catalogue becomes a record of which
        path happened to be configured."""
        from constat.ai.guidance import ANCHORS, WHAT_A_RULE_IS
        from constat.ai.providers.anthropic import SYSTEM

        for shared in (WHAT_A_RULE_IS, ANCHORS):
            assert shared in SYSTEM
            assert shared in self.rendered("document")

    def test_no_prompt_instructs_acceptance(self):
        """D-055 reaches the prompts too. A model that could be *told* to
        accept is only one missing tool away from accepting."""
        from constat.mcp import FORBIDDEN_TOOLS

        for prompt in self.prompts():
            text = self.rendered(prompt.name).lower()
            assert "nothing you propose is accepted" in text or "cannot accept" in text
            for forbidden in FORBIDDEN_TOOLS:
                assert f"call `{forbidden}" not in text

    def test_the_review_prompt_refuses_to_recommend(self):
        """The natural shape of "summarise what is waiting" is to end with a
        recommendation, and a recommendation from the thing that wrote the
        proposal is not a review."""
        text = self.rendered("review")

        assert "Do not recommend accepting or rejecting" in text
        assert "constat rule accept" in text   # names the human's command

    def test_the_review_prompt_keeps_the_empty_queue_honest(self):
        text = self.rendered("review")
        assert "not a statement that the ticket has no rules" in text

    def test_the_document_prompt_does_not_route_around_refusals(self):
        """A refusal is the product working. An agent told to "get it done"
        would retry with --accept-scan-findings, which is the one thing that
        must stay a human act."""
        text = self.rendered("document")

        assert "rather than working around it" in text
        assert "accept-scan-findings" not in text
