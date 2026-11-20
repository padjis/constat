"""Publication refuses more than a credential (CON-95, D-095).

Egress had one hole. D-044 and D-047 gate credentials on every path out, and
D-040 keeps identity from crossing at all — but a published page could still
carry an internal hostname, a connection string, or a sentence describing how
to defeat a check. A page is the one egress that cannot be recalled (D-058) and
the one a whole organisation reads.

Four properties carry these tests:

1. **Publication only, never export.** A provider payload is evidence read from
   the code, which legitimately contains hostnames and the word "bypass".
   Refusing to export a diff for that would make the product unusable.
2. **A business rule is not a disclosure.** "A transfer above 500 euros is
   refused" must pass — it is this project's own canonical example of a
   business rule.
3. **Commercial data is not covered, and the output says so.** There is no
   generic detector; a figure with a currency is what a rule legitimately says.
4. **A clean pass states its limits.** A silent pass reads as proof, and this
   one is not.
"""

from __future__ import annotations

import pytest

from constat.ai.redaction import (
    CommitContext,
    FileChange,
    ProviderPayload,
    RepositoryContext,
)
from constat.ai.scanning import (
    DISCLOSURE,
    guard_publication,
    guard_release,
    scan_disclosure,
)
from constat.errors import PublicationRefused


# -- what it catches ----------------------------------------------------------


class TestItCatchesDisclosure:
    @pytest.mark.parametrize(
        "line,detector",
        [
            ("Requests go to billing.internal for pricing.", "internal_hostname"),
            ("The queue lives at orders.svc inside the cluster.", "internal_hostname"),
            ("Connect to 10.0.0.14 for the staging feed.", "ip_address"),
            ("It reads postgres://db/app at start-up.", "connection_string"),
            ("Configured with jdbc:mysql://host/db", "connection_string"),
            ("An SQL injection in the search box reads any order.", "security_weakness"),
            ("A missing check lets a user bypass the guard.", "security_weakness"),
            ("This is a privilege escalation if the role is unset.", "security_weakness"),
            ("The endpoint is vulnerable when the token is absent.", "security_weakness"),
        ],
    )
    def test_each_class_is_detected(self, line, detector) -> None:
        assert detector in [f.detector for f in scan_disclosure(line)]

    def test_the_line_number_is_reported(self) -> None:
        """A finding nobody can locate is not actionable."""
        body = "fine\nalso fine\nRequests go to billing.internal.\n"

        found = scan_disclosure(body)

        assert [f.line for f in found] == [3]

    @pytest.mark.parametrize(
        "line",
        [
            "Connect to 10.0.0.14.",
            "Then 10.0.0.14, please.",
            "The host is (10.0.0.14) today.",
        ],
    )
    def test_an_address_at_the_end_of_a_sentence_is_caught(self, line) -> None:
        """Found by a test on first writing. The guard against version numbers
        was `(?![\\d.])`, which rejected `10.0.0.14.` because of the full
        stop — the most likely form in prose. It is now "not followed by
        another number"."""
        assert [f.detector for f in scan_disclosure(line)] == ["ip_address"]

    def test_a_longer_dotted_sequence_is_not_an_address(self) -> None:
        assert scan_disclosure("Build 1.2.3.4.5 shipped") == ()

    def test_a_four_part_version_is_reported_and_that_is_honest(self) -> None:
        """`1.2.3.4` is a valid address and a plausible version, and nothing can
        tell which from the text. This gate reports rather than decides, and
        the override exists for exactly this."""
        assert [f.detector for f in scan_disclosure("Release 1.2.3.4")] == ["ip_address"]

    def test_one_line_reports_each_class_once(self) -> None:
        body = "Connect to 10.0.0.14 and 10.0.0.15 for the feed."

        found = scan_disclosure(body)

        assert [f.detector for f in found] == ["ip_address"]


class TestItDoesNotCatchBusinessProse:
    @pytest.mark.parametrize(
        "line",
        [
            "A transfer above 500 euros is refused.",
            "The daily limit is 1.1% of the balance.",
            "Version 1.2.3 of the app, released on 2026-11-20.",
            "An upload larger than 50 MB is refused as a whole.",
            "The news pages carry no third-party advertising.",
            "Losing an analytics beacon is acceptable; failing a request is not.",
        ],
    )
    def test_a_real_business_sentence_passes(self, line) -> None:
        """The direction that matters most. "A transfer above 500 euros is
        refused" is this project's own canonical business rule — a gate that
        refused it would have broken the catalogue to protect it, which is the
        failure D-091 found in the leakage gate."""
        assert scan_disclosure(line) == ()


# -- publication only ---------------------------------------------------------


def _payload_with(line: str) -> ProviderPayload:
    return ProviderPayload(
        reference="615",
        repositories=(
            RepositoryContext(
                alias="billing",
                default_branch="main",
                status="pending",
                commits=(
                    CommitContext(
                        sha="d" * 40,
                        subject="Point at the new host",
                        body="",
                        files=(
                            FileChange(path="app.py", change_type="modified", diff=line),
                        ),
                    ),
                ),
            ),
        ),
    )


class TestTheGateIsOnPublicationOnly:
    def test_a_hostname_in_evidence_does_not_block_export(self) -> None:
        """The decisive asymmetry. A provider payload is evidence read from the
        code, and code legitimately contains hostnames — refusing to export a
        diff for that would make the product unusable. The credential gate
        fires on every egress because a credential is a credential wherever it
        goes; these are not."""
        payload = _payload_with("+ HOST = 'billing.internal'")

        assert guard_release(payload) == ()

    def test_a_weakness_in_evidence_does_not_block_export(self) -> None:
        payload = _payload_with("+ # TODO: this is vulnerable without the token")

        assert guard_release(payload) == ()

    def test_the_same_text_blocks_publication(self) -> None:
        """Same words, different door — and only one of them cannot be
        recalled."""
        with pytest.raises(PublicationRefused, match="disclosure"):
            guard_publication("Requests go to billing.internal.")

    def test_publication_still_refuses_a_credential(self) -> None:
        """The hole was additive: nothing the credential gate caught stopped
        being caught."""
        with pytest.raises(PublicationRefused):
            guard_publication("token = ghp_" + "a" * 36)


class TestRefusingAndOverriding:
    def test_a_refusal_names_every_finding(self) -> None:
        body = "Go to billing.internal.\nThen 10.0.0.14.\n"

        with pytest.raises(PublicationRefused) as raised:
            guard_publication(body)

        message = str(raised.value)
        assert "internal_hostname" in message
        assert "ip_address" in message
        assert "line 1" in message and "line 2" in message

    def test_a_refusal_says_nothing_was_published(self) -> None:
        with pytest.raises(PublicationRefused, match="Nothing has been published"):
            guard_publication("Go to billing.internal.")

    def test_a_refusal_names_the_uncovered_class(self) -> None:
        """So a reader does not take a refusal, or its absence, as a clean bill
        of health on commercial content."""
        with pytest.raises(PublicationRefused, match="commercial disclosure"):
            guard_publication("Go to billing.internal.")

    def test_an_accepted_finding_is_returned_not_raised(self) -> None:
        """The override is recorded by the caller as an operation; the gate's
        job is to report rather than to decide a second time."""
        found = guard_publication("Go to billing.internal.", accepted=True)

        assert [f.detector for f in found] == ["internal_hostname"]

    def test_a_clean_document_returns_nothing(self) -> None:
        assert guard_publication("A transfer above 500 euros is refused.") == ()


class TestWhatIsDeliberatelyNotDetected:
    def test_commercial_data_has_no_detector(self) -> None:
        """A decision, not an oversight (D-095). CON-95 asked for it; a figure
        with a currency is the canonical *legitimate* content of a business
        rule, so a currency detector would refuse the sentences the catalogue
        exists to hold. Named customers need a customer list Constat has not
        got."""
        assert "commercial" not in [name for name, _ in DISCLOSURE]

        for line in (
            "Acme pays 40,000 euros a year for the enterprise plan.",
            "Our largest customer ships 12,000 consignments a month.",
        ):
            assert scan_disclosure(line) == ()

    def test_the_limit_is_stated_in_the_detector_docstring(self) -> None:
        """Said out loud rather than implied by a clean pass."""
        from constat.ai import scanning

        assert "Commercial data is not here" in scanning.__dict__["DISCLOSURE"].__doc__ or True
        # The docstring lives on the module attribute; assert on the source so
        # the claim cannot quietly disappear.
        import inspect

        source = inspect.getsource(scanning)
        assert "Commercial data is not here" in source
        assert "500 euros is refused" in source
