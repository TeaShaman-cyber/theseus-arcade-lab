import json
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

ZENODO_API_BASE = "https://zenodo.org/api"
DEFAULT_TIMEOUT_SECONDS = 30


def _file_summary(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": raw.get("key") or raw.get("name") or "",
        "size": raw.get("size") if raw.get("size") is not None else raw.get("filesize"),
        "checksum": raw.get("checksum"),
    }


def normalize_deposit(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return an allow-listed, model-visible projection of one Zenodo draft record."""
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), Mapping) else {}
    links = raw.get("links") if isinstance(raw.get("links"), Mapping) else {}
    pids = raw.get("pids") if isinstance(raw.get("pids"), Mapping) else {}
    doi_info = pids.get("doi") if isinstance(pids.get("doi"), Mapping) else {}
    files_obj = raw.get("files") if isinstance(raw.get("files"), Mapping) else {}
    entries = files_obj.get("entries") if isinstance(files_obj.get("entries"), list) else []

    return {
        "id": raw.get("id"),
        "title": metadata.get("title") or raw.get("title") or "",
        "is_published": bool(raw.get("is_published", False)),
        "created": raw.get("created"),
        "updated": raw.get("updated"),
        "doi": doi_info.get("identifier"),
        "html_url": links.get("self_html"),
        "files": [_file_summary(item) for item in entries if isinstance(item, Mapping)],
    }


class ZenodoClient:
    """Authenticated client for Zenodo's current InvenioRDM draft-record endpoints."""

    def __init__(
        self,
        access_token: str,
        *,
        base_url: str = ZENODO_API_BASE,
        opener: Callable[..., Any] = urlopen,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not access_token:
            raise ValueError("Zenodo authorization is required")
        self._access_token = access_token
        self._base_url = base_url.rstrip("/")
        self._opener = opener
        self._timeout = timeout

    def _get_json(self, path: str) -> Any:
        request = Request(
            f"{self._base_url}{path}",
            headers={"Authorization": f"Bearer {self._access_token}", "Accept": "application/json"},
            method="GET",
        )
        with self._opener(request, timeout=self._timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def list_deposits(self) -> list[dict[str, Any]]:
        payload = self._get_json("/user/records?q=is_published%3Afalse&size=100")
        if not isinstance(payload, Mapping):
            raise ValueError("Zenodo user-records response must be an object")
        hits = payload.get("hits") if isinstance(payload.get("hits"), Mapping) else {}
        records = hits.get("hits") if isinstance(hits.get("hits"), list) else None
        if records is None:
            raise ValueError("Zenodo user-records response must contain hits.hits")
        return [normalize_deposit(item) for item in records if isinstance(item, Mapping)]

    def get_deposit(self, deposition_id: str) -> dict[str, Any]:
        exact_id = str(deposition_id).strip()
        if not exact_id:
            raise ValueError("deposition_id must be a non-empty Zenodo record ID")
        encoded_id = quote(exact_id, safe="")
        payload = self._get_json(f"/records/{encoded_id}/draft")
        if not isinstance(payload, Mapping):
            raise ValueError("Zenodo draft-record response must be an object")
        return normalize_deposit(payload)
