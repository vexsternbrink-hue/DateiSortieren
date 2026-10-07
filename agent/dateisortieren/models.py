"""Gemeinsame Datenstrukturen."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

ActionKind = Literal["move", "delete", "compress"]
ActionStatus = Literal[
    "proposed",  # Dry-Run: würde ausgeführt werden
    "approved",  # im Dashboard / CLI freigegeben
    "rejected",
    "applied",
    "skipped",  # z. B. Komprimierung brachte keine Ersparnis
    "failed",
    "undo_requested",
    "undone",
]


def now_iso() -> str:
    # Mikrosekunden: Undo braucht eine eindeutige Reihenfolge auch innerhalb einer Sekunde
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Classification:
    category: str
    doc_type: str = ""
    title: str = ""
    vendor: str | None = None
    date: str | None = None  # YYYY-MM-DD
    amount: float | None = None
    currency: str | None = None
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    summary: str = ""
    source: str = "heuristic"  # heuristic | rule:<name> | anthropic | openai | ollama

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Action:
    kind: ActionKind
    src: str
    dst: str | None = None
    reason: str = ""
    confidence: float = 1.0
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=new_id)
    batch_id: str | None = None
    status: ActionStatus = "proposed"
    backup_path: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=now_iso)
    applied_at: str | None = None
    undone_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_cloud(self) -> dict[str, Any]:
        """Format für die Dashboard-API (Spaltennamen der Supabase-Tabelle)."""
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "kind": self.kind,
            "status": self.status,
            "src_path": self.src,
            "dst_path": self.dst,
            "reason": self.reason,
            "confidence": self.confidence,
            "category": self.category,
            "tags": self.tags,
            "details": self.details,
            "error": self.error,
            "created_at": self.created_at,
            "applied_at": self.applied_at,
            "undone_at": self.undone_at,
        }

    @classmethod
    def from_cloud(cls, row: dict[str, Any]) -> "Action":
        return cls(
            id=row["id"],
            batch_id=row.get("batch_id"),
            kind=row["kind"],
            status=row.get("status", "proposed"),
            src=row["src_path"],
            dst=row.get("dst_path"),
            reason=row.get("reason") or "",
            confidence=row.get("confidence") or 0.0,
            category=row.get("category"),
            tags=row.get("tags") or [],
            details=row.get("details") or {},
        )


@dataclass
class Plan:
    batch_id: str = field(default_factory=new_id)
    actions: list[Action] = field(default_factory=list)

    def add(self, action: Action) -> None:
        action.batch_id = self.batch_id
        self.actions.append(action)

    def __len__(self) -> int:
        return len(self.actions)
