from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from agent_app.domain.models import RunSpec, RunState
from agent_app.domain.serialization import from_json_dict, to_json_dict
from agent_app.infra.paths import validate_run_id


class RunStore:
    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root.resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)

    def create_run(self, spec: RunSpec) -> RunState:
        now = self._now()
        run_id = f"run_{now.replace('-', '').replace(':', '').replace('T', '_')}_{uuid4().hex[:6]}"
        state = RunState(run_id=run_id, spec=spec, created_at=now, updated_at=now)
        self.run_dir(run_id).mkdir(parents=True, exist_ok=False)
        self.save_state(state)
        return state

    def run_dir(self, run_id: str) -> Path:
        validate_run_id(run_id)
        return self.output_root / run_id

    def save_state(self, state: RunState) -> None:
        state.updated_at = self._now()
        path = self.run_dir(state.run_id) / "run.json"
        path.write_text(json.dumps(to_json_dict(state), ensure_ascii=False, indent=2), encoding="utf-8")

    def load_state(self, run_id: str) -> RunState:
        path = self.run_dir(run_id) / "run.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        return from_json_dict(RunState, payload)

    @staticmethod
    def _now() -> str:
        return datetime.now().replace(microsecond=0).isoformat()
