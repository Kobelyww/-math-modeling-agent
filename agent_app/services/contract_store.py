from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agent_app.domain.contracts import Claim, ProblemContract
from agent_app.domain.serialization import from_json_dict, to_json_dict


class ContractStore:
    def __init__(self, run_dir: Path | str) -> None:
        self.run_dir = Path(run_dir)

    def write_problem_contract(self, contract: ProblemContract) -> Path:
        return self._write_json("contracts/problem_contract.json", to_json_dict(contract))

    def read_problem_contract(self) -> ProblemContract:
        payload = self._read_json("contracts/problem_contract.json")
        return from_json_dict(ProblemContract, payload)

    def write_claim_map(self, claims: list[Claim]) -> Path:
        return self._write_json("claims/claim_map.json", to_json_dict(claims))

    def read_claim_map(self) -> list[Claim]:
        payload = self._read_json("claims/claim_map.json")
        return from_json_dict(list[Claim], payload)

    def mark_stale(self, artifact_group: str, reason: str) -> Path:
        safe_group = "".join(ch for ch in artifact_group if ch.isalnum() or ch in ("-", "_"))
        if not safe_group:
            raise ValueError("artifact_group must contain a safe name")
        return self._write_json(
            f"stale/{safe_group}.json",
            {
                "artifact_group": safe_group,
                "reason": reason,
                "created_at": datetime.now().replace(microsecond=0).isoformat(),
            },
        )

    def _write_json(self, relative_path: str, payload: object) -> Path:
        path = self.run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _read_json(self, relative_path: str) -> object:
        path = self.run_dir / relative_path
        return json.loads(path.read_text(encoding="utf-8"))
