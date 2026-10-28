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
    """Return an allow-listed, model-visible projection of one Zenodo record/draft."""
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
    """Authenticated client for Zenodo's current InvenioRDM record/draft endpoints."""

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

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: Any | None = None,
        raw_data: bytes | None = None,
        content_type: str = "application/json",
    ) -> Any:
        if payload is not None and raw_data is not None:
            raise ValueError("payload and raw_data are mutually exclusive")
        data = raw_data
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }
        if data is not None:
            headers["Content-Type"] = content_type
        request = Request(f"{self._base_url}{path}", data=data, headers=headers, method=method)
        with self._opener(request, timeout=self._timeout) as response:
            raw = response.read()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    @staticmethod
    def _record_id(value: str) -> str:
        exact = str(value).strip()
        if not exact:
            raise ValueError("deposition_id must be a non-empty Zenodo record ID")
        return quote(exact, safe="")

    @staticmethod
    def _file_key(value: str) -> str:
        exact = str(value).strip()
        if not exact:
            raise ValueError("filename must be non-empty")
        return quote(exact, safe="")

    def _get_draft_raw(self, deposition_id: str) -> Mapping[str, Any]:
        encoded_id = self._record_id(deposition_id)
        payload = self._request_json(f"/records/{encoded_id}/draft")
        if not isinstance(payload, Mapping):
            raise ValueError("Zenodo draft-record response must be an object")
        return payload

    def list_deposits(self) -> list[dict[str, Any]]:
        payload = self._request_json("/user/records?q=is_published%3Afalse&size=100")
        if not isinstance(payload, Mapping):
            raise ValueError("Zenodo user-records response must be an object")
        hits = payload.get("hits") if isinstance(payload.get("hits"), Mapping) else {}
        records = hits.get("hits") if isinstance(hits.get("hits"), list) else None
        if records is None:
            raise ValueError("Zenodo user-records response must contain hits.hits")
        return [normalize_deposit(item) for item in records if isinstance(item, Mapping)]

    def get_deposit(self, deposition_id: str) -> dict[str, Any]:
        return normalize_deposit(self._get_draft_raw(deposition_id))

    def create_deposit(self, metadata: Mapping[str, Any] | None = None, *, files_enabled: bool = True) -> dict[str, Any]:
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ValueError("metadata must be an object")
        body: dict[str, Any] = {"files": {"enabled": bool(files_enabled)}}
        if metadata:
            body["metadata"] = dict(metadata)
        payload = self._request_json("/records", method="POST", payload=body)
        if not isinstance(payload, Mapping):
            raise ValueError("Zenodo create-record response must be an object")
        return normalize_deposit(payload)

    def update_deposit(self, deposition_id: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(metadata, Mapping) or not metadata:
            raise ValueError("metadata must be a non-empty object")
        encoded_id = self._record_id(deposition_id)
        current = self._get_draft_raw(deposition_id)
        writable: dict[str, Any] = {}
        for key in ("metadata", "access", "files", "pids", "custom_fields"):
            value = current.get(key)
            if isinstance(value, Mapping):
                writable[key] = dict(value)
        current_metadata = writable.get("metadata") if isinstance(writable.get("metadata"), dict) else {}
        current_metadata.update(dict(metadata))
        writable["metadata"] = current_metadata
        payload = self._request_json(f"/records/{encoded_id}/draft", method="PUT", payload=writable)
        if not isinstance(payload, Mapping):
            raise ValueError("Zenodo update-record response must be an object")
        return normalize_deposit(payload)

    def reserve_doi(self, deposition_id: str) -> dict[str, Any]:
        encoded_id = self._record_id(deposition_id)
        self._request_json(f"/records/{encoded_id}/draft/pids/doi", method="POST", payload={})
        return self.get_deposit(deposition_id)

    def get_file(self, deposition_id: str, filename: str) -> dict[str, Any]:
        encoded_id = self._record_id(deposition_id)
        encoded_file = self._file_key(filename)
        payload = self._request_json(f"/records/{encoded_id}/draft/files/{encoded_file}")
        if not isinstance(payload, Mapping):
            raise ValueError("Zenodo file response must be an object")
        return _file_summary(payload)

    def upload_file(self, deposition_id: str, filename: str, content: bytes) -> dict[str, Any]:
        if not isinstance(content, (bytes, bytearray)):
            raise ValueError("content must be bytes")
        encoded_id = self._record_id(deposition_id)
        encoded_file = self._file_key(filename)
        self._request_json(
            f"/records/{encoded_id}/draft/files",
            method="POST",
            payload=[{"key": str(filename).strip()}],
        )
        self._request_json(
            f"/records/{encoded_id}/draft/files/{encoded_file}/content",
            method="PUT",
            raw_data=bytes(content),
            content_type="application/octet-stream",
        )
        self._request_json(f"/records/{encoded_id}/draft/files/{encoded_file}/commit", method="POST", payload={})
        return self.get_file(deposition_id, filename)

    def delete_file(self, deposition_id: str, filename: str) -> dict[str, Any]:
        encoded_id = self._record_id(deposition_id)
        encoded_file = self._file_key(filename)
        self._request_json(f"/records/{encoded_id}/draft/files/{encoded_file}", method="DELETE")
        return {"deleted": True, "deposition_id": str(deposition_id).strip(), "file": str(filename).strip()}

    def delete_draft(self, deposition_id: str) -> dict[str, Any]:
        encoded_id = self._record_id(deposition_id)
        self._request_json(f"/records/{encoded_id}/draft", method="DELETE")
        return {"deleted": True, "deposition_id": str(deposition_id).strip()}

    def edit_published_deposit(self, deposition_id: str) -> dict[str, Any]:
        encoded_id = self._record_id(deposition_id)
        payload = self._request_json(f"/records/{encoded_id}/draft", method="POST", payload={})
        if not isinstance(payload, Mapping):
            raise ValueError("Zenodo edit-draft response must be an object")
        return normalize_deposit(payload)

    def create_new_version(self, deposition_id: str) -> dict[str, Any]:
        encoded_id = self._record_id(deposition_id)
        payload = self._request_json(f"/records/{encoded_id}/versions", method="POST", payload={})
        if not isinstance(payload, Mapping):
            raise ValueError("Zenodo new-version response must be an object")
        return normalize_deposit(payload)

    def import_previous_version_files(self, deposition_id: str) -> dict[str, Any]:
        encoded_id = self._record_id(deposition_id)
        payload = self._request_json(f"/records/{encoded_id}/draft/actions/files-import", method="POST", payload={})
        if not isinstance(payload, Mapping):
            raise ValueError("Zenodo file-import response must be an object")
        return normalize_deposit(payload)

    def publish_deposit(self, deposition_id: str) -> dict[str, Any]:
        """Low-level provider primitive. Agent-facing publication is GitHub-governed elsewhere."""
        encoded_id = self._record_id(deposition_id)
        payload = self._request_json(f"/records/{encoded_id}/draft/actions/publish", method="POST", payload={})
        if not isinstance(payload, Mapping):
            raise ValueError("Zenodo publish response must be an object")
        return normalize_deposit(payload)
