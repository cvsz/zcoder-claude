"""
infrastructure/anthropic_api/files_gateway.py — Files API gateway
AI Model Coder CLI v1.50.0 (Clean Architecture refactor, Phase C, Context #4)

Real HTTP calls to api.anthropic.com's Files API and Messages API
(the latter only for ask_about_file's file-reference call) — zero
print(). Extracted 2026-08-18 from claude_files.py's FilesAPI class.

GA note (2026-08-22): the Files API went GA on Aug 19–20, 2026 — no
`files-api-2025-04-14` beta header on /v1/files or Messages
file-reference calls anymore (see domain/skills_api.py's module
docstring). GA responses add expiration fields (`expires_in_seconds`
on upload results, `expires_at` on file objects) and cursor pagination
(`page` request param, `next_page` in list responses). upload()/list
paths normalize `expires_at` via parse_expires_at(), and
list_files_all() follows GA `next_page` tokens with a legacy
`has_more`/`after_id` fallback for old-format responses. All response
parsing is defensive (.get()) so legacy beta-header-shaped responses
still work.

The local-disk "which files did I upload from this machine" registry
that upload()/delete()/list_local() touch is not this gateway's
concern — it's delegated to infrastructure/local_storage/
files_registry_store.py, same reasoning as every other split in this
project between "talks to Anthropic" and "touches local disk".
"""

import json
import mimetypes
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core.exceptions import ZCoderError
from domain.files import MAX_FILE_SIZE_BYTES, _validate_filename
from infrastructure.anthropic_api.http_client import CircuitBreaker, raise_for_http_error, retry, urlopen_json
from infrastructure.local_storage import files_registry_store as registry

FILES_BASE = "https://api.anthropic.com/v1/files"
MESSAGES_BASE = "https://api.anthropic.com/v1/messages"

_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


def parse_expires_at(file_obj: dict, now: datetime | None = None) -> str | None:
    """Return the file's GA expiration timestamp, or None if it has none.

    GA file objects carry `expires_at` directly; GA *upload* responses may
    instead report a relative `expires_in_seconds`. Legacy beta-format
    responses carry neither. Never raises — unknown shapes yield None."""
    if not isinstance(file_obj, dict):
        return None
    expires_at = file_obj.get("expires_at")
    if expires_at:
        return expires_at
    seconds = file_obj.get("expires_in_seconds")
    if isinstance(seconds, (int, float)) and seconds >= 0:
        base = now or datetime.now(UTC)
        return (base + timedelta(seconds=seconds)).isoformat()
    return None


class FilesAPI:
    """Wrapper around the Anthropic Files API."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-5"):
        self.api_key = api_key
        self.model = model
        registry.ensure_registry_dir()

    def _headers(self, content_type: str = "application/json") -> dict:
        # Files API is GA — no anthropic-beta header (2026-08-22).
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": content_type,
        }

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call_json(self, req: urllib.request.Request, timeout: float) -> dict:
        return urlopen_json(req, timeout=timeout)

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call_bytes(self, req: urllib.request.Request, timeout: float) -> bytes:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.HTTPError, TimeoutError, ConnectionError, OSError) as e:
            raise_for_http_error(e)

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call_nobody(self, req: urllib.request.Request, timeout: float) -> None:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                r.read()
        except (urllib.error.HTTPError, TimeoutError, ConnectionError, OSError) as e:
            raise_for_http_error(e)

    # ── Upload ────────────────────────────────────────────────────────────

    def upload(self, file_path: str) -> dict:
        """Upload a file. Returns {id, filename, size, created_at, ...}"""
        p = Path(file_path)

        name_err = _validate_filename(p.name)
        if name_err:
            raise RuntimeError(f"Upload failed: {name_err}")

        size = p.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            raise RuntimeError(
                f"Upload failed: File too large: {size / (1024*1024):.1f}MB "
                f"(max {MAX_FILE_SIZE_BYTES / (1024*1024):.0f}MB per file)"
            )

        data = p.read_bytes()
        mt = mimetypes.guess_type(str(p))[0] or "application/octet-stream"

        # Multipart/form-data encoding
        boundary = "---AICLIBoundary"

        body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{p.name}"\r\n'
                f"Content-Type: {mt}\r\n\r\n"
            ).encode()
            + data
            + f"\r\n--{boundary}--\r\n".encode()
        )

        headers = self._headers(f"multipart/form-data; boundary={boundary}")
        headers.pop("Content-Type", None)  # let us set it with boundary
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

        req = urllib.request.Request(FILES_BASE, data=body, headers=headers, method="POST")
        try:
            result = self._call_json(req, timeout=60)
        except ZCoderError as e:
            raise RuntimeError(f"Upload failed: {e.message}") from e
        if not isinstance(result, dict) or not result.get("id"):
            raise RuntimeError("Upload failed: API returned no file id")

        # GA upload responses may report a relative expires_in_seconds —
        # normalize it to an absolute expires_at so callers see one shape.
        expires_at = parse_expires_at(result)
        if expires_at and not result.get("expires_at"):
            result["expires_at"] = expires_at

        # Save to local registry
        registry.register_file(result, str(p))
        return result

    # ── List ──────────────────────────────────────────────────────────────

    def list_files(
        self,
        limit: int = 20,
        before_id: str | None = None,
        after_id: str | None = None,
        page: str | None = None,
    ) -> dict:
        """List one page of files.

        GA responses: {"data": [...], "has_more": bool, "first_id": ...,
        "last_id": ..., "next_page": "<cursor>"} — pass `page` to fetch the
        next GA cursor page. Legacy responses keep the has_more/after_id
        shape; both are handled (defensively) by list_files_all()."""
        params = {"limit": str(limit)}
        if before_id:
            params["before_id"] = before_id
        if after_id:
            params["after_id"] = after_id
        if page:
            params["page"] = page
        query = "&".join(f"{k}={v}" for k, v in params.items())
        req = urllib.request.Request(
            f"{FILES_BASE}?{query}",
            headers=self._headers(),
            method="GET",
        )
        try:
            return self._call_json(req, timeout=30)
        except ZCoderError as e:
            raise RuntimeError(f"List failed: {e.message}") from e

    def list_files_all(self, max_items: int | None = None) -> list:
        """Auto-paginate across all pages, bounded by max_items (None = unbounded).

        Follows GA `next_page` cursor pagination when the response carries
        one; falls back to legacy has_more/after_id paging otherwise. All
        fields are read defensively so either response era works."""
        out, after_id, next_page = [], None, None
        while True:
            result = self.list_files(limit=100, after_id=after_id, page=next_page)
            batch = result.get("data") or []
            for item in batch:
                if isinstance(item, dict):
                    expires_at = parse_expires_at(item)
                    if expires_at and not item.get("expires_at"):
                        item["expires_at"] = expires_at
                out.append(item)
            if max_items is not None and len(out) >= max_items:
                return out[:max_items]
            ga_next = result.get("next_page")
            if ga_next:
                next_page, after_id = ga_next, None
                continue
            next_page = None
            last = batch[-1] if batch else None
            last_id = last.get("id") if isinstance(last, dict) else None
            if not result.get("has_more") or not last_id:
                return out
            after_id = last_id

    # ── Retrieve metadata ─────────────────────────────────────────────────

    def get_file(self, file_id: str) -> dict:
        req = urllib.request.Request(
            f"{FILES_BASE}/{file_id}",
            headers=self._headers(),
            method="GET",
        )
        try:
            return self._call_json(req, timeout=30)
        except ZCoderError as e:
            raise RuntimeError(f"Get failed: {e.message}") from e

    # ── Download content ──────────────────────────────────────────────────

    def download(self, file_id: str, output_path: str) -> str:
        # The API returns 400 "Not downloadable" for any file you uploaded
        # yourself — only files created by Skills or the code execution tool
        # have downloadable=true. Check metadata first so the CLI gives a
        # clear, actionable message instead of a bare HTTP error.
        try:
            meta = self.get_file(file_id)
        except RuntimeError:
            meta = None
        if meta is not None and meta.get("downloadable") is False:
            raise RuntimeError(
                "Download failed: this file is not downloadable. Only files "
                "created by Skills or the code execution tool can be "
                "downloaded — files you uploaded yourself never can be."
            )

        req = urllib.request.Request(
            f"{FILES_BASE}/{file_id}/content",
            headers={k: v for k, v in self._headers().items() if k != "Content-Type"},
            method="GET",
        )
        try:
            data = self._call_bytes(req, timeout=60)
        except ZCoderError as e:
            raise RuntimeError(f"Download failed: {e.message}") from e
        Path(output_path).write_bytes(data)
        return output_path

    # ── Delete ────────────────────────────────────────────────────────────

    def delete(self, file_id: str) -> bool:
        req = urllib.request.Request(
            f"{FILES_BASE}/{file_id}",
            headers=self._headers(),
            method="DELETE",
        )
        try:
            self._call_nobody(req, timeout=30)
            registry.unregister_file(file_id)
            return True
        except ZCoderError as e:
            raise RuntimeError(f"Delete failed: {e.message}") from e

    # ── Use file in Messages API ────────────────────────────────────────────

    def ask_about_file(
        self,
        file_id: str,
        prompt: str,
        media_type: str = "application/pdf",
        max_tokens: int = 4096,
        use_code_execution: bool = False,
    ) -> str:
        """Reference an uploaded file in a Messages API call.

        Block type follows the File type -> Content block table in
        platform.claude.com/docs/en/build-with-claude/files:
          - image/*                          -> `image` block
          - use_code_execution=True           -> `container_upload` block
            (datasets/CSV/XLSX/etc. that Claude's sandbox needs to actually
            open and run code against, not just read as text)
          - everything else (PDF, text/plain) -> `document` block
        """
        tools = []

        if media_type.startswith("image/"):
            block = {"type": "image", "source": {"type": "file", "file_id": file_id}}
        elif use_code_execution:
            block = {"type": "container_upload", "file_id": file_id}
            tools = [{"type": "code_execution_20250825", "name": "code_execution"}]
        else:
            block = {
                "type": "document",
                "source": {"type": "file", "file_id": file_id},
                "citations": {"enabled": True},
            }

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [block, {"type": "text", "text": prompt}],
                }
            ],
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            MESSAGES_BASE,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            data = self._call_json(req, timeout=120)
        except ZCoderError as e:
            return f"[API ERROR {getattr(e, 'status_code', '')}] {e.message}"

        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

    # ── Local registry helpers ────────────────────────────────────────────
    # Thin delegation to infrastructure/local_storage/files_registry_store.py
    # kept here too so `FilesAPI(...).list_local()` — the call shape every
    # existing caller (cmd_file_list) already uses — keeps working unchanged.

    def list_local(self) -> dict:
        return registry.list_local()
