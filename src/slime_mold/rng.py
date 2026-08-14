"""Deterministic random number streams for the simulation engine.

Reproducibility is a first-class requirement of SlimeMold. All randomness in a
simulation flows through a single :class:`SeededRandom` master stream. Every
subsystem (task arrival, agent behaviour, turnover, knowledge) receives its own
:class:`random.Random` *child* stream whose seed is derived deterministically
from the master seed and a stable tag hash (SHA-256), so subsystem draws never
perturb one another and results are bit-for-bit reproducible across platforms
and Python versions.
"""

from __future__ import annotations

import hashlib
import random


def _derive_seed(master_seed: int, tag: str) -> int:
    """Derive a stable child seed from a master seed and a subsystem tag."""
    digest = hashlib.sha256(f"{master_seed}:{tag}".encode()).hexdigest()
    return int(digest[:16], 16)


class SeededRandom:
    """A master stream plus lazily created, deterministic child streams.

    Parameters
    ----------
    seed:
        The master seed. Any ``int`` is accepted. A ``None`` seed is expanded
        from ``os.urandom`` so that a "random" run is still fully deterministic
        for that run (the expanded seed is recorded in the run metadata).
    """

    def __init__(self, seed: int | None = None) -> None:
        if seed is None:
            seed = random.SystemRandom().getrandbits(128)
        self.master_seed = int(seed)
        self._master = random.Random(self.master_seed)
        self._children: dict[str, random.Random] = {}

    def child(self, tag: str) -> random.Random:
        """Return (creating on first use) the child stream for a subsystem."""
        if tag not in self._children:
            self._children[tag] = random.Random(_derive_seed(self.master_seed, tag))
        return self._children[tag]

    def master(self) -> random.Random:
        """Return the master stream used for structural draws."""
        return self._master

    def __getattr__(self, item: str):
        """Proxy unknown attribute access to the master stream."""
        return getattr(self._master, item)

    def to_dict(self) -> dict:
        """Serialize for reproduction metadata."""
        return {
            "master_seed": self.master_seed,
            "child_tags": sorted(self._children),
        }
