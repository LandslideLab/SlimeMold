"""Message bus and the complete event log.

All interaction in a SlimeMold simulation happens through messages on a
:class:`MessageBus`. Messages are the only way agents exchange information, and
every message is appended to the run's event log. The bus is turn-ordered and
deterministic: messages are delivered in the order they were sent within a
turn, which guarantees reproducible coordination traces.

The event log is an append-only list of :class:`Event` records. It is the
*evidence base* for every metric (message counts, waiting times, escalation
counts, approval flows) and for the replay animation in the web testbed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageType(str, Enum):
    ASSIGN = "assign"                 # task handed to a role
    SUBMIT = "submit"                 # work product submitted (for approval)
    APPROVE = "approve"               # supervisor approves
    REJECT = "reject"                 # supervisor rejects
    CONSULT = "consult"               # request for advice before acting
    RESPOND = "respond"               # answer to a consult
    ESCALATE = "escalate"             # request pushed up the chain
    REPORT = "report"                 # completion / status report
    NOTIFY = "notify"                 # informational broadcast (knowledge share)


@dataclass(frozen=True)
class Message:
    """A single unit of interaction between two roles."""

    id: str
    kind: MessageType
    sender: str
    receiver: str
    turn: int
    task_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "sender": self.sender,
            "receiver": self.receiver,
            "turn": self.turn,
            "task_id": self.task_id,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class Event:
    """An append-only, time-ordered record of anything that happened."""

    turn: int
    kind: str
    subject: str
    actor: str = ""
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "turn": self.turn,
            "kind": self.kind,
            "subject": self.subject,
            "actor": self.actor,
            "message": self.message,
            "data": self.data,
        }


class MessageBus:
    """Turn-ordered message queue plus full event log."""

    def __init__(self) -> None:
        self._queue: list[Message] = []
        self.messages: list[Message] = []
        self.events: list[Event] = []
        self._msg_counter = 0

    def send(self, kind: MessageType, sender: str, receiver: str, turn: int,
             task_id: str | None = None, payload: dict | None = None) -> Message:
        self._msg_counter += 1
        msg = Message(
            id=f"M{self._msg_counter}",
            kind=kind,
            sender=sender,
            receiver=receiver,
            turn=turn,
            task_id=task_id,
            payload=payload or {},
        )
        self._queue.append(msg)
        self.messages.append(msg)
        self.events.append(
            Event(
                turn=turn,
                kind=f"msg:{kind.value}",
                subject=task_id or "",
                actor=sender,
                message=f"{sender} -> {receiver} [{kind.value}]",
                data={"sender": sender, "receiver": receiver, "task_id": task_id},
            )
        )
        return msg

    def log(self, turn: int, kind: str, subject: str, actor: str = "",
            message: str = "", data: dict | None = None) -> None:
        self.events.append(
            Event(turn=turn, kind=kind, subject=subject, actor=actor,
                  message=message, data=data or {})
        )

    def drain(self) -> list[Message]:
        """Return and clear the current queue (deliver within a turn)."""
        out, self._queue = self._queue, []
        return out

    def pending(self) -> int:
        return len(self._queue)
