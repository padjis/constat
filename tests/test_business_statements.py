"""A rule statement must be a business statement (CON-74, D-066).

Two things are tested and they are not the same thing:

1. **Leakage is refused mechanically** — an identifier, a path, an endpoint,
   an annotation in a statement or a behaviour. Refused with the offending
   token named, so the reading is told what to remove.
2. **A business sentence survives.** This half matters more than the first.
   A check that refuses "a transfer above 500 euros is refused" has broken
   the product to protect it, and the canonical business rule in this project
   contains a number that looks exactly like an HTTP status.

**What is deliberately not tested, because it is not implemented:** that a
statement is business-*oriented*. No check can decide that, and the sentence
that caused D-066 — "a first launch succeeds even when several requests arrive
at once" — contains no code token and passes. It is asserted here as passing,
so nobody later reads these tests as a quality guarantee they are not.
"""

from __future__ import annotations

import pytest

from constat.ai.parsing import parse
from constat.ai.redaction import ProviderPayload, RepositoryContext
from constat.ai.statements import code_leakage


# -- the detector -------------------------------------------------------------


class TestLeakageIsCaught:
    @pytest.mark.parametrize(
        "statement, expected",
        [
            ("findOrCreateDevice reads then inserts.", "an identifier"),
            ("DeviceProvisioningService adopts the row.", "an identifier"),
            ("The device row is read from PostgreSQL.", "an identifier"),
            ("UserNameService.release undoes it.", "an identifier"),
            ("The loader in functions/_lib/render.ts is gone.", "a file path"),
            ("A request to /v2/configuration/list succeeds.", "a file path"),
            ("The call returns HTTP 500.", "an HTTP method or status"),
            ("A GET for the feed is cached.", "an HTTP method or status"),
            ("The application_id index rejects duplicates.", "a snake_case identifier"),
            ("The row is locked with @Transactional.", "an annotation or decorator"),
            ("The handler calls poll() first.", "a function call"),
            ("The field is set to `true`.", "a code fence or inline code"),
        ],
    )
    def test_each_kind_of_leak(self, statement: str, expected: str) -> None:
        found = code_leakage(statement)
        assert found is not None, statement
        assert found.startswith(expected), found

    def test_the_reason_names_the_offending_token(self) -> None:
        """A reading told "not business-oriented" has nothing to act on."""
        found = code_leakage("findOrCreateDevice reads then inserts.")
        assert "findOrCreateDevice" in found


class TestBusinessSentencesSurvive:
    """The half that protects the product from the check.

    Every case here is a sentence a product owner would recognise, and each
    one trips a pattern that a less careful detector would have refused.
    """

    @pytest.mark.parametrize(
        "statement",
        [
            # A three-digit number is money far more often than a status code.
            "A transfer above 500 euros is refused.",
            "An order over 404 euros needs a second approval.",
            # All-caps business vocabulary is not an identifier.
            "A VAT invoice is issued for every order.",
            "An SMS confirmation is sent within one minute.",
            "A KYC check precedes the first payout.",
            "A PDF statement stays available for seven years.",
            # One internal capital is a brand, not a class.
            "The site is not approved by Google AdSense.",
            # The project's own accepted rule 1.
            "237feed's news and feed content pages carry no third-party "
            "advertising while the site is not approved by the ad network.",
            # Prose abbreviations look like qualified names.
            "Users see their balance before 9 a.m., i.e. before trading opens.",
        ],
    )
    def test_it_is_not_refused(self, statement: str) -> None:
        assert code_leakage(statement) is None, code_leakage(statement)

    def test_the_sentence_that_caused_the_decision_still_passes(self) -> None:
        """Honesty about the limit, asserted so it cannot be forgotten.

        This statement is why D-066 exists and it is *not* a business
        sentence — "several requests at once" is the cause of a bug wearing a
        rule's clothes. No syntactic check can catch it. The guidance and the
        reviewer are what stop it, and anyone reading this file is entitled to
        know that.
        """
        leaky = (
            "A device's first use of the app is served successfully even when "
            "the app's launch sends several requests at once."
        )
        assert code_leakage(leaky) is None


# -- the parse gate -----------------------------------------------------------


def _payload() -> ProviderPayload:
    return ProviderPayload(
        reference="628",
        repositories=(
            RepositoryContext(alias="billing", default_branch="main", status="pending"),
        ),
    )


def _reply(statement: str, behaviour: str = "The limit is explained") -> str:
    import json

    return json.dumps(
        {
            "rules": [
                {
                    "name": "daily-limit",
                    "statement": statement,
                    "behaviours": [behaviour],
                    "anchors": [{"path_glob": "rules.py", "repository_alias": "billing"}],
                }
            ]
        }
    )


class TestTheParseGate:
    """Grounding is checked against a payload, so these go through `parse`.

    `_payload` carries no commits, so no anchor can be grounded — which means
    a rejection here could be either reason. Each test therefore asserts on
    the *reason*, never merely on the count.
    """

    def test_a_leaking_statement_is_refused_with_its_reason(self) -> None:
        result = parse(_reply("findOrCreateDevice reads then inserts."), _payload())

        assert result.proposals == ()
        assert len(result.rejections) == 1
        reason = result.rejections[0].reason
        assert "not a business statement" in reason
        assert "findOrCreateDevice" in reason
        assert "D-066" in reason

    def test_a_leaking_behaviour_is_refused_too(self) -> None:
        """A clean statement with technical behaviours is still a technical rule."""
        result = parse(
            _reply(
                "A transfer above the daily limit is refused.",
                behaviour="DeviceProvisioningService adopts the row",
            ),
            _payload(),
        )

        assert result.proposals == ()
        reason = result.rejections[0].reason
        assert "a behaviour is not a business statement" in reason
        assert "DeviceProvisioningService" in reason

    def test_a_business_statement_reaches_the_anchor_check(self) -> None:
        """The gate must not stand in for grounding.

        A clean statement should fail here for the *anchor*, not the wording —
        proof that a good sentence passes the new check rather than being
        caught by it for the wrong reason.
        """
        result = parse(_reply("A transfer above 500 euros is refused."), _payload())

        assert result.proposals == ()
        assert result.rejections[0].reason == "no anchor grounded in the evidence supplied"


# -- the guidance says it, on both paths --------------------------------------


class TestGuidance:
    def test_the_test_is_stated_positively(self) -> None:
        """The rule for a reader is one question, not a list of prohibitions."""
        from constat.ai.guidance import WHAT_A_RULE_IS

        assert "would have an opinion on" in WHAT_A_RULE_IS
        assert "read aloud to a product owner" in WHAT_A_RULE_IS

    def test_a_bug_fix_is_called_out_as_usually_no_rule(self) -> None:
        """The cause of the three bad proposals on 628 (CON-73's interim half)."""
        from constat.ai.guidance import WHAT_A_RULE_IS

        assert "bug fix" in WHAT_A_RULE_IS
        assert "restores conformance" in WHAT_A_RULE_IS

    def test_both_paths_carry_it(self) -> None:
        import asyncio

        from constat.ai.guidance import WHAT_A_RULE_IS, for_system_prompt
        from constat.mcp import build_server

        assert WHAT_A_RULE_IS in for_system_prompt()
        got = asyncio.run(build_server("/tmp").get_prompt("document", {"reference": "628"}))
        assert WHAT_A_RULE_IS in got.messages[0].content.text
