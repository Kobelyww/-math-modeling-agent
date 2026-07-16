from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agent_app.domain.contracts import (
    Claim,
    PaperOutline,
    ProblemContract,
    StagedPaperManifest,
    SymbolDefinition,
)
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

    def write_paper_outline(self, outline: PaperOutline) -> Path:
        return self._write_json("paper_outline.json", to_json_dict(outline))

    def read_paper_outline(self) -> PaperOutline:
        payload = self._read_json("paper_outline.json")
        return from_json_dict(PaperOutline, payload)

    def write_staged_paper_manifest(self, manifest: StagedPaperManifest) -> Path:
        return self._write_json("staged_paper_manifest.json", to_json_dict(manifest))

    def read_staged_paper_manifest(self) -> StagedPaperManifest:
        payload = self._read_json("staged_paper_manifest.json")
        return from_json_dict(StagedPaperManifest, payload)

    def write_symbol_table(self, symbols: list[SymbolDefinition]) -> Path:
        return self._write_json("symbol_table.json", to_json_dict(symbols))

    def read_symbol_table(self) -> list[SymbolDefinition]:
        payload = self._read_json("symbol_table.json")
        return from_json_dict(list[SymbolDefinition], payload)

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
