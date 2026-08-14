"""Turnover: membership volatility and its knowledge/competence cost.

Turnover models members leaving and being replaced. Leaving removes:

* the member's personal experience/competence from the role;
* a fraction of the member's personal knowledge (what was only in their head).

New members arrive with lower experience and an empty personal knowledge
store, so performance dips after a turnover event and recovers as the new
member re-learns (the resilience curve). The mechanism exposes both a fixed
per-turn per-member probability and deterministic scheduled departure events,
which keeps resilience experiments reproducible.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .roles import Member


@dataclass
class Turnover:
    """Turnover scheduler.

    Parameters
    ----------
    per_turn_probability:
        Probability each active member departs each turn.
    schedule:
        Optional dict ``turn -> [role_id, ...]`` forcing specific departures
        at specific turns (for planned resilience stress tests).
    replace_experience:
        Experience of the incoming replacement member.
    onboarding_turns:
        Turns before a replacement is fully functional (their experience ramps).
    knowledge_loss_fraction:
        Fraction of the departing member's knowledge lost to the org.
    """

    per_turn_probability: float = 0.0
    schedule: dict[int, list[str]] = field(default_factory=dict)
    replace_experience: float = 0.2
    onboarding_turns: int = 10
    knowledge_loss_fraction: float = 0.8

    def __post_init__(self) -> None:
        self._generation: dict[str, int] = {}

    def step(
        self,
        turn: int,
        members: dict[str, Member],
        rng: random.Random,
        on_departure=None,
    ) -> list[str]:
        """Advance turnover; return ids of departing members.

        ``on_departure`` is an optional callback ``(member) -> None`` used by
        the simulation to scrub personal knowledge.
        """
        departing: list[str] = []
        if turn in self.schedule:
            for role_id in self.schedule[turn]:
                if role_id in members:
                    departing.append(role_id)
        if self.per_turn_probability > 0:
            for role_id, member in list(members.items()):
                if member.is_active and rng.random() < self.per_turn_probability:
                    departing.append(role_id)
        for role_id in departing:
            member = members[role_id]
            if on_departure is not None:
                on_departure(member)
            gen = self._generation.get(role_id, 1) + 1
            self._generation[role_id] = gen
            members[role_id] = Member(
                id=f"{role_id}#v{gen}",
                role_id=role_id,
                kind=member.kind,
                experience=self.replace_experience,
                tenure=0,
                is_active=True,
            )
        return departing

    def to_dict(self) -> dict:
        return {
            "per_turn_probability": self.per_turn_probability,
            "schedule": {str(k): v for k, v in self.schedule.items()},
            "replace_experience": self.replace_experience,
            "onboarding_turns": self.onboarding_turns,
            "knowledge_loss_fraction": self.knowledge_loss_fraction,
        }
