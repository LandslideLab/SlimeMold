"""SimulationRunner: the deterministic, turn-based organizational simulator.

Design goals (ABM methodology requirements):

* **Determinism** -- a single master seed drives all randomness through
  :class:`~slime_mold.rng.SeededRandom` child streams. Re-running the same
  config + seed reproduces the same event log bit-for-bit.
* **Turn-based scheduler** -- every turn executes the same fixed pipeline
  (turnover -> environment -> arrivals -> approvals -> execution -> timeouts ->
  knowledge), so results do not depend on host speed or thread scheduling.
* **Message bus** -- all interaction is recorded on the
  :class:`~slime_mold.bus.MessageBus`; the event log is the complete evidence
  base for metrics and replay.
* **Timeout/deadlock detection** -- approval/consult requests that cannot be
  served (typically because supervision budget is exhausted) wait, escalate up
  the chain after ``escalation_timeout`` turns and are force-resolved after
  ``max_wait_turns``. Every forced resolution is logged as a
  ``deadlock_resolved`` event.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from . import autonomy as _autonomy
from .agents import AgentPolicy, ScriptedPolicy
from .bus import Event, MessageBus, MessageType
from .institution import Institution
from .knowledge import KnowledgeMechanism
from .organization import Organization
from .rng import SeededRandom
from .roles import Member
from .tasks import Task, TaskFlow, TaskState
from .turnover import Turnover


@dataclass
class SimConfig:
    """Top-level simulation configuration.

    Parameters
    ----------
    turns:
        Number of simulation turns (ticks) to run.
    seed:
        Master random seed. ``None`` derives a random-but-recorded seed.
    max_attempts:
        Max rework attempts per task before it is abandoned.
    knowledge_weight:
        Weight of the knowledge effect in task success probability.
    supervision_enabled:
        Master switch for approval/consultation flows (for ablation studies).
    """

    turns: int = 100
    seed: int | None = None
    max_attempts: int = 2
    knowledge_weight: float = 0.4
    supervision_enabled: bool = True

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SimConfig:
        names = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class SimulationResult:
    """Complete, serializable output of a simulation run."""

    config: SimConfig
    org: Organization
    institution: Institution
    taskflow: TaskFlow
    turnover: Turnover
    knowledge: KnowledgeMechanism
    tasks: list[Task] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    messages: list = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)
    turnover_events: list[tuple[int, str]] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    engine_version: str = ""

    def to_dict(self) -> dict:
        return {
            "config": self.config.to_dict(),
            "organization": self.org.to_dict(),
            "institution": self.institution.to_dict(),
            "taskflow": {
                "arrival_rate": self.taskflow.arrival_rate,
                "task_types": self.taskflow.task_types,
                "dynamism": self.taskflow.dynamism,
            },
            "turnover": self.turnover.to_dict(),
            "knowledge": self.knowledge.to_dict(),
            "tasks": [t.to_dict() for t in self.tasks],
            "events": [e.to_dict() for e in self.events],
            "messages": [m.to_dict() for m in self.messages],
            "timeline": self.timeline,
            "turnover_events": list(self.turnover_events),
            "metrics": self.metrics,
            "engine_version": self.engine_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SimulationResult:
        from .organization import OrgRole

        roles = {rid: OrgRole.from_dict(r) for rid, r in data["organization"]["roles"].items()}
        org = Organization.from_spec(
            roles, data["organization"]["reporting"], name=data["organization"]["name"]
        )
        inst = Institution.from_dict(data["institution"])
        tf_data = data.get("taskflow", {})
        tf = TaskFlow(
            arrival_rate=tf_data.get("arrival_rate", 1.0),
            task_types=tf_data.get("task_types", ["t1", "t2", "t3"]),
            dynamism=tf_data.get("dynamism", 0.0),
        )
        turn = Turnover(**{k: v for k, v in data["turnover"].items()
                           if k in {f.name for f in dataclasses.fields(Turnover)}})
        kn = KnowledgeMechanism()
        res = cls(
            config=SimConfig.from_dict(data["config"]),
            org=org,
            institution=inst,
            taskflow=tf,
            turnover=turn,
            knowledge=kn,
            tasks=[Task(**{kk: vv for kk, vv in t.items()
                           if kk in {f.name for f in dataclasses.fields(Task)}})
                   for t in data["tasks"]],
            turnover_events=[tuple(e) for e in data.get("turnover_events", [])],
            timeline=data.get("timeline", []),
            engine_version=data.get("engine_version", ""),
        )
        res.metrics = data.get("metrics", {})
        return res


class SimulationRunner:
    """Runs an :class:`Organization` + :class:`Institution` over ``turns``."""

    def __init__(
        self,
        org: Organization,
        institution: Institution,
        taskflow: TaskFlow,
        turnover: Turnover | None = None,
        knowledge: KnowledgeMechanism | None = None,
        config: SimConfig | None = None,
    ) -> None:
        self.org = org
        self.institution = institution
        self.taskflow = taskflow
        self.turnover = turnover or Turnover()
        self.knowledge = knowledge or KnowledgeMechanism()
        self.config = config or SimConfig()
        self.bus = MessageBus()

        self._members: dict[str, Member] = {}
        self._policies: dict[str, AgentPolicy] = {}

        self._tasks: dict[str, Task] = {}
        self._waiting: dict[str, dict] = {}
        self._executing: dict[str, int] = {}
        self._manager_budget: dict[str, int] = {}

    # ------------------------------------------------------------------ setup

    def _reset_rng(self) -> None:
        self._rng = SeededRandom(self.config.seed)
        self._rng_turnover = self._rng.child("turnover")
        self._rng_env = self._rng.child("env")
        self._rng_task = self._rng.child("tasks")
        self._rng_agent = self._rng.child("agents")
        self._rng_outcome = self._rng.child("outcome")
        self._rng_knowledge = self._rng.child("knowledge")
        self.knowledge.set_environment(
            lambda tt, turn: self.taskflow.env.valid_task_type(tt, turn),
            self._rng_knowledge,
        )

    def build_members(self) -> None:
        """Instantiate one member + policy per role."""
        for role_id in self.org.roles:
            self._members[role_id] = Member(
                id=f"{role_id}@m1",
                role_id=role_id,
                kind="scripted",
                experience=0.6,
            )
            self._policies[role_id] = ScriptedPolicy()

    def set_policy(self, role_id: str, policy: AgentPolicy) -> None:
        """Override a role's decision policy (e.g. an LLM adapter)."""
        self._policies[role_id] = policy

    # ---------------------------------------------------------------- helpers

    def _role(self, role_id: str):
        return self.org.roles[role_id]

    def _capable_subordinates(self, role_id: str, capability: str) -> list[str]:
        return [
            rid for rid in self.org.direct_reports(role_id)
            if capability in self._role(rid).can_handle
        ]

    def _find_owner(self, capability: str) -> str | None:
        """Route a task down the chain to the deepest capable role."""
        best: str | None = None
        best_depth = -1
        for rid in self.org.roles:
            role = self._role(rid)
            if capability in role.can_handle:
                d = self.org.depth_of(rid)
                if d > best_depth:
                    best, best_depth = rid, d
        return best

    def _manager_of(self, role_id: str) -> str | None:
        mgrs = self.org.managers(role_id)
        return mgrs[0] if mgrs else None

    def _ctx(self, task: Task, owner: str) -> dict:
        return {
            "rng": self._rng_agent,
            "task": task.to_dict(),
            "owner": owner,
            "risky": self.institution.effective_risk(task.risk) >= 0.5,
            "novel": task.is_novel,
            "capable_subordinates": self._capable_subordinates(owner, task.capability),
            "experience": self._members[owner].experience,
            "budget": self.institution.budget_for(owner),
        }

    def _context_key(self, task: Task) -> str:
        return f"{self.taskflow.env.regime}:{task.task_type}"

    # ---------------------------------------------------------------- pipeline

    def run(self, turns: int | None = None, collect_metrics: bool = True) -> SimulationResult:
        """Run the simulation and return a complete result object.

        Every call starts from a fully fresh internal state: a new bus, a
        freshly rebuilt task flow / knowledge mechanism (so no state leaks
        between runs or across runners sharing config objects) and a re-seeded
        RNG tree. This is what makes ``run()`` reproducible.
        """
        if turns is not None:
            self.config.turns = turns

        # fresh per-run state
        from dataclasses import fields

        from .bus import MessageBus
        from .knowledge import KnowledgeMechanism
        from .tasks import TaskFlow

        self.bus = MessageBus()
        tf_fields = {f.name: getattr(self.taskflow, f.name) for f in fields(TaskFlow)}
        self.taskflow = TaskFlow(**tf_fields)
        self.turnover = Turnover(
            per_turn_probability=self.turnover.per_turn_probability,
            schedule=dict(self.turnover.schedule),
            replace_experience=self.turnover.replace_experience,
            onboarding_turns=self.turnover.onboarding_turns,
            knowledge_loss_fraction=self.turnover.knowledge_loss_fraction,
        )
        self.knowledge = KnowledgeMechanism(
            sharing_probability=self.knowledge.sharing_probability,
            half_life=self.knowledge.half_life,
            revalidation_probability=self.knowledge.revalidation_probability,
            max_items_per_member=self.knowledge.max_items_per_member,
            noise=self.knowledge.noise,
        )
        self._tasks = {}
        self._waiting = {}
        self._executing = {}
        self._manager_budget = {}
        self._timeline: list[dict] = []
        self._turnover_events: list[tuple[int, str]] = []

        self._reset_rng()
        self.build_members()

        for turn in range(1, self.config.turns + 1):
            self._step_turn(turn)

        result = SimulationResult(
            config=self.config,
            org=self.org,
            institution=self.institution,
            taskflow=self.taskflow,
            turnover=self.turnover,
            knowledge=self.knowledge,
            tasks=list(self._tasks.values()),
            events=self.bus.events,
            messages=self.bus.messages,
            timeline=self._timeline,
            turnover_events=self._turnover_events,
            engine_version=self._engine_version(),
        )
        if collect_metrics:
            from .metrics import MetricsEngine
            result.metrics = MetricsEngine.compute(result)
        return result

    def _engine_version(self) -> str:
        try:
            from .__version__ import __version__
            return __version__
        except ImportError:
            return "unknown"

    def _step_turn(self, turn: int) -> None:
        self._turn = turn
        self._timeline.append(self._snapshot(turn))

        # 1. turnover
        departed = self.turnover.step(
            turn, self._members, self._rng_turnover, on_departure=self._on_departure
        )
        for role_id in departed:
            self._turnover_events.append((turn, role_id))
            self.bus.log(turn, "turnover", role_id, role_id,
                         f"member departed from role {role_id}")

        # 2. environment
        env_events = self.taskflow.step_environment(turn, self._rng_env)
        for e in env_events:
            self.bus.log(turn, "environment", "flow", "", e)

        # 3. arrivals + anomalies
        anomalies = self.taskflow.step_anomaly(turn, self._rng_env)
        arrivals = self.taskflow.generate_tasks(turn, self._rng_task)
        new_tasks = anomalies + arrivals
        for task in new_tasks:
            self._tasks[task.id] = task
            self._dispatch(task, turn)

        # 4. approvals / consultations
        self._process_waiting(turn)

        # 5. execution steps
        self._step_executions(turn)

        # 6. timeouts + deadlock resolution
        self._scan_timeouts(turn)

        # 7. knowledge maintenance
        self.knowledge.step_forgetting(turn)
        self.knowledge.step_revalidation(turn)

        # 8. reset per-turn manager budgets
        self._manager_budget = {}

    def _snapshot(self, turn: int) -> dict:
        return {
            "turn": turn,
            "active_tasks": len(self._tasks),
            "waiting": len(self._waiting),
            "executing": len(self._executing),
        }

    # ---------------------------------------------------------------- dispatch

    def _dispatch(self, task: Task, turn: int) -> None:
        owner = self._find_owner(task.capability)
        if owner is None:
            task.state = TaskState.FAILED
            self.bus.log(turn, "task:failed", task.id, "", "no capable role",
                         {"reason": "no_capable_role"})
            return
        self._assign(task, owner, turn)
        self._act_on_task(task, turn)

    def _assign(self, task: Task, owner: str, turn: int) -> None:
        task.owner_role_id = owner
        task.assigned_turn = turn
        if task.state in (TaskState.ARRIVED, TaskState.ESCALATED):
            task.state = TaskState.DISPATCHING
        self.bus.send(MessageType.ASSIGN, "org", owner, turn, task.id,
                      {"capability": task.capability})

    def _act_on_task(self, task: Task, turn: int) -> None:
        owner = task.owner_role_id
        if owner is None:
            return
        role = self._role(owner)
        ctx = self._ctx(task, owner)
        decision = self._policies[owner].decide_task_action(ctx)

        if decision == "delegate":
            subs = self._capable_subordinates(owner, task.capability)
            if subs:
                sub = self._pick_subordinate(subs)
                self.bus.send(MessageType.ASSIGN, owner, sub, turn, task.id,
                              {"delegated": True})
                self._assign(task, sub, turn)
                self._act_on_task(task, turn)
                return
            decision = "execute"
        if decision == "escalate":
            task.escalation_count += 1
            mgr = self._manager_of(owner)
            if mgr is None:
                task.state = TaskState.FAILED
                self.bus.log(turn, "task:failed", task.id, owner, "root escalation",
                             {"reason": "root_escalated"})
                return
            self.bus.send(MessageType.ESCALATE, owner, mgr, turn, task.id)
            task.owner_role_id = mgr
            task.state = TaskState.ESCALATED
            self._act_on_task(task, turn)
            return
        if decision == "reject":
            task.state = TaskState.FAILED
            self.bus.log(turn, "task:failed", task.id, owner, "agent rejected task",
                         {"reason": "rejected"})
            return

        # execute
        risky = ctx["risky"]
        approval_needed = self.institution.requires_approval(task, role)
        consult_needed = (
            not approval_needed
            and self.config.supervision_enabled
            and _autonomy.requires_consultation(role.autonomy, risky, task.is_novel)
        )
        if approval_needed and self.config.supervision_enabled:
            self._enter_waiting(task, "approval", turn)
            return
        if consult_needed:
            self._enter_waiting(task, "consult", turn)
            return
        self._start_execution(task, turn)

    def _pick_subordinate(self, subs: list[str]) -> str:
        # deterministic: pick the deepest capable subordinate (ties by id)
        return min(subs, key=lambda rid: (self.org.depth_of(rid), rid))

    def _enter_waiting(self, task: Task, kind: str, turn: int) -> None:
        task.state = TaskState.AWAITING_APPROVAL
        manager = self._manager_of(task.owner_role_id) if task.owner_role_id else None
        if manager is None:
            # no one to approve: fail-fast
            task.state = TaskState.FAILED
            self.bus.log(turn, "task:failed", task.id, "", "no approver",
                         {"reason": "no_approver"})
            return
        self._waiting[task.id] = {
            "task_id": task.id,
            "kind": kind,
            "manager": manager,
            "since": turn,
        }
        msg_type = MessageType.SUBMIT if kind == "approval" else MessageType.CONSULT
        self.bus.send(msg_type, task.owner_role_id, manager, turn, task.id)

    # --------------------------------------------------------------- approvals

    def _process_waiting(self, turn: int) -> None:
        for task_id in list(self._waiting):
            wait = self._waiting[task_id]
            task = self._tasks[task_id]
            manager = wait["manager"]
            budget = self.institution.budget_for(manager)
            if budget is not None and self._manager_budget.get(manager, budget) <= 0:
                continue  # supervision budget exhausted: keep waiting
            if budget is not None:
                self._manager_budget[manager] = self._manager_budget.get(
                    manager, budget
                ) - self.institution.approval_turn_cost

            owner = task.owner_role_id
            if wait["kind"] == "approval":
                quality = self._submitted_quality(task)
                approved = self._policies[manager].decide_approval(
                    {"rng": self._rng_agent, "submitted_quality": quality,
                     "risk": task.risk, "task": task.to_dict()}
                )
                if approved:
                    self.bus.send(MessageType.APPROVE, manager, owner, turn, task.id)
                    self._start_execution(task, turn)
                else:
                    self.bus.send(MessageType.REJECT, manager, owner, turn, task.id)
                    task.attempts += 1
                    if task.attempts >= self.config.max_attempts:
                        task.state = TaskState.FAILED
                        self.bus.log(turn, "task:failed", task.id, owner,
                                     "exceeded max rework attempts",
                                     {"reason": "max_rework"})
                    else:
                        self._start_execution(task, turn)
            else:  # consult
                proceed = self._policies[manager].decide_consult_response(
                    {"rng": self._rng_agent, "task": task.to_dict(),
                     "risk": task.risk}
                )
                self.bus.send(MessageType.RESPOND, manager, owner, turn, task.id,
                              {"proceed": proceed})
                if proceed:
                    self._start_execution(task, turn)
                else:
                    task.escalation_count += 1
                    task.state = TaskState.ESCALATED
                    mgr = self._manager_of(manager)
                    if mgr is None:
                        task.state = TaskState.FAILED
                        self.bus.log(turn, "task:failed", task.id, owner,
                                     "consult refused at root",
                                     {"reason": "consult_refused"})
                    else:
                        self.bus.send(MessageType.ESCALATE, manager, mgr, turn, task.id)
                        self._assign(task, mgr, turn)
                        self._act_on_task(task, turn)
            del self._waiting[task_id]

    def _submitted_quality(self, task: Task) -> float:
        member = self._members[task.owner_role_id]
        return max(0.0, min(1.0, member.experience * (1 - task.complexity * 0.5)))

    def _start_execution(self, task: Task, turn: int) -> None:
        task.state = TaskState.EXECUTING
        task.started_turn = turn
        self._executing[task.id] = max(1, task.required_turns)
        self.bus.log(turn, "task:start", task.id, task.owner_role_id,
                     f"{task.owner_role_id} started executing {task.id}")

    # ------------------------------------------------------------- execution

    def _step_executions(self, turn: int) -> None:
        for task_id in list(self._executing):
            task = self._tasks[task_id]
            remaining = self._executing[task_id] - 1
            if remaining > 0:
                self._executing[task_id] = remaining
                continue
            del self._executing[task_id]
            self._resolve_outcome(task, turn)

    def _resolve_outcome(self, task: Task, turn: int) -> None:
        owner = task.owner_role_id
        member = self._members[owner]
        context = self._context_key(task)
        effect, has_knowledge = self.knowledge.knowledge_effect(
            member.id, task.task_type, context, self._rng_outcome
        )
        policy = self._policies[owner]
        error = getattr(policy, "error_probability", 0.08)
        competence = 0.4 + 0.5 * member.experience
        base = max(0.05, min(0.95, competence - 0.25 * task.complexity - 0.2 * task.risk))
        p = min(0.97, (base + self.config.knowledge_weight * effect) * (1 - error))
        success = self._rng_outcome.random() < p

        task.attempts += 1
        task.completed_turn = turn
        task.state = TaskState.COMPLETED if success else TaskState.FAILED

        self.knowledge.observe_outcome(
            member.id, task.task_type, context, success, turn
        )
        if success:
            member.skill_gain()
            self._propagate_knowledge(owner, member.id, task.task_type, context, turn)
        else:
            member.experience *= 0.99

        self.bus.send(MessageType.REPORT, owner, self._manager_of(owner) or "org",
                      turn, task.id, {"success": success})
        self.bus.log(turn, "task:completed" if success else "task:failed",
                     task.id, owner, f"outcome={success} p={p:.3f}",
                     {"success": success, "probability": round(p, 4),
                      "has_knowledge": has_knowledge, "attempts": task.attempts})

    def _propagate_knowledge(self, role_id: str, member_id: str, task_type: str,
                             context: str, turn: int) -> None:
        neighbors: list[str] = []
        for m in self.org.managers(role_id):
            if m in self._members:
                neighbors.append(self._members[m].id)
        for sub in self.org.direct_reports(role_id):
            if sub in self._members:
                neighbors.append(self._members[sub].id)
        item = self.knowledge.item(member_id, task_type, context)
        if item is None:
            return
        for neighbor in neighbors:
            self.knowledge.share_to(neighbor, item, turn)
            self.bus.send(MessageType.NOTIFY, member_id, neighbor, turn,
                          None, {"task_type": task_type, "context": context})

    # ------------------------------------------------------------------ scans

    def _scan_timeouts(self, turn: int) -> None:
        for task_id in list(self._waiting):
            wait = self._waiting[task_id]
            task = self._tasks[task_id]
            waited = turn - wait["since"]
            manager = wait["manager"]
            if waited >= self.institution.escalation_timeout:
                mgr = self._manager_of(manager)
                if mgr is not None:
                    task.escalation_count += 1
                    wait["manager"] = mgr
                    wait["since"] = turn
                    self.bus.log(turn, "escalation", task.id, manager,
                                 f"approval/consult escalated to {mgr}")
            if waited >= self.institution.max_wait_turns:
                self._resolve_deadlock(task, turn)
                del self._waiting[task_id]

    def _resolve_deadlock(self, task: Task, turn: int) -> None:
        approve = task.risk < 0.5
        self.bus.log(turn, "deadlock_resolved", task.id, "",
                     f"forced {'approve' if approve else 'fail'}",
                     {"forced": approve})
        if approve:
            self._start_execution(task, turn)
        else:
            task.state = TaskState.FAILED
            task.completed_turn = turn
            self.bus.log(turn, "task:failed", task.id, task.owner_role_id,
                         "deadlock forced failure", {"reason": "deadlock"})

    # ---------------------------------------------------------------- turnover

    def _on_departure(self, member: Member) -> None:
        # scrub a fraction of the departing member's personal knowledge
        store = getattr(self.knowledge, "_store", {}).get(member.id, {})
        keep = int(len(store) * (1 - self.turnover.knowledge_loss_fraction))
        if store:
            # keep the highest-confidence items (mimicking handover notes)
            items = sorted(store.items(), key=lambda kv: kv[1].confidence,
                           reverse=True)
            for key, _ in items[keep:]:
                del store[key]

    # ---------------------------------------------------------------- metrics

    def metrics_dict(self) -> dict:
        """Compute metrics without a full re-run (requires prior run())."""
        from .metrics import MetricsEngine
        result = SimulationResult(
            config=self.config,
            org=self.org,
            institution=self.institution,
            taskflow=self.taskflow,
            turnover=self.turnover,
            knowledge=self.knowledge,
            tasks=list(self._tasks.values()),
            events=self.bus.events,
            messages=self.bus.messages,
            timeline=self._timeline,
            turnover_events=self._turnover_events,
        )
        return MetricsEngine.compute(result)
