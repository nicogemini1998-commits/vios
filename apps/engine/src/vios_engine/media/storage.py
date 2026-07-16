"""Backends de almacenamiento. Media SIEMPRE por URL/clave, nunca base64 (D6)."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    def put(self, local_path: str | Path, key: str) -> str: ...
    def exists(self, key: str) -> bool: ...
    def url_for(self, key: str) -> str: ...


class LocalStorage:
    """Filesystem backend para dev/tests. La 'URL' es una ruta bajo `root`."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dest(self, key: str) -> Path:
        return self.root / key

    def put(self, local_path: str | Path, key: str) -> str:
        dest = self._dest(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_path, dest)
        return self.url_for(key)

    def exists(self, key: str) -> bool:
        return self._dest(key).exists()

    def url_for(self, key: str) -> str:
        return f"file://{self._dest(key)}"


class SupabaseStorage:
    """Backend Supabase Storage (producción). Stub hasta crear el proyecto VIOS (M3.1)."""

    def __init__(self, url: str, service_key: str, bucket: str) -> None:
        self.url = url
        self.service_key = service_key
        self.bucket = bucket

    def put(self, local_path: str | Path, key: str) -> str:  # pragma: no cover
        raise NotImplementedError("SupabaseStorage se completa al crear el proyecto VIOS (M3.1)")

    def exists(self, key: str) -> bool:  # pragma: no cover
        raise NotImplementedError

    def url_for(self, key: str) -> str:  # pragma: no cover
        return f"{self.url}/storage/v1/object/public/{self.bucket}/{key}"
