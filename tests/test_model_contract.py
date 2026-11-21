"""Every published model is immutable and strict (`Frozen`).

This used to live in `test_models.py`, which went with `analyse` and
`snapshot` (CON-104) because every one of its cases exercised a model that
existed only for them. Two of its properties were not about those models at
all, and keeping them attached to deleted ones would have lost them quietly:

1. **Immutable.** A governance record that can be edited in place is not a
   record. The whole catalogue depends on this.
2. **`extra="forbid"`.** A typo'd key silently accepted would vanish from a
   record with nobody noticing — the failure is invisible by construction,
   which is why it is asserted rather than assumed.

Asserted against `Rule`, a model that is actually persisted, rather than
against `Frozen` directly: the contract matters where it is relied on.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from constat.models import Rule


def _a_rule() -> Rule:
    return Rule(
        name="daily-limit",
        statement="A transfer above the daily limit is refused.",
        created_at=datetime(2026, 11, 21, tzinfo=timezone.utc),
    )


class TestThePublishedModelContract:
    def test_a_model_cannot_be_mutated(self) -> None:
        rule = _a_rule()

        with pytest.raises(ValidationError):
            rule.statement = "Something else"  # type: ignore[misc]

    def test_an_unknown_field_is_refused(self) -> None:
        """A typo'd key must not vanish silently from a governance record."""
        with pytest.raises(ValidationError):
            Rule(
                name="daily-limit",
                statemnet="A transfer above the daily limit is refused.",  # typo
                created_at=datetime(2026, 11, 21, tzinfo=timezone.utc),
            )

    def test_a_required_field_is_refused_when_empty(self) -> None:
        with pytest.raises(ValidationError):
            Rule(
                name="",
                statement="A transfer above the daily limit is refused.",
                created_at=datetime(2026, 11, 21, tzinfo=timezone.utc),
            )
