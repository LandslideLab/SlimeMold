"""Institution: the formal rules of the game.

The institution encodes the *governance* layer that sits on top of the
reporting topology. It captures three management-theory levers:

* **delegation strategy** -- how much decision authority is pushed down:
  ``command`` (centralize), ``consultative`` (involve managers on risk),
  ``controlled`` (delegate within mandate, gate the risky), ``full`` (delegate
  everything). This operationalizes contingency-theory claims that the optimal
  delegation depends on environmental dynamism and task risk.
* **approval gates** -- explicit criteria (risk threshold, novelty, cost) that
  force a task through an approval step, whatever the role's autonomy. This is
  the agency-theory control mechanism (monitoring to curb moral hazard).
* **supervision budget** -- a finite per-manager budget of approval/consult
  interactions per period. Exhausting the budget queues requests (waiting
  time = coordination cost) and eventually escalates. This is the *span of
  control in time*: managers cannot supervise unboundedly.

Five autonomy levels (see :mod:`slimemold.autonomy`) interact with the
institution: the autonomy level decides which interactions are *required*; the
delegation strategy decides whether a manager *grants* them; the budget decides
whether the manager can *afford* them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DelegationStrategy(str, Enum):
    COMMAND = "command"
    CONSULTATIVE = "consultative"
    CONTROLLED = "controlled"
    FULL = "full"


@dataclass(frozen=True)
class ApprovalGate:
    """A rule that forces a task through approval.

    ``kind`` is one of ``"risk"``, ``"novelty"``, ``"cost"``, ``"always"``.
    ``threshold`` is the value above which the gate triggers. An ``always``
    gate has no threshold.
    """

    kind: str = "risk"
    threshold: float = 0.5
    name: str = "gate"

    def triggers(self, task) -> bool:
        if self.kind == "always":
            return True
        if self.kind == "risk":
            return task.risk >= self.threshold
        if self.kind == "novelty":
            return task.is_novel
        if self.kind == "cost":
            return task.cost >= self.threshold
        raise ValueError(f"unknown gate kind: {self.kind}")

    def to_dict(self) -> dict:
        return {"kind": self.kind, "threshold": self.threshold, "name": self.name}

    @classmethod
    def from_dict(cls, data: dict) -> ApprovalGate:
        return cls(
            kind=data.get("kind", "risk"),
            threshold=data.get("threshold", 0.5),
            name=data.get("name", "gate"),
        )


@dataclass
class Institution:
    """Governance rules for an organization design.

    Parameters
    ----------
    delegation_strategy:
        One of the :class:`DelegationStrategy` values.
    approval_gates:
        Gates that force approval regardless of autonomy.
    supervision_budget:
        Map ``manager_role_id -> max approval/consult actions per turn``. A
        value of ``None`` for a manager means "unlimited". ``default`` is
        applied to managers without an explicit entry. A budget of 0 with a
        strategy that requires approvals effectively makes those approvals
        impossible (they queue and escalate).
    approval_turn_cost:
        Turns each approval/consult consumes from the manager's capacity.
    escalation_timeout:
        Turns a request may wait before it is auto-escalated one level up.
    max_wait_turns:
        Turns a task may remain unactioned before deadlock handling kicks in.
    risk_acceptance:
        Institution-level tolerance that raises/lowers effective task risk
        (models formal risk appetite of the org).
    """

    delegation_strategy: DelegationStrategy = DelegationStrategy.CONTROLLED
    approval_gates: list[ApprovalGate] = field(default_factory=list)
    supervision_budget: dict[str, int | None] = field(default_factory=dict)
    default_supervision_budget: int | None = None
    approval_turn_cost: int = 1
    escalation_timeout: int = 5
    max_wait_turns: int = 12
    risk_acceptance: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.delegation_strategy, str):
            self.delegation_strategy = DelegationStrategy(self.delegation_strategy)

    def effective_risk(self, base_risk: float) -> float:
        """Risk adjusted by the institution's risk appetite."""
        return max(0.0, min(1.0, base_risk - self.risk_acceptance))

    def requires_approval(self, task, role) -> bool:
        """Whether a task executed by *role* must pass an approval step."""
        if any(g.triggers(task) for g in self.approval_gates):
            return True
        strategy = self.delegation_strategy
        autonomy = role.autonomy
        risky = self.effective_risk(task.risk) >= 0.5

        if strategy == DelegationStrategy.COMMAND:
            return True
        if strategy == DelegationStrategy.CONSULTATIVE:
            return risky
        if strategy == DelegationStrategy.CONTROLLED:
            if autonomy.rank <= 1:  # operator / collaborator
                return True
            return autonomy.rank == 2 and risky  # consultant + risky
        if strategy == DelegationStrategy.FULL:
            return False
        return False

    def budget_for(self, manager_role_id: str) -> int | None:
        """Max approval actions per turn for a manager (None = unlimited)."""
        return self.supervision_budget.get(
            manager_role_id, self.default_supervision_budget
        )

    def to_dict(self) -> dict:
        return {
            "delegation_strategy": self.delegation_strategy.value,
            "approval_gates": [g.to_dict() for g in self.approval_gates],
            "supervision_budget": self.supervision_budget,
            "default_supervision_budget": self.default_supervision_budget,
            "approval_turn_cost": self.approval_turn_cost,
            "escalation_timeout": self.escalation_timeout,
            "max_wait_turns": self.max_wait_turns,
            "risk_acceptance": self.risk_acceptance,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Institution:
        gates = [ApprovalGate.from_dict(g) for g in data.get("approval_gates", [])]
        budget = data.get("supervision_budget", {})
        inst = cls(
            delegation_strategy=data.get("delegation_strategy", "controlled"),
            approval_gates=gates,
            supervision_budget=dict(budget),
            default_supervision_budget=data.get("default_supervision_budget"),
            approval_turn_cost=data.get("approval_turn_cost", 1),
            escalation_timeout=data.get("escalation_timeout", 5),
            max_wait_turns=data.get("max_wait_turns", 12),
            risk_acceptance=data.get("risk_acceptance", 0.0),
        )
        inst.validate()
        return inst

    def validate(self) -> None:
        for gate in self.approval_gates:
            if gate.kind not in {"risk", "novelty", "cost", "always"}:
                raise ValueError(f"unknown approval gate kind: {gate.kind}")
