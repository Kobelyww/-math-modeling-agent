"""对局复盘与归因分析。"""

from __future__ import annotations

import json
from pathlib import Path


class GameReplay:
    def __init__(self, log_path: str | Path) -> None:
        self.log_path = Path(log_path)
        self.data = json.loads(self.log_path.read_text())

    def get_timeline(self) -> list[dict]:
        """按时间顺序重建对局事件线。"""
        return sorted(self.data.get("events", []), key=lambda e: (e.get("round", 0), e.get("phase", "")))

    def get_night_actions(self) -> list[dict]:
        return [e for e in self.get_timeline() if "night" in e.get("phase", "")]

    def get_day_actions(self) -> list[dict]:
        return [e for e in self.get_timeline() if "day" in e.get("phase", "")]

    def get_player_actions(self, player_id: int) -> list[dict]:
        return [e for e in self.get_timeline() if e.get("actor") == player_id]

    def find_turning_points(self) -> list[str]:
        """识别对局关键转折点。"""
        points: list[str] = []
        events = self.get_timeline()

        for e in events:
            if e.get("action") == "save":
                points.append(f"第{e['round']}天：女巫使用解药救了{e['detail'].get('target')}号")
            if e.get("action") == "poison":
                target = e["detail"].get("target")
                role = e.get("role", "")
                points.append(f"第{e['round']}天：女巫毒杀{target}号")
            if e.get("action") == "check" and e["detail"].get("result") == "狼人":
                points.append(f"第{e['round']}天：预言家查验{e['detail'].get('target')}号为狼人")
            if e.get("action") == "hunter_shoot":
                points.append(f"猎人开枪带走{e['detail'].get('target')}号")

        return points

    def generate_narrative(self) -> str:
        """生成对局叙事总结。"""
        timeline = self.get_timeline()
        points = self.find_turning_points()

        lines = ["# 对局复盘", "", f"总事件数：{len(timeline)}", ""]
        if points:
            lines.append("## 关键转折点")
            for p in points:
                lines.append(f"- {p}")

        lines.append("")
        lines.append("## 完整时间线")
        current_day = -1
        for e in timeline:
            day = e.get("round", 0)
            if day != current_day:
                current_day = day
                lines.append(f"\n### 第 {day} 天")
            lines.append(
                f"- [{e.get('phase')}] {e.get('actor')}号({e.get('role')}) "
                f"{e.get('action')} {e.get('detail', '')}"
            )

        return "\n".join(lines)
