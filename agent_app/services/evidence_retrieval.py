from __future__ import annotations

from datetime import datetime
from typing import Protocol

from agent_app.domain.contracts import EvidenceItem


class MimoSearchClient(Protocol):
    def search(self, query: str, limit: int) -> list[dict]:
        raise NotImplementedError


class MimoEvidenceRetriever:
    def __init__(self, client: MimoSearchClient, enabled: bool = True) -> None:
        self.client = client
        self.enabled = enabled

    def retrieve(self, query: str, top_k: int = 5, recommended_use: str = "method_reference") -> list[EvidenceItem]:
        if not self.enabled:
            return []
        cards = self.client.search(query, limit=top_k)
        retrieved_at = datetime.now().replace(microsecond=0).isoformat()
        return [
            EvidenceItem(
                evidence_id=f"mimo_{index}",
                title=str(card.get("title", "")).strip(),
                source=str(card.get("url") or card.get("source") or "").strip(),
                summary=str(card.get("summary", "")).strip(),
                relevance=str(card.get("relevance", "")).strip(),
                credibility_risk=str(card.get("credibility_risk", "")).strip(),
                retrieved_at=retrieved_at,
                recommended_use=recommended_use,
            )
            for index, card in enumerate(cards, start=1)
            if card.get("title") and (card.get("url") or card.get("source"))
        ]
