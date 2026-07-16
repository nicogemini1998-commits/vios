"""Cache de MediaIntelligence por source_hash (D4)."""
from __future__ import annotations

from vios_contracts import MediaIntelligence


class InMemoryIntelligenceCache:
    def __init__(self) -> None:
        self._store: dict[str, MediaIntelligence] = {}

    def get(self, source_hash: str) -> MediaIntelligence | None:
        return self._store.get(source_hash)

    def put(self, source_hash: str, mi: MediaIntelligence) -> None:
        self._store[source_hash] = mi
