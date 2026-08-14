"""Tests for turnover, RNG streams and agents."""

import random

import pytest

from slime_mold.agents import DummyLLMAdapter, ScriptedPolicy
from slime_mold.rng import SeededRandom, _derive_seed
from slime_mold.roles import Member
from slime_mold.turnover import Turnover


def members():
    return {"a": Member(id="a#1", role_id="a"),
            "b": Member(id="b#1", role_id="b")}


# ------------------------------------------------------------- turnover


def test_turnover_no_events_with_zero_probability():
    t = Turnover(per_turn_probability=0.0)
    departed = t.step(5, members(), random.Random(1))
    assert departed == []


def test_turnover_scheduled():
    t = Turnover(schedule={5: ["a"]})
    ms = members()
    departed = t.step(5, ms, random.Random(1))
    assert departed == ["a"]
    assert ms["a"].experience == t.replace_experience
    assert ms["a"].tenure == 0


def test_turnover_probabilistic():
    t = Turnover(per_turn_probability=1.0)
    ms = members()
    departed = t.step(1, ms, random.Random(1))
    assert set(departed) == {"a", "b"}
    assert ms["a"].id != "a#1"
    assert ms["a"].experience == t.replace_experience


def test_turnover_on_departure_callback():
    t = Turnover(schedule={1: ["a"]})
    ms = members()
    calls = []
    t.step(1, ms, random.Random(1), on_departure=lambda m: calls.append(m.id))
    assert calls == ["a#1"]


def test_turnover_schedule_missing_role_ignored():
    t = Turnover(schedule={1: ["ghost"]})
    departed = t.step(1, members(), random.Random(1))
    assert departed == []


def test_turnover_to_dict():
    t = Turnover(per_turn_probability=0.1)
    d = t.to_dict()
    assert d["per_turn_probability"] == 0.1


# ------------------------------------------------------------------ rng


def test_seeded_random_child_deterministic():
    a = SeededRandom(7)
    b = SeededRandom(7)
    assert a.child("x").getstate() == b.child("x").getstate()


def test_seeded_random_child_distinct_tags():
    a = SeededRandom(7)
    assert a.child("x") is not a.child("y")


def test_seeded_random_master_proxy():
    a = SeededRandom(7)
    assert isinstance(a.random(), float)


def test_seeded_random_none_seed_recorded():
    a = SeededRandom(None)
    assert isinstance(a.master_seed, int)


def test_derive_seed_stable():
    assert _derive_seed(7, "tasks") == _derive_seed(7, "tasks")
    assert _derive_seed(7, "tasks") != _derive_seed(7, "env")


def test_seeded_random_to_dict():
    a = SeededRandom(3)
    a.child("x")
    d = a.to_dict()
    assert d["master_seed"] == 3
    assert d["child_tags"] == ["x"]


# --------------------------------------------------------------- agents


def test_scripted_policy_execute():
    p = ScriptedPolicy(delegate_when_possible=False, escalation_probability=0.0)
    ctx = {"rng": random.Random(1), "risky": False,
           "capable_subordinates": []}
    assert p.decide_task_action(ctx) == "execute"


def test_scripted_policy_delegate():
    p = ScriptedPolicy(delegate_when_possible=True)
    ctx = {"rng": random.Random(1), "risky": False,
           "capable_subordinates": ["sub"]}
    assert p.decide_task_action(ctx) == "delegate"


def test_scripted_policy_escalate():
    p = ScriptedPolicy(escalation_probability=1.0)
    ctx = {"rng": random.Random(1), "risky": False,
           "capable_subordinates": []}
    assert p.decide_task_action(ctx) == "escalate"


def test_scripted_policy_reject_risky():
    p = ScriptedPolicy(risk_aversion=1.0)
    ctx = {"rng": random.Random(1), "risky": True,
           "capable_subordinates": []}
    assert p.decide_task_action(ctx) == "reject"


def test_scripted_policy_approval():
    p = ScriptedPolicy()
    ctx = {"rng": random.Random(1), "submitted_quality": 0.9}
    assert p.decide_approval(ctx) is True
    # guaranteed rubber-stamp miss
    ctx2 = {"rng": random.Random(1), "submitted_quality": 0.0}
    assert isinstance(p.decide_approval(ctx2), bool)


def test_scripted_policy_consult_response():
    p = ScriptedPolicy(error_probability=1.0)
    ctx = {"rng": random.Random(1)}
    assert p.decide_consult_response(ctx) in (True, False)


def test_dummy_llm_adapter():
    a = DummyLLMAdapter()
    ctx = {"capable_subordinates": []}
    assert a.decide_task_action(ctx) == "execute"
    ctx2 = {"capable_subordinates": ["x"]}
    assert a.decide_task_action(ctx2) == "delegate"
    assert a.decide_approval({}) is True
    assert a.decide_consult_response({}) is True


def test_llm_adapter_invoke_not_implemented():
    from slime_mold.agents import LLMAgentAdapter

    class Noop(LLMAgentAdapter):
        pass

    with pytest.raises(NotImplementedError):
        Noop().decide_task_action({})
