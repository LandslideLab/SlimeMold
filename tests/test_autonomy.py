"""Tests for the five-level autonomy model."""


from slime_mold import autonomy
from slime_mold.autonomy import (
    AutonomyLevel,
    can_execute,
    requires_approval,
    requires_consultation,
)

ALL_LEVELS = list(AutonomyLevel)


def test_rank_ordering():
    assert AutonomyLevel.OPERATOR.rank < AutonomyLevel.COLLABORATOR.rank
    assert AutonomyLevel.COLLABORATOR.rank < AutonomyLevel.CONSULTANT.rank
    assert AutonomyLevel.CONSULTANT.rank < AutonomyLevel.APPROVER.rank
    assert AutonomyLevel.APPROVER.rank < AutonomyLevel.OBSERVER.rank


def test_roundtrip_rank():
    for rank in range(5):
        assert AutonomyLevel.from_rank(rank).rank == rank


def test_enum_values():
    assert AutonomyLevel("operator").value == "operator"
    assert AutonomyLevel("observer").value == "observer"


def test_can_execute_routine():
    assert can_execute(AutonomyLevel.OPERATOR, risky=False) is False
    assert can_execute(AutonomyLevel.COLLABORATOR, risky=False) is True
    assert can_execute(AutonomyLevel.CONSULTANT, risky=False) is True
    assert can_execute(AutonomyLevel.APPROVER, risky=False) is True
    assert can_execute(AutonomyLevel.OBSERVER, risky=False) is True


def test_can_execute_risky():
    assert can_execute(AutonomyLevel.OPERATOR, risky=True) is False
    assert can_execute(AutonomyLevel.COLLABORATOR, risky=True) is False
    assert can_execute(AutonomyLevel.CONSULTANT, risky=True) is False
    assert can_execute(AutonomyLevel.APPROVER, risky=True) is True
    assert can_execute(AutonomyLevel.OBSERVER, risky=True) is True


def test_requires_consultation_low_levels_always():
    for level in (AutonomyLevel.OPERATOR, AutonomyLevel.COLLABORATOR):
        assert requires_consultation(level, risky=False, novelty=False) is True
        assert requires_consultation(level, risky=True, novelty=False) is True


def test_requires_consultation_consultant():
    c = AutonomyLevel.CONSULTANT
    assert requires_consultation(c, risky=False, novelty=False) is False
    assert requires_consultation(c, risky=True, novelty=False) is True
    assert requires_consultation(c, risky=False, novelty=True) is True


def test_requires_consultation_high_levels_never():
    for level in (AutonomyLevel.APPROVER, AutonomyLevel.OBSERVER):
        assert requires_consultation(level, risky=True, novelty=True) is False


def test_requires_approval():
    assert requires_approval(AutonomyLevel.OPERATOR, risky=False) is True
    assert requires_approval(AutonomyLevel.COLLABORATOR, risky=True) is True
    assert requires_approval(AutonomyLevel.CONSULTANT, risky=False) is False
    assert requires_approval(AutonomyLevel.CONSULTANT, risky=True) is True
    assert requires_approval(AutonomyLevel.APPROVER, risky=True) is False


def test_permissions_table_consistency():
    for level in ALL_LEVELS:
        perms = autonomy._PERMISSIONS[level]
        assert set(perms) == {"execute_routine", "execute_risky", "approve",
                              "delegate", "consult"}
