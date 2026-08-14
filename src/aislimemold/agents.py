"""Agents: deterministic scripted agents and the LLM adapter seam.

SlimeMold is designed so that the *default* experiment corpus is fully
reproducible: scripted agents make decisions from a small, documented rule set
driven only by the seeded RNG. The same decision interface is exposed to real
LLM/human agents through :class:`AgentPolicy`, so a design can be tested with
both scripted and live agents without changing the engine.

The agent policy asks the agent one question at a time:

* ``decide_task_action`` -- given a task and its knowledge/context, pick
  ``"execute"`` (start work), ``"delegate"`` (pass to a subordinate),
  ``"escalate"`` (push up), or ``"reject"``.
* ``decide_approval`` -- approve or reject a submitted work product.
* ``decide_consult_response`` -- answer a consultation.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class AgentPolicy(ABC):
    """Decision interface for any agent kind (scripted, LLM or human)."""

    @abstractmethod
    def decide_task_action(
        self,
        ctx: dict[str, Any],
    ) -> str:
        """Return ``execute`` | ``delegate`` | ``escalate`` | ``reject``."""

    @abstractmethod
    def decide_approval(self, ctx: dict[str, Any]) -> bool:
        """Return True to approve a submitted work product."""

    @abstractmethod
    def decide_consult_response(self, ctx: dict[str, Any]) -> bool:
        """Return True to recommend the consulting party proceed."""


@dataclass
class ScriptedPolicy(AgentPolicy):
    """Transparent, documented rule-based policy.

    Parameters
    ----------
    error_probability:
        Baseline probability a task attempt fails (quality/competence).
    delegate_when_possible:
        If True, delegates whenever a capable subordinate exists (promotes
        hierarchical task splitting and manager throughput).
    escalation_probability:
        Probability of pushing a task up instead of attempting it.
    risk_aversion:
        In [0, 1]; how much high-risk work is avoided (drives rejections).
    knowledge_weight:
        Weight of the knowledge effect in the success probability.
    """

    error_probability: float = 0.08
    delegate_when_possible: bool = True
    escalation_probability: float = 0.05
    risk_aversion: float = 0.0
    knowledge_weight: float = 0.4

    def decide_task_action(self, ctx: dict[str, Any]) -> str:
        rng: random.Random = ctx["rng"]
        risky = ctx["risky"]
        # Risk-averse agents reject high-risk work they cannot consult about.
        if risky and self.risk_aversion > 0 and rng.random() < self.risk_aversion:
            return "reject"
        if rng.random() < self.escalation_probability:
            return "escalate"
        subordinates = ctx.get("capable_subordinates", [])
        if self.delegate_when_possible and subordinates:
            return "delegate"
        return "execute"

    def decide_approval(self, ctx: dict[str, Any]) -> bool:
        rng: random.Random = ctx["rng"]
        # Approvers are "faulty": they occasionally miss problems (error).
        error = self.error_probability
        quality = ctx.get("submitted_quality", 0.8)
        if rng.random() < error:
            return True  # rubber-stamp (miss)
        return quality >= 0.5

    def decide_consult_response(self, ctx: dict[str, Any]) -> bool:
        rng: random.Random = ctx["rng"]
        return rng.random() >= self.error_probability * 0.5


class LLMAgentAdapter(AgentPolicy):
    """Adapter that turns an LLM (or a human in the loop) into an AgentPolicy.

    The engine never calls the LLM synchronously inside the turn loop. Instead
    ``decide_*`` returns the *request* to be resolved by the harness; a real
    implementation should subclass and call the LLM API (or route the request
    to a human UI) then return the parsed decision.

    ``DummyLLMAdapter`` is provided for tests: it returns a deterministic
    answer, so tests of the adapter seam need no network access.
    """

    def decide_task_action(self, ctx: dict[str, Any]) -> str:
        return self.invoke("decide_task_action", ctx)

    def decide_approval(self, ctx: dict[str, Any]) -> bool:
        return bool(self.invoke("decide_approval", ctx))

    def decide_consult_response(self, ctx: dict[str, Any]) -> bool:
        return bool(self.invoke("decide_consult_response", ctx))

    def invoke(self, method: str, ctx: dict[str, Any]) -> Any:
        raise NotImplementedError(
            "subclass must implement invoke(); see DummyLLMAdapter"
        )


class DummyLLMAdapter(LLMAgentAdapter):
    """Deterministic stand-in used to test the LLM integration seam."""

    def invoke(self, method: str, ctx: dict[str, Any]) -> Any:
        if method == "decide_task_action":
            subordinates = ctx.get("capable_subordinates", [])
            if subordinates:
                return "delegate"
            return "execute"
        if method == "decide_approval":
            return True
        return True
