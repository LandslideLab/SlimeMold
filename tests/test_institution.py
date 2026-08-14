"""Tests for the institution and approval gates."""

import pytest

from slimemold.institution import (
    ApprovalGate,
    DelegationStrategy,
    Institution,
)
from slimemold.roles import OrgRole
from slimemold.tasks import Task


def make_task(**kwargs):
    defaults = {"id": "t", "task_type": "x", "capability": "x", "complexity": 0.5,
                "risk": 0.3, "cost": 1.0, "value": 1.5, "arrival_turn": 0,
                "required_turns": 2}
    defaults.update(kwargs)
    return Task(**defaults)


def role(level):
    return OrgRole(id="r", capabilities={"x"}, autonomy=level)


@pytest.mark.parametrize("strategy,risk,level,expected", [
    ("command", 0.1, "consultant", True),
    ("command", 0.9, "approver", True),
    ("consultative", 0.1, "approver", False),
    ("consultative", 0.9, "consultant", True),
    ("controlled", 0.1, "approver", False),
    ("controlled", 0.1, "collaborator", True),
    ("controlled", 0.9, "consultant", True),
    ("controlled", 0.9, "approver", False),
    ("full", 0.9, "operator", False),
])
def test_requires_approval_by_strategy(strategy, risk, level, expected):
    inst = Institution(delegation_strategy=strategy)
    t = make_task(risk=risk)
    r = role(level)
    assert inst.requires_approval(t, r) is expected


def test_approval_gate_risk():
    gate = ApprovalGate(kind="risk", threshold=0.6)
    assert gate.triggers(make_task(risk=0.9)) is True
    assert gate.triggers(make_task(risk=0.2)) is False


def test_approval_gate_novelty():
    gate = ApprovalGate(kind="novelty")
    assert gate.triggers(make_task(is_novel=True)) is True
    assert gate.triggers(make_task(is_novel=False)) is False


def test_approval_gate_always():
    gate = ApprovalGate(kind="always")
    assert gate.triggers(make_task(risk=0.0)) is True


def test_approval_gate_cost():
    gate = ApprovalGate(kind="cost", threshold=5.0)
    assert gate.triggers(make_task(cost=6.0)) is True
    assert gate.triggers(make_task(cost=1.0)) is False


def test_approval_gate_unknown_kind():
    gate = ApprovalGate(kind="bogus")
    with pytest.raises(ValueError):
        gate.triggers(make_task())


def test_gate_triggers_on_task():
    inst = Institution(approval_gates=[ApprovalGate(kind="risk", threshold=0.5)])
    t = make_task(risk=0.9)
    r = role("approver")
    assert inst.requires_approval(t, r) is True


def test_effective_risk():
    inst = Institution(risk_acceptance=0.2)
    assert inst.effective_risk(0.8) == pytest.approx(0.6)
    assert inst.effective_risk(0.1) == pytest.approx(0.0)
    assert inst.effective_risk(0.9) == pytest.approx(0.7)


def test_budget_for_default():
    inst = Institution(supervision_budget={"a": 2}, default_supervision_budget=5)
    assert inst.budget_for("a") == 2
    assert inst.budget_for("b") == 5


def test_strategy_enum_from_string():
    inst = Institution(delegation_strategy="command")
    assert inst.delegation_strategy == DelegationStrategy.COMMAND


def test_institution_roundtrip_dict():
    inst = Institution(delegation_strategy="controlled",
                       approval_gates=[ApprovalGate(kind="risk", threshold=0.7)],
                       supervision_budget={"mgr": 3})
    d = inst.to_dict()
    inst2 = Institution.from_dict(d)
    assert inst2.delegation_strategy == inst.delegation_strategy
    assert inst2.approval_gates[0].threshold == 0.7
    assert inst2.supervision_budget == {"mgr": 3}


def test_institution_from_dict_validate_unknown_gate():
    with pytest.raises(ValueError):
        Institution.from_dict({"approval_gates": [{"kind": "nope"}]})


def test_gate_roundtrip():
    g = ApprovalGate(kind="cost", threshold=3.0, name="g")
    assert ApprovalGate.from_dict(g.to_dict()) == g
