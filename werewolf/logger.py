"""结构化游戏日志记录器。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

@dataclass
class GameEvent:
    round_idx: int
    phase: str
    actor_id: int | None
    actor_role: str
    action_type: str
    action_detail: dict[str, Any] = field(default_factory=dict)
    public_visible: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class GameLogger:
    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or (APP_ROOT / "output")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self.events: list[GameEvent] = []

    def log(self, event_or_kwargs) -> GameEvent:
        if isinstance(event_or_kwargs, GameEvent):
            event = event_or_kwargs
        else:
            event = GameEvent(**event_or_kwargs)
        self.events.append(event)
        return event

    def public_log(self) -> list[GameEvent]:
        return [e for e in self.events if e.public_visible]

    def full_log(self) -> list[GameEvent]:
        return self.events

    def save(self, filename: str | None = None) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = filename or f"game_{ts}"
        filepath = self._output_dir / f"{name}.json"
        data = {
            "game_id": name,
            "total_events": len(self.events),
            "events": [
                {
                    "round": e.round_idx,
                    "phase": e.phase,
                    "actor": e.actor_id,
                    "role": e.actor_role,
                    "action": e.action_type,
                    "detail": e.action_detail,
                    "public": e.public_visible,
                    "time": e.timestamp,
                }
                for e in self.events
            ],
        }
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        return filepath

    def save_summary(self, winner: str, reason: str, players: list, filename: str | None = None) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = filename or f"summary_{ts}"
        filepath = self._output_dir / f"{name}.md"
        lines = [
            f"# 狼人杀对局复盘",
            f"",
            f"**结果**：{winner} 胜利",
            f"**原因**：{reason}",
            f"**总局数**：{max((e.round_idx for e in self.events), default=0)} 天",
            f"",
            f"## 玩家身份",
        ]
        for p in players:
            lines.append(f"- {p.player_id}号：{p.role_name}（{'存活' if p.alive else '已出局'}）")
        lines.append("")
        lines.append("## 关键事件")
        for e in self.events:
            if e.action_type in ("kill", "check", "save", "poison", "vote_out", "speech", "hunter_shoot"):
                lines.append(
                    f"- 第{e.round_idx}天 [{e.phase}] "
                    f"{e.actor_id}号({e.actor_role}) {e.action_type} → "
                    f"{e.action_detail.get('target', '')} "
                    f"{e.action_detail.get('extra', '')}"
                )
        filepath.write_text("\n".join(lines), encoding="utf-8")
        return filepath

    def clear(self) -> None:
        self.events.clear()


APP_ROOT = Path(__file__).resolve().parent
