"""Tests for the knowledge mechanism."""

import random

from slimemold.knowledge import KnowledgeItem, KnowledgeMechanism


def make_knowledge(**kwargs):
    defaults = {"sharing_probability": 1.0, "half_life": 100.0,
                "revalidation_probability": 0.0, "max_items_per_member": 10,
                "noise": 0.0}
    defaults.update(kwargs)
    return KnowledgeMechanism(**defaults)


def test_observe_outcome_creates_item():
    kn = make_knowledge()
    rng = random.Random(1)
    kn.set_environment(lambda *a: True, rng)
    item = kn.observe_outcome("m", "t", "ctx", True, 1)
    assert item.confidence == 0.6
    assert kn.item("m", "t", "ctx") is item


def test_observe_success_increases_confidence():
    kn = make_knowledge()
    kn.set_environment(lambda *a: True, random.Random(1))
    kn.observe_outcome("m", "t", "ctx", True, 1)
    item = kn.observe_outcome("m", "t", "ctx", True, 2)
    assert item.confidence == 0.7


def test_observe_failure_decreases_confidence():
    kn = make_knowledge()
    kn.set_environment(lambda *a: True, random.Random(1))
    kn.observe_outcome("m", "t", "ctx", True, 1)
    item = kn.observe_outcome("m", "t", "ctx", False, 2)
    assert item.confidence < 0.6


def test_knowledge_effect_returns_boost():
    kn = make_knowledge()
    kn.set_environment(lambda *a: True, random.Random(1))
    kn.observe_outcome("m", "t", "ctx", True, 1)
    effect, has = kn.knowledge_effect("m", "t", "ctx", random.Random(2))
    assert has is True
    assert 0.0 < effect <= 1.0


def test_knowledge_effect_missing():
    kn = make_knowledge()
    kn.set_environment(lambda *a: True, random.Random(1))
    effect, has = kn.knowledge_effect("m", "missing", "ctx", random.Random(2))
    assert has is False
    assert effect == 0.0


def test_share_to_propagates():
    kn = make_knowledge()
    kn.set_environment(lambda *a: True, random.Random(1))
    item = kn.observe_outcome("m1", "t", "ctx", True, 1)
    kn.share_to("m2", item, 2)
    assert kn.item("m2", "t", "ctx") is not None


def test_share_to_respects_probability():
    kn = make_knowledge(sharing_probability=0.0)
    kn.set_environment(lambda *a: True, random.Random(1))
    item = kn.observe_outcome("m1", "t", "ctx", True, 1)
    kn.share_to("m2", item, 2)
    assert kn.item("m2", "t", "ctx") is None


def test_half_life_decay():
    kn = make_knowledge(half_life=10.0)
    kn.set_environment(lambda *a: True, random.Random(1))
    item = kn.observe_outcome("m", "t", "ctx", True, 1)
    kn.step_forgetting(11)
    decayed = kn.item("m", "t", "ctx")
    assert decayed.confidence < item.confidence


def test_revalidation_drops_stale_invalid_items():
    kn = make_knowledge(half_life=5.0, revalidation_probability=1.0)
    kn.set_environment(lambda task_type, turn: False, random.Random(1))
    kn.observe_outcome("m", "t", "ctx", True, 1)
    kn.step_revalidation(20)
    assert kn.item("m", "t", "ctx") is None
    assert kn.revalidation_rate() < 1.0


def test_revalidation_rate_full_when_none():
    kn = make_knowledge()
    kn.set_environment(lambda *a: True, random.Random(1))
    assert kn.revalidation_rate() == 1.0


def test_retention_rate():
    kn = make_knowledge()
    kn.set_environment(lambda *a: True, random.Random(1))
    kn.observe_outcome("m", "t", "ctx", True, 1)
    assert kn.retention_rate(5) == 1.0
    assert kn.size() == 1


def test_eviction_caps_memory():
    kn = make_knowledge(max_items_per_member=3)
    kn.set_environment(lambda *a: True, random.Random(1))
    for i in range(10):
        kn.observe_outcome("m", f"t{i}", "ctx", True, i)
    assert kn.size() <= 3


def test_global_count():
    kn = make_knowledge()
    kn.set_environment(lambda *a: True, random.Random(1))
    kn.observe_outcome("m", "t", "ctx", True, 1)
    kn.observe_outcome("m", "t", "ctx", True, 2)
    assert kn.global_count()[("t", "ctx")] == 2


def test_to_dict():
    kn = make_knowledge()
    kn.set_environment(lambda *a: True, random.Random(1))
    kn.observe_outcome("m", "t", "ctx", True, 1)
    d = kn.to_dict()
    assert d["size"] == 1
    assert "retention_rate" in d


def test_knowledge_item_to_dict():
    item = KnowledgeItem(task_type="t", context="c", action="a",
                         confidence=0.8, created_at=1)
    d = item.to_dict()
    assert d["confidence"] == 0.8
    assert d["valid"] is True
