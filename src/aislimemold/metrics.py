"""MetricsEngine: aggregate organizational constructs from a simulation run.

Metrics are deliberately expressed in *organizational* language, not raw event
counts, so that designs can be compared on management-relevant dimensions:

* **performance** -- throughput (completed tasks per 100 turns), success rate,
  mean completion (flow) time.
* **coordination** -- message volume per completed task, mean approval/consult
  waiting time, escalation count, supervision load (approval interactions).
* **quality / safety** -- error rate (failed / completed+failed), uncaught risk
  (failed risky tasks / all risky tasks), deadlock-resolved failures.
* **decision** -- decision latency (assignment -> execution start) and the
  autonomy share (fraction of tasks executed without a supervisor approval).
* **knowledge** -- retention rate, learning curve (success rate by time window),
  revalidation rate.
* **resilience** -- for each turnover event, the performance drop after the
  event and the turns-to-recovery back to the pre-event baseline.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from statistics import mean

from .tasks import Task, TaskState


@dataclass
class MetricBundle:
    performance: dict
    coordination: dict
    quality: dict
    decision: dict
    knowledge: dict
    resilience: dict

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


class MetricsEngine:
    """Static computation helpers; instantiate for convenience access."""

    def __init__(self, result=None) -> None:
        self.result = result

    @staticmethod
    def compute(result) -> dict:
        """Compute the full metric bundle for a SimulationResult."""
        tasks = result.tasks
        completed = [t for t in tasks if t.state == TaskState.COMPLETED]
        failed = [t for t in tasks if t.state == TaskState.FAILED]
        total = len(tasks)
        n_completed = len(completed)
        n_failed = len(failed)
        turns = max(result.config.turns, 1)

        # -- performance -----------------------------------------------------
        throughput = (n_completed / turns) * 100.0
        success_rate = n_completed / total if total else 1.0
        flow_times = [t.flow_time for t in completed if t.flow_time is not None]
        mean_flow = mean(flow_times) if flow_times else 0.0
        value_delivered = sum(t.value for t in completed)
        # late tasks (flow time beyond an SLA of 15 turns)
        sla = 15
        late = sum(1 for ft in flow_times if ft > sla)
        sla_breach = late / len(flow_times) if flow_times else 0.0

        # -- coordination ----------------------------------------------------
        n_messages = len(result.messages)
        messages_per_task = n_messages / total if total else 0.0
        waits = []
        for t in tasks:
            if t.assigned_turn is not None and t.started_turn is not None:
                waits.append(max(0, t.started_turn - t.assigned_turn))
        mean_wait = mean(waits) if waits else 0.0
        escalations = sum(t.escalation_count for t in tasks)
        approval_msgs = sum(
            1 for m in result.messages if m.kind.value in ("approve", "reject")
        )
        consult_msgs = sum(
            1 for m in result.messages if m.kind.value == "consult"
        )
        supervision_load = approval_msgs + consult_msgs

        # -- quality / safety -----------------------------------------------
        error_rate = n_failed / (n_completed + n_failed) if (n_completed + n_failed) else 0.0
        risky = [t for t in tasks if t.risk >= 0.5]
        risky_failed = [t for t in risky if t.state == TaskState.FAILED]
        uncaught_risk = len(risky_failed) / len(risky) if risky else 0.0
        deadlocks = sum(
            1 for e in result.events if e.kind == "deadlock_resolved"
        )
        deadlock_failures = sum(
            1
            for t in tasks
            if t.state == TaskState.FAILED
            and any(
                e.kind == "task:failed" and e.subject == t.id and "deadlock" in e.data.get("reason", "")
                for e in result.events
            )
        )

        # -- decision --------------------------------------------------------
        latencies = []
        for t in tasks:
            if t.assigned_turn is not None and t.started_turn is not None:
                latencies.append(max(0, t.started_turn - t.assigned_turn))
        mean_decision_latency = mean(latencies) if latencies else 0.0
        # autonomy share: fraction of completed+failed tasks that were never
        # gated by an approval message
        gated_ids = {
            m.task_id
            for m in result.messages
            if m.kind.value in ("submit", "consult") and m.task_id is not None
        }
        n_ungated = sum(1 for t in tasks if t.id not in gated_ids)
        autonomy_share = n_ungated / total if total else 1.0

        # -- knowledge -------------------------------------------------------
        retention = result.knowledge.retention_rate(result.config.turns)
        reval_rate = result.knowledge.revalidation_rate()
        learning_curve = _learning_curve(result, completed + failed)
        knowledge_volume = result.knowledge.size()

        # -- resilience ------------------------------------------------------
        resilience = _resilience(result)

        return {
            "performance": {
                "throughput": round(throughput, 3),
                "success_rate": round(success_rate, 3),
                "mean_flow_time": round(mean_flow, 3),
                "value_delivered": round(value_delivered, 3),
                "sla_breach_rate": round(sla_breach, 3),
                "n_completed": n_completed,
                "n_failed": n_failed,
            },
            "coordination": {
                "messages": n_messages,
                "messages_per_task": round(messages_per_task, 3),
                "mean_waiting_turns": round(mean_wait, 3),
                "escalations": escalations,
                "approval_messages": approval_msgs,
                "consult_messages": consult_msgs,
                "supervision_load": supervision_load,
            },
            "quality": {
                "error_rate": round(error_rate, 3),
                "uncaught_risk": round(uncaught_risk, 3),
                "deadlock_resolutions": deadlocks,
                "deadlock_failures": deadlock_failures,
            },
            "decision": {
                "mean_decision_latency": round(mean_decision_latency, 3),
                "autonomy_share": round(autonomy_share, 3),
            },
            "knowledge": {
                "retention_rate": round(retention, 3),
                "revalidation_rate": round(reval_rate, 3),
                "learning_curve": learning_curve,
                "knowledge_volume": knowledge_volume,
            },
            "resilience": resilience,
        }


def _learning_curve(result, considered: list[Task]) -> dict:
    """Success rate in successive time windows (the org learning curve)."""
    if not considered:
        return {"windows": [], "success_by_window": []}
    n_windows = 4
    total_turns = result.config.turns
    window_len = max(1, total_turns // n_windows)
    by_window: list[list[bool]] = [[] for _ in range(n_windows)]
    for t in considered:
        idx = min(n_windows - 1, (t.completed_turn or t.arrival_turn) // window_len)
        by_window[idx].append(t.state == TaskState.COMPLETED)
    rates = [
        round(sum(win) / len(win), 3) if win else 0.0 for win in by_window
    ]
    return {
        "windows": [i * window_len for i in range(n_windows)],
        "success_by_window": rates,
    }


def _resilience(result) -> dict:
    """Drop-and-recovery analysis around turnover events."""
    events = result.turnover_events
    if not events:
        return {
            "events": [],
            "note": "no turnover events occurred",
            "mean_drop": 0.0,
            "mean_recovery_turns": 0.0,
        }

    turn_of = {t.id: t for t in result.tasks}
    success_by_turn: dict[int, list[bool]] = {}
    for t in turn_of.values():
        if t.completed_turn is None:
            continue
        success_by_turn.setdefault(t.completed_turn, []).append(t.state == TaskState.COMPLETED)

    def success_in(window_start: int, window_end: int) -> float | None:
        vals: list[bool] = []
        for tt in range(window_start, window_end):
            vals.extend(success_by_turn.get(tt, []))
        if not vals:
            return None
        return sum(vals) / len(vals)

    drops: list[float] = []
    recoveries: list[float] = []
    horizon = max(1, result.config.turns // 5)
    for (ev_turn, role_id) in events:
        baseline = success_in(max(0, ev_turn - horizon), ev_turn)
        post = success_in(ev_turn, min(result.config.turns, ev_turn + horizon))
        if baseline is None or post is None or baseline <= 0:
            continue
        drop = baseline - post
        # recovery: first turn window where performance returns to baseline
        recovery = None
        for k in range(0, result.config.turns - ev_turn, 5):
            window = success_in(ev_turn + k, ev_turn + k + 5)
            if window is not None and window >= baseline:
                recovery = k
                break
        if recovery is not None:
            recoveries.append(recovery)
        drops.append(max(0.0, drop))

    return {
        "events": [{"turn": t, "role_id": r} for t, r in events],
        "n_events": len(events),
        "mean_drop": round(mean(drops), 3) if drops else 0.0,
        "mean_recovery_turns": round(mean(recoveries), 3) if recoveries else None,
    }
