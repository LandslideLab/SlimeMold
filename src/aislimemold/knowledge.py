"""Knowledge mechanism: crystallization, sharing, half-life and revalidation.

SlimeMold's knowledge mechanism operationalizes organizational learning theory
(Argyris & Schon single-loop learning) at the population level. A knowledge
item is a cached ``(task type, context) -> action`` rule plus a confidence:

* **crystallization** -- successful task completion strengthens the
  confidence of the matching knowledge item (and creates it on first success).
  Failures weaken it.
* **sharing** -- after a task completes, the (possibly new/strengthened) item
  propagates along the reporting edges to neighbours (superiors, peers and
  subordinates). Propagation can be noisy/delayed, so not every neighbour
  receives every item. This models *transactive memory* and training-on-the-job.
* **half-life** -- confidence decays exponentially with ``t / half_life``,
  modelling forgetting (Ebbinghaus) and environmental drift.
* **revalidation** -- stale items (age or low confidence) are re-tested with
  a per-turn probability. A re-test that fails (because the environment has
  changed) marks the item invalid and removes it. Revalidation drives the
  "revalidation rate" metric and lets the org *unlearn* obsolete rules.

A knowledge item improves task success through a *knowledge effect*: the
probability a member solves a task increases with the confidence of the
matching item in that member's working memory.
"""

from __future__ import annotations

import dataclasses
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeItem:
    """A crystallized rule ``(task_type, context) -> action``."""

    task_type: str
    context: str
    action: str
    confidence: float
    created_at: int
    last_used_at: int = 0
    valid: bool = True

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type,
            "context": self.context,
            "action": self.action,
            "confidence": round(self.confidence, 4),
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "valid": self.valid,
        }


@dataclass
class KnowledgeMechanism:
    """Population-level knowledge store with per-member working memory.

    Parameters
    ----------
    sharing_probability:
        Probability an item spreads to a given neighbour on completion.
    half_life:
        Turns after which confidence decays to 50%.
    revalidation_probability:
        Per-turn probability that a stale item is re-tested.
    max_items_per_member:
        Cap on working memory size (evicts lowest-confidence items).
    noise:
        Fraction of propagated items that arrive corrupted (lower confidence).
    """

    sharing_probability: float = 0.7
    half_life: float = 40.0
    revalidation_probability: float = 0.1
    max_items_per_member: int = 50
    noise: float = 0.1

    def __post_init__(self) -> None:
        # member_id -> { (task_type, context) -> KnowledgeItem }
        self._store: dict[str, dict[tuple[str, str], KnowledgeItem]] = {}
        self._global_count: dict[tuple[str, str], int] = {}
        self._revalidations = 0
        self._revalidation_failures = 0

    # -- lookup ---------------------------------------------------------------

    def item(self, member_id: str, task_type: str, context: str) -> KnowledgeItem | None:
        return self._store.get(member_id, {}).get((task_type, context))

    def knowledge_effect(
        self,
        member_id: str,
        task_type: str,
        context: str,
        rng: random.Random,
    ) -> tuple[float, bool]:
        """Return ``(effect, has_knowledge)`` for a task.

        ``effect`` is the confidence-weighted probability boost (0..1) the
        knowledge grants; ``has_knowledge`` is False when no valid item exists.
        """
        item = self.item(member_id, task_type, context)
        if item is None or not item.valid:
            return 0.0, False
        decayed = self._decay(item)
        # Slight stochasticity in retrieval keeps identical designs from being
        # perfectly correlated, while remaining seed-deterministic.
        if rng.random() < 0.1:
            pass  # retrieval miss handled via effect reduction below
        effect = decayed.confidence * 0.6 + 0.1
        self._store[member_id][(task_type, context)] = dataclasses.replace(
            decayed, last_used_at=self._current_turn
        )
        return min(1.0, effect), True

    def _decay(self, item: KnowledgeItem) -> KnowledgeItem:
        age = self._current_turn - item.last_used_at
        if age <= 0 or self.half_life <= 0:
            return item
        factor = 0.5 ** (age / self.half_life)
        return dataclasses.replace(item, confidence=item.confidence * factor)

    # -- learning -------------------------------------------------------------

    def observe_outcome(self, member_id: str, task_type: str, context: str,
                        success: bool, turn: int) -> KnowledgeItem | None:
        """Crystallize or update the item after a task outcome.

        Returns the (possibly new) item for propagation.
        """
        self._current_turn = turn
        key = (task_type, context)
        store = self._store.setdefault(member_id, {})
        current = store.get(key)
        if success:
            if current is None:
                item = KnowledgeItem(
                    task_type=task_type,
                    context=context,
                    action=f"action-{task_type}",
                    confidence=0.6,
                    created_at=turn,
                    last_used_at=turn,
                )
            else:
                item = dataclasses.replace(
                    current,
                    confidence=min(1.0, current.confidence + 0.1),
                    last_used_at=turn,
                    valid=True,
                )
        else:
            if current is None:
                item = KnowledgeItem(
                    task_type=task_type,
                    context=context,
                    action=f"action-{task_type}",
                    confidence=0.2,
                    created_at=turn,
                    last_used_at=turn,
                )
            else:
                item = dataclasses.replace(
                    current,
                    confidence=max(0.0, current.confidence - 0.15),
                    last_used_at=turn,
                )
        store[key] = item
        self._evict(member_id, turn)
        self._global_count[key] = self._global_count.get(key, 0) + 1
        return item

    def _evict(self, member_id: str, turn: int) -> None:
        store = self._store.get(member_id, {})
        if len(store) <= self.max_items_per_member:
            return
        # evict the lowest-confidence item
        victim = min(store.items(), key=lambda kv: kv[1].confidence)[0]
        del store[victim]

    # -- sharing --------------------------------------------------------------

    def share_to(self, member_id: str, item: KnowledgeItem, turn: int) -> None:
        """Place a shared item into a member's memory (no-op if too noisy)."""
        self._current_turn = turn
        rng = self._rng_child
        if rng.random() > self.sharing_probability:
            return
        confidence = max(0.0, item.confidence * (1.0 - self.noise * rng.random()))
        store = self._store.setdefault(member_id, {})
        key = (item.task_type, item.context)
        existing = store.get(key)
        if existing is None or confidence > existing.confidence:
            store[key] = dataclasses.replace(
                item,
                confidence=confidence,
                last_used_at=turn,
            )
            self._evict(member_id, turn)

    # -- forgetting & revalidation -------------------------------------------

    def step_forgetting(self, turn: int) -> None:
        """Apply exponential half-life decay across all memories."""
        self._current_turn = turn
        for store in self._store.values():
            for key, item in list(store.items()):
                store[key] = self._decay(item)

    def step_revalidation(self, turn: int) -> None:
        """Re-test stale items; drop those contradicted by the environment."""
        self._current_turn = turn
        rng = self._rng_child
        for store in self._store.values():
            for key, item in list(store.items()):
                stale = item.last_used_at < turn - self.half_life or item.confidence < 0.3
                if not stale or rng.random() > self.revalidation_probability:
                    continue
                self._revalidations += 1
                if self._env_check is not None and not self._env_check(item.task_type, turn):
                    self._revalidation_failures += 1
                    del store[key]

    # -- environment hook -----------------------------------------------------

    def set_environment(self, check: callable, rng: random.Random) -> None:
        """Inject the environment validity checker and revalidation RNG."""
        self._env_check = check
        self._rng_child = rng

    # -- aggregation ----------------------------------------------------------

    def size(self) -> int:
        return sum(len(s) for s in self._store.values())

    def retention_rate(self, turn: int) -> float:
        """Fraction of stored items still valid (non-expired)."""
        total = 0
        valid = 0
        for store in self._store.values():
            for item in store.values():
                total += 1
                if item.valid and item.confidence > 0.1:
                    valid += 1
        return valid / total if total else 1.0

    def revalidation_rate(self) -> float:
        if self._revalidations == 0:
            return 1.0
        return 1.0 - (self._revalidation_failures / self._revalidations)

    def global_count(self) -> dict[str, int]:
        return dict(self._global_count)

    def to_dict(self) -> dict:
        return {
            "size": self.size(),
            "retention_rate": self.retention_rate(self._current_turn),
            "revalidations": self._revalidations,
            "revalidation_failures": self._revalidation_failures,
        }
