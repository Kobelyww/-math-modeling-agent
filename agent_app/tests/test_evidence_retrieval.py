from agent_app.services.evidence_retrieval import MimoEvidenceRetriever


class FakeMimoClient:
    def __init__(self):
        self.requests = []

    def search(self, query: str, limit: int):
        self.requests.append({"query": query, "limit": limit})
        return [
            {
                "title": "Binomial acceptance sampling",
                "url": "https://example.test/sampling",
                "summary": "Acceptance sampling uses binomial probabilities and operating characteristic curves.",
                "relevance": "Supports q1 sampling plan.",
                "credibility_risk": "example source used in unit test",
            }
        ]


class DirtyMimoClient:
    def search(self, query: str, limit: int):
        return [
            {"title": "", "url": "https://example.test/empty-title"},
            {"title": "Missing URL"},
            {"title": "Source field card", "source": "local-reference", "summary": "ok"},
        ]


def test_mimo_evidence_retriever_normalizes_source_cards():
    client = FakeMimoClient()
    retriever = MimoEvidenceRetriever(client=client)

    evidence = retriever.retrieve("二项抽样 检验", top_k=1)

    assert client.requests == [{"query": "二项抽样 检验", "limit": 1}]
    assert evidence[0].evidence_id == "mimo_1"
    assert evidence[0].title == "Binomial acceptance sampling"
    assert evidence[0].source == "https://example.test/sampling"
    assert evidence[0].recommended_use == "method_reference"


def test_mimo_evidence_retriever_can_be_disabled():
    retriever = MimoEvidenceRetriever(client=FakeMimoClient(), enabled=False)

    assert retriever.retrieve("二项抽样", top_k=3) == []


def test_mimo_evidence_retriever_filters_cards_without_title_or_source():
    retriever = MimoEvidenceRetriever(client=DirtyMimoClient())

    evidence = retriever.retrieve("质量控制")

    assert len(evidence) == 1
    assert evidence[0].title == "Source field card"
    assert evidence[0].source == "local-reference"
