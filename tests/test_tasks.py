"""Tests for task model and task flow."""

import random

from slimemold.tasks import (
    Task,
    TaskFlow,
    TaskState,
    poisson,
)


def test_task_defaults_and_dict():
    t = Task(id="t1", task_type="a", capability="a", complexity=0.5, risk=0.2,
             cost=1.0, value=1.5, arrival_turn=0, required_turns=3)
    assert t.state == TaskState.ARRIVED
    assert t.flow_time is None
    d = t.to_dict()
    assert d["id"] == "t1"
    assert d["flow_time"] is None


def test_task_completed_flow_time():
    t = Task(id="t1", task_type="a", capability="a", complexity=0.5, risk=0.2,
             cost=1.0, value=1.5, arrival_turn=2, required_turns=3)
    t.completed_turn = 7
    t.state = TaskState.COMPLETED
    assert t.flow_time == 5
    assert t.completed is True
    assert t.succeeded is True


def test_poisson_deterministic():
    rng = random.Random(42)
    rng2 = random.Random(42)
    a = [poisson(1.0, rng) for _ in range(50)]
    b = [poisson(1.0, rng2) for _ in range(50)]
    assert a == b


def test_poisson_nonnegative():
    rng = random.Random(1)
    assert all(poisson(0.0, rng) == 0 for _ in range(5))
    assert all(poisson(0.5, rng) >= 0 for _ in range(20))


def test_generate_tasks_distribution():
    tf = TaskFlow(arrival_rate=2.0, task_types=["t1", "t2"])
    rng = random.Random(5)
    tasks = tf.generate_tasks(1, rng)
    assert len(tasks) >= 0
    assert all(t.arrival_turn == 1 for t in tasks)
    assert all(t.capability in ("t1", "t2") for t in tasks)


def test_novel_tasks():
    tf = TaskFlow(task_types=["t1"], novelty_probability=1.0)
    rng = random.Random(5)
    tasks = tf.generate_tasks(1, rng)
    assert all(t.is_novel for t in tasks)


def test_environment_shift():
    tf = TaskFlow(task_types=["t1", "t2"], dynamism=1.0)
    rng = random.Random(3)
    events = tf.step_environment(5, rng)
    assert len(events) == 1
    assert "regime shift" in events[0]
    assert tf.env.regime != "normal"


def test_environment_deterministic_shift_every():
    tf = TaskFlow(shift_every=5)
    rng = random.Random(1)
    events = tf.step_environment(5, rng)
    assert events  # forced shift at turn 5
    events2 = tf.step_environment(6, rng)
    assert not events2  # no shift normally at turn 6


def test_environment_no_shift_when_dynamism_zero():
    tf = TaskFlow(dynamism=0.0)
    rng = random.Random(1)
    events = tf.step_environment(5, rng)
    assert events == []


def test_anomaly_surge():
    tf = TaskFlow(anomaly_probability=1.0, arrival_rate=1.0)
    rng = random.Random(9)
    # first draw decides kind; monkeypatch env to force surge
    tf.env.anomaly_probability = 1.0
    tasks = tf.step_anomaly(3, rng)
    assert len(tasks) > 0


def test_anomaly_none_when_probability_zero():
    tf = TaskFlow(anomaly_probability=0.0)
    rng = random.Random(9)
    assert tf.step_anomaly(3, rng) == []


def test_valid_task_type_environment():
    tf = TaskFlow(task_types=["t1"])
    assert tf.env.valid_task_type("t1", 1) is True
    assert tf.env.valid_task_type("t9", 1) is False


def test_task_state_enum_values():
    assert TaskState("completed").value == "completed"
    assert TaskState.COMPLETED in (TaskState.COMPLETED,)


def test_load_multiplier_changes_rate():
    tf = TaskFlow(arrival_rate=10.0, load_multiplier=0.0)
    rng = random.Random(2)
    assert tf.generate_tasks(1, rng) == []
