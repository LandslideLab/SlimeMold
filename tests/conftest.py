"""Shared fixtures and helpers for the SlimeMold test-suite."""

import pytest

from slimemold.dsl import build_spec


@pytest.fixture
def hierarchy_spec_dict():
    return {
        "name": "test-org",
        "sim": {"turns": 40, "seed": 7},
        "organization": {
            "name": "hierarchy",
            "roles": [
                {"id": "mgr", "capabilities": ["review"], "autonomy": "approver"},
                {"id": "a1", "capabilities": ["t1"], "autonomy": "collaborator"},
                {"id": "a2", "capabilities": ["t2"], "autonomy": "collaborator"},
            ],
            "reporting": {"a1": "mgr", "a2": "mgr"},
        },
        "institution": {
            "delegation_strategy": "controlled",
            "supervision_budget": {"mgr": 5},
        },
        "taskflow": {"arrival_rate": 1.0, "task_types": ["t1", "t2"]},
    }


@pytest.fixture
def flat_spec_dict():
    return {
        "name": "test-flat",
        "sim": {"turns": 40, "seed": 7},
        "organization": {
            "name": "flat",
            "roles": [
                {"id": "a1", "capabilities": ["t1"], "autonomy": "approver"},
                {"id": "a2", "capabilities": ["t2"], "autonomy": "approver"},
            ],
            "reporting": {"a1": None, "a2": None},
        },
        "institution": {"delegation_strategy": "full"},
        "taskflow": {"arrival_rate": 1.0, "task_types": ["t1", "t2"]},
    }


@pytest.fixture
def built_hierarchy(hierarchy_spec_dict):
    return build_spec(hierarchy_spec_dict)


@pytest.fixture
def built_flat(flat_spec_dict):
    return build_spec(flat_spec_dict)
