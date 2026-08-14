"""DSL parsing: turn a spec (dict or YAML) into runnable engine objects.

The SlimeMold DSL describes an *organization design*:

.. code-block:: yaml

    name: my-org
    sim: {turns: 100, seed: 42}
    organization:
      name: cs-hierarchy
      roles:
        - id: manager
          capabilities: [review]
          autonomy: approver
        - id: agent1
          capabilities: [t1]
          autonomy: collaborator
      reporting:
        agent1: manager
    institution:
      delegation_strategy: controlled
      supervision_budget: {manager: 5}
      approval_gates:
        - {kind: risk, threshold: 0.6}
    taskflow:
      arrival_rate: 1.2
      task_types: [t1, t2]
      dynamism: 0.02
    knowledge:
      sharing_probability: 0.7
      half_life: 40
    turnover:
      per_turn_probability: 0.002
    agents:
      - {role: agent1, error_probability: 0.15}

The ``agents`` section is optional and overrides per-role policy parameters.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..agents import ScriptedPolicy
from ..institution import ApprovalGate, Institution
from ..knowledge import KnowledgeMechanism
from ..organization import Organization, TopologyError
from ..roles import OrgRole
from ..simulation import SimConfig
from ..tasks import TaskFlow
from ..turnover import Turnover


class SpecError(ValueError):
    """Raised when a DSL spec is malformed."""


@dataclass
class BuildResult:
    """Everything needed to construct a SimulationRunner."""

    name: str
    sim: SimConfig
    org: Organization
    institution: Institution
    taskflow: TaskFlow
    turnover: Turnover
    knowledge: KnowledgeMechanism
    policy_overrides: dict[str, ScriptedPolicy]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "sim": self.sim.to_dict(),
            "organization": self.org.to_dict(),
            "institution": self.institution.to_dict(),
            "taskflow": {
                "arrival_rate": self.taskflow.arrival_rate,
                "task_types": self.taskflow.task_types,
                "dynamism": self.taskflow.dynamism,
            },
            "turnover": self.turnover.to_dict(),
            "knowledge": {
                "sharing_probability": self.knowledge.sharing_probability,
                "half_life": self.knowledge.half_life,
                "revalidation_probability": self.knowledge.revalidation_probability,
            },
        }


def build_spec(spec: dict | str | bytes) -> BuildResult:
    """Build a :class:`BuildResult` from a spec dict, YAML string or file path."""
    data = _load(spec)
    if not isinstance(data, dict):
        raise SpecError("spec must be a mapping at the top level")
    return _build(data)


def _load(spec: dict | str | bytes) -> dict:
    if isinstance(spec, dict):
        return spec
    if isinstance(spec, (str, bytes)):
        from .yamlmini import parse_yaml

        text = spec.decode("utf-8") if isinstance(spec, bytes) else spec
        if isinstance(spec, str) and not text.lstrip().startswith(("{", "[")):
            import os

            if os.path.exists(text):
                with open(text, "r", encoding="utf-8") as fh:
                    text = fh.read()
        return parse_yaml(text)
    raise SpecError("spec must be a mapping, YAML string, or file path")


def _build(data: dict) -> BuildResult:
    org_data = data.get("organization")
    if not isinstance(org_data, dict):
        raise SpecError("spec must define 'organization'")

    sim = SimConfig.from_dict(data.get("sim", {}))
    org = _build_org(org_data)
    inst = _build_institution(data.get("institution", {}))
    tf = _build_taskflow(data.get("taskflow", {}))
    turn = _build_turnover(data.get("turnover", {}))
    kn = _build_knowledge(data.get("knowledge", {}))

    overrides: dict[str, ScriptedPolicy] = {}
    for agent in data.get("agents", []):
        role_id = agent.get("role")
        if not role_id or role_id not in org.roles:
            raise SpecError(f"agents section references unknown role: {role_id}")
        overrides[role_id] = ScriptedPolicy(
            error_probability=agent.get("error_probability", 0.15),
            delegate_when_possible=agent.get("delegate_when_possible", True),
            escalation_probability=agent.get("escalation_probability", 0.05),
            risk_aversion=agent.get("risk_aversion", 0.0),
            knowledge_weight=agent.get("knowledge_weight", 0.4),
        )

    return BuildResult(
        name=data.get("name", "organization"),
        sim=sim,
        org=org,
        institution=inst,
        taskflow=tf,
        turnover=turn,
        knowledge=kn,
        policy_overrides=overrides,
    )


def _build_org(data: dict) -> Organization:
    roles: list[OrgRole] = []
    raw_roles = data.get("roles", [])
    if isinstance(raw_roles, dict):
        for rid, rdata in raw_roles.items():
            entry = dict(rdata) if isinstance(rdata, dict) else {}
            entry.setdefault("id", rid)
            raw_roles = []
            roles.append(OrgRole.from_dict(entry))
    if isinstance(raw_roles, list):
        for entry in raw_roles:
            roles.append(OrgRole.from_dict(entry))
    reporting = dict(data.get("reporting") or {})
    try:
        return Organization.from_spec(
            roles,
            reporting,
            name=data.get("name", "organization"),
            allow_disconnected=data.get("allow_disconnected", False),
        )
    except TopologyError as exc:
        raise SpecError(f"organization topology is invalid: {exc}")


def _build_institution(data: dict) -> Institution:
    gates = [ApprovalGate.from_dict(g) for g in (data.get("approval_gates") or [])]
    return Institution(
        delegation_strategy=data.get("delegation_strategy", "controlled"),
        approval_gates=gates,
        supervision_budget=dict(data.get("supervision_budget") or {}),
        default_supervision_budget=data.get("default_supervision_budget"),
        approval_turn_cost=data.get("approval_turn_cost", 1),
        escalation_timeout=data.get("escalation_timeout", 5),
        max_wait_turns=data.get("max_wait_turns", 12),
        risk_acceptance=data.get("risk_acceptance", 0.0),
    )


def _build_taskflow(data: dict) -> TaskFlow:
    types = data.get("task_types", ["t1", "t2", "t3"])
    capability_map = data.get("capability_by_type") or {}
    if not capability_map:
        capability_map = {t: t for t in types}
    return TaskFlow(
        arrival_rate=data.get("arrival_rate", 1.0),
        task_types=list(types),
        capability_by_type=capability_map,
        complexity_mu=data.get("complexity_mu", 0.4),
        risk_mu=data.get("risk_mu", 0.3),
        cost_mu=data.get("cost_mu", 1.0),
        dynamism=data.get("dynamism", 0.0),
        anomaly_probability=data.get("anomaly_probability", 0.02),
        novelty_probability=data.get("novelty_probability", 0.05),
        shift_every=data.get("shift_every"),
        load_multiplier=data.get("load_multiplier", 1.0),
    )


def _build_turnover(data: dict) -> Turnover:
    return Turnover(
        per_turn_probability=data.get("per_turn_probability", 0.0),
        schedule=data.get("schedule", {}),
        replace_experience=data.get("replace_experience", 0.2),
        onboarding_turns=data.get("onboarding_turns", 10),
        knowledge_loss_fraction=data.get("knowledge_loss_fraction", 0.8),
    )


def _build_knowledge(data: dict) -> KnowledgeMechanism:
    return KnowledgeMechanism(
        sharing_probability=data.get("sharing_probability", 0.7),
        half_life=data.get("half_life", 40.0),
        revalidation_probability=data.get("revalidation_probability", 0.1),
        max_items_per_member=data.get("max_items_per_member", 50),
        noise=data.get("noise", 0.1),
    )
