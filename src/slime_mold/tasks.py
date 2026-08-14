"""Task model and task flow (arrival, dynamism, anomalies, dispatch).

Tasks are the unit of work that flows along the reporting chain. A task has a
type, a required capability, complexity, risk, cost and value. The flow draws
tasks from an arrival distribution, evolves the environment (dynamism), and
occasionally injects anomaly events (surges, novel task types, infrastructure
failures). Dispatch routes each task down the chain to a role that can handle
it, decomposing it into subtasks when the holder delegates to subordinates.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum


def poisson(lam: float, rng: random.Random) -> int:
    """Deterministic Poisson draw (Knuth's product method)."""
    if lam <= 0:
        return 0
    if lam < 30:
        l = math.exp(-lam)
        k = 0
        p = 1.0
        while p > l:
            k += 1
            p *= rng.random()
        return k - 1
    # large lambda: normal approximation (rarely hit in practice)
    return max(0, round(rng.gauss(lam, math.sqrt(lam))))


class TaskState(str, Enum):
    ARRIVED = "arrived"
    DISPATCHING = "dispatching"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"
    EXPIRED = "expired"


@dataclass
class Task:
    """A unit of work flowing through the organization."""

    id: str
    task_type: str
    capability: str
    complexity: float
    risk: float
    cost: float
    value: float
    arrival_turn: int
    required_turns: int
    is_novel: bool = False
    anomaly: str | None = None
    state: TaskState = TaskState.ARRIVED
    owner_role_id: str | None = None
    assigned_turn: int | None = None
    started_turn: int | None = None
    completed_turn: int | None = None
    attempts: int = 0
    escalation_count: int = 0
    parent_id: str | None = None
    subtasks: list[str] = field(default_factory=list)

    @property
    def completed(self) -> bool:
        return self.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.EXPIRED)

    @property
    def succeeded(self) -> bool:
        return self.state == TaskState.COMPLETED

    @property
    def flow_time(self) -> int | None:
        if self.completed_turn is None:
            return None
        return self.completed_turn - self.arrival_turn

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_type": self.task_type,
            "capability": self.capability,
            "complexity": round(self.complexity, 3),
            "risk": round(self.risk, 3),
            "cost": round(self.cost, 3),
            "value": round(self.value, 3),
            "arrival_turn": self.arrival_turn,
            "required_turns": self.required_turns,
            "is_novel": self.is_novel,
            "anomaly": self.anomaly,
            "state": self.state.value,
            "owner_role_id": self.owner_role_id,
            "completed_turn": self.completed_turn,
            "flow_time": self.flow_time,
            "escalation_count": self.escalation_count,
            "parent_id": self.parent_id,
            "subtasks": self.subtasks,
        }


@dataclass
class EnvironmentState:
    """Current environmental regime (drives task distributions)."""

    regime: str = "normal"
    task_types: list[str] = field(default_factory=lambda: ["t1", "t2", "t3"])
    dynamism: float = 0.0          # probability of regime shift per turn
    anomaly_probability: float = 0.02
    load_multiplier: float = 1.0

    def valid_task_type(self, task_type: str, turn: int) -> bool:
        """Environment validity hook for knowledge revalidation."""
        # types in the current regime are valid; others expire
        return task_type in self.task_types


@dataclass
class TaskFlow:
    """Task generation, environment evolution and anomaly injection.

    Parameters
    ----------
    arrival_rate:
        Mean tasks per turn (Poisson). Scaled by ``load_multiplier``.
    task_types:
        List of task types; each maps to a required capability.
    capability_by_type:
        Mapping ``task_type -> capability`` (defaults to the type itself).
    complexity_mu / risk_mu:
        Mean complexity and risk of arriving tasks.
    cost_mu:
        Mean cost (in arbitrary units) of arriving tasks.
    dynamism:
        Per-turn probability of a regime shift (changes distributions).
    anomaly_probability:
        Per-turn probability of an anomaly event.
    novelty_probability:
        Probability a task is of a type never seen before.
    shift_every:
        If set, force a regime shift every N turns (deterministic).
    """

    arrival_rate: float = 1.0
    task_types: list[str] = field(default_factory=lambda: ["t1", "t2", "t3"])
    capability_by_type: dict[str, str] = field(default_factory=dict)
    complexity_mu: float = 0.4
    risk_mu: float = 0.3
    cost_mu: float = 1.0
    dynamism: float = 0.0
    anomaly_probability: float = 0.02
    novelty_probability: float = 0.05
    shift_every: int | None = None
    load_multiplier: float = 1.0

    def __post_init__(self) -> None:
        self.env = EnvironmentState(
            task_types=list(self.task_types),
            dynamism=self.dynamism,
            anomaly_probability=self.anomaly_probability,
            load_multiplier=self.load_multiplier,
        )
        self._counter = 0

    # -- generation -----------------------------------------------------------

    def generate_tasks(
        self, turn: int, rng: random.Random
    ) -> list[Task]:
        """Draw the tasks that arrive this turn (deterministic per seed)."""
        effective_rate = self.arrival_rate * self.env.load_multiplier
        n = poisson(effective_rate, rng)
        tasks: list[Task] = []
        for _ in range(n):
            tasks.append(self._make_task(turn, rng))
        return tasks

    def _make_task(self, turn: int, rng: random.Random) -> Task:
        self._counter += 1
        task_type = rng.choice(self.env.task_types)
        is_novel = rng.random() < self.novelty_probability
        if is_novel:
            task_type = f"novel-{self._counter}"
        capability = self.capability_by_type.get(
            task_type.split("-")[0], task_type.split("-")[0]
        )
        complexity = max(0.0, min(1.0, rng.gauss(self.complexity_mu, 0.2)))
        risk = max(0.0, min(1.0, rng.gauss(self.risk_mu, 0.2)))
        cost = max(0.1, rng.gauss(self.cost_mu, 0.3))
        required = max(1, round(1 + complexity * 5))
        return Task(
            id=f"T{turn}-{self._counter}",
            task_type=task_type,
            capability=capability,
            complexity=round(complexity, 3),
            risk=round(risk, 3),
            cost=round(cost, 3),
            value=round(cost * (1.5 + complexity), 3),
            arrival_turn=turn,
            required_turns=required,
            is_novel=is_novel,
        )

    # -- environment ----------------------------------------------------------

    def step_environment(self, turn: int, rng: random.Random) -> list[str]:
        """Advance the environment; return event descriptions for the log."""
        events: list[str] = []
        shifted = self.shift_every is not None and turn > 0 and turn % self.shift_every == 0
        if not shifted and rng.random() >= self.env.dynamism:
            pass
        else:
            self.env.regime = f"regime-{turn}"
            # shuffle task types to model changing demand composition
            new_types = list(self.env.task_types)
            rng.shuffle(new_types)
            if new_types:
                new_types[0] = f"new-{turn}"  # a genuinely new type enters
            self.env.task_types = new_types
            self.env.load_multiplier = max(0.5, 1.0 + rng.gauss(0.0, 0.2))
            events.append(f"environment regime shift at turn {turn}")
        return events

    def step_anomaly(self, turn: int, rng: random.Random) -> list[Task]:
        """Inject anomaly events; return the anomalous tasks."""
        tasks: list[Task] = []
        if rng.random() < self.env.anomaly_probability:
            kind = rng.choice(["surge", "novel", "infrastructure"])
            if kind == "surge":
                extra = round(self.arrival_rate * 3)
                for _ in range(extra):
                    t = self._make_task(turn, rng)
                    t.anomaly = "surge"
                    tasks.append(t)
            elif kind == "novel":
                t = self._make_task(turn, rng)
                t.is_novel = True
                t.task_type = f"novel-anomaly-{turn}"
                t.capability = t.task_type.split("-")[0]
                t.anomaly = "novel"
                tasks.append(t)
            else:  # infrastructure
                t = self._make_task(turn, rng)
                t.anomaly = "infrastructure"
                t.risk = 1.0
                tasks.append(t)
        return tasks
