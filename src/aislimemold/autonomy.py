"""The five-level autonomy model (operator / collaborator / consultant /
approver / observer).

The autonomy level of a role determines, together with the institution's
delegation strategy and supervision budget, *how much* supervision an agent
needs before it may act. Higher levels require fewer supervision interactions
and are allowed to make more decisions on their own.

The model is deliberately small and theory-grounded:

* **operator**  -- executes only under explicit instruction; every completed
  action is reported and reviewed (tightest control, max supervision load).
* **collaborator** -- proposes plans to the supervisor and executes once the
  plan is confirmed; proposals consume supervision budget.
* **consultant** -- executes routine work independently but *must consult*
  before high-risk or novel decisions; consultations consume supervision budget.
* **approver** -- executes and approves within its mandate; only high-risk
  tasks are flagged; consumes supervision budget only for those flags.
* **observer** -- fully autonomous within its mandate; monitors subordinates,
  delegates execution and only intervenes on escalations.

We refer to the corresponding agency-theory intuition (risk-sharing vs. control)
in the ODD documentation: more autonomy transfers decision rights down the
hierarchy, trading supervision cost for latent risk.
"""

from __future__ import annotations

from enum import Enum


class AutonomyLevel(str, Enum):
    """Five-level autonomy scale, ordered from least to most autonomous."""

    OPERATOR = "operator"
    COLLABORATOR = "collaborator"
    CONSULTANT = "consultant"
    APPROVER = "approver"
    OBSERVER = "observer"

    @property
    def rank(self) -> int:
        return _RANK[self]

    @classmethod
    def from_rank(cls, rank: int) -> AutonomyLevel:
        return _FROM_RANK[rank]


_RANK = {
    AutonomyLevel.OPERATOR: 0,
    AutonomyLevel.COLLABORATOR: 1,
    AutonomyLevel.CONSULTANT: 2,
    AutonomyLevel.APPROVER: 3,
    AutonomyLevel.OBSERVER: 4,
}
_FROM_RANK = {v: k for k, v in _RANK.items()}

# Level -> set of decision rights granted without direct supervisor sign-off.
# "execute_routine": can start routine (low risk, known type) work alone.
# "execute_risky":   can start high-risk / novel work alone.
# "approve":         can approve (sub-)task outputs.
# "delegate":        can pass work down the reporting chain.
# "consult":         must send a consultation message for risky/novel tasks.
_PERMISSIONS: dict[AutonomyLevel, dict[str, bool]] = {
    AutonomyLevel.OPERATOR: {
        "execute_routine": False,
        "execute_risky": False,
        "approve": False,
        "delegate": False,
        "consult": True,
    },
    AutonomyLevel.COLLABORATOR: {
        "execute_routine": True,
        "execute_risky": False,
        "approve": False,
        "delegate": False,
        "consult": True,
    },
    AutonomyLevel.CONSULTANT: {
        "execute_routine": True,
        "execute_risky": False,
        "approve": True,
        "delegate": True,
        "consult": True,
    },
    AutonomyLevel.APPROVER: {
        "execute_routine": True,
        "execute_risky": True,
        "approve": True,
        "delegate": True,
        "consult": False,
    },
    AutonomyLevel.OBSERVER: {
        "execute_routine": True,
        "execute_risky": True,
        "approve": True,
        "delegate": True,
        "consult": False,
    },
}


def can_execute(level: AutonomyLevel, risky: bool) -> bool:
    """Whether a role at *level* may start work on a (possibly risky) task."""
    if risky:
        return _PERMISSIONS[level]["execute_risky"]
    return _PERMISSIONS[level]["execute_routine"]


def requires_consultation(level: AutonomyLevel, risky: bool, novelty: bool) -> bool:
    """Whether a role must consult its supervisor for this task."""
    if not _PERMISSIONS[level]["consult"]:
        return False
    # Operators/collaborators consult on everything; consultants only on
    # risky or novel work.
    if level.rank <= AutonomyLevel.COLLABORATOR.rank:
        return True
    return risky or novelty


def requires_approval(level: AutonomyLevel, risky: bool) -> bool:
    """Whether executing the task needs an explicit supervisor approval."""
    if level.rank <= AutonomyLevel.COLLABORATOR.rank:
        return True
    if level == AutonomyLevel.CONSULTANT:
        return risky
    return False
