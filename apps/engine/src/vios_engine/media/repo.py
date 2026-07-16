"""Repositorio de AssetRecord. InMemory para tests; PgAssetRepo (asyncpg) llega con M3.1."""
from __future__ import annotations

from typing import Protocol

from .models import AssetRecord


class AssetRepo(Protocol):
    def find_by_hash(self, hash_: str) -> AssetRecord | None: ...
    def add(self, record: AssetRecord) -> None: ...
    def get(self, asset_id: str) -> AssetRecord | None: ...


class InMemoryAssetRepo:
    def __init__(self) -> None:
        self._by_id: dict[str, AssetRecord] = {}
        self._by_hash: dict[str, AssetRecord] = {}

    def find_by_hash(self, hash_: str) -> AssetRecord | None:
        return self._by_hash.get(hash_)

    def add(self, record: AssetRecord) -> None:
        self._by_id[record.id] = record
        self._by_hash[record.hash] = record

    def get(self, asset_id: str) -> AssetRecord | None:
        return self._by_id.get(asset_id)
