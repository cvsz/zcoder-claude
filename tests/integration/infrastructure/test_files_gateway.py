"""tests/integration/infrastructure/test_files_gateway.py

Covers infrastructure/anthropic_api/files_gateway.py's FilesAPI against
fake HTTP responses — no real network. Focus: the Files API GA adoption
(2026-08-22) — no `files-api-2025-04-14` beta header on any request,
GA response shapes (expires_at / expires_in_seconds, next_page cursor
pagination) parsed correctly, and legacy beta-era response shapes still
handled without crashing.
"""

from datetime import UTC

import pytest

import infrastructure.anthropic_api.files_gateway as gw
from infrastructure.anthropic_api.files_gateway import FilesAPI, parse_expires_at
from infrastructure.local_storage import files_registry_store as registry

FILES_API_BETA = "files-api-2025-04-14"


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "LOCAL_REGISTRY", tmp_path / "files_registry.json")


class HttpHarness:
    """Substitutes urlopen_json / raw urlopen; records every outgoing Request."""

    def __init__(self):
        self.requests = []
        self.responses = []

    def install(self, monkeypatch, responses):
        self.responses = list(responses)

        def fake_urlopen_json(req, timeout):
            self.requests.append(req)
            return self.responses.pop(0)

        def fake_urlopen_bytes(req, timeout):
            self.requests.append(req)
            raise gw.ZCoderError("no bytes in these tests")

        monkeypatch.setattr(gw, "urlopen_json", fake_urlopen_json)
        monkeypatch.setattr(
            FilesAPI, "_call_bytes", lambda self, req, timeout: fake_urlopen_bytes(req, timeout)
        )
        monkeypatch.setattr(FilesAPI, "_call_nobody", lambda self, req, timeout: None)


def make_api():
    return FilesAPI(api_key="k", model="claude-sonnet-5")


# ── parse_expires_at ─────────────────────────────────────────────────────


def test_parse_expires_at_ga_object_has_absolute_field():
    obj = {"id": "file_1", "expires_at": "2026-09-21T00:00:00Z"}
    assert parse_expires_at(obj) == "2026-09-21T00:00:00Z"


def test_parse_expires_at_upload_relative_seconds():
    from datetime import datetime

    base = datetime(2026, 8, 22, tzinfo=UTC)
    out = parse_expires_at({"id": "f", "expires_in_seconds": 3600}, now=base)
    assert out == "2026-08-22T01:00:00+00:00"


def test_parse_expires_at_legacy_response_has_nothing():
    assert parse_expires_at({"id": "file_1", "filename": "x.pdf"}) is None


def test_parse_expires_at_defensive_on_garbage():
    assert parse_expires_at({}) is None
    assert parse_expires_at(None) is None
    assert parse_expires_at("nope") is None
    assert parse_expires_at({"expires_in_seconds": "soon"}) is None
    assert parse_expires_at({"expires_in_seconds": -5}) is None


# ── No beta header anywhere (GA) ──────────────────────────────────────────


def test_headers_carry_no_anthropic_beta():
    headers = make_api()._headers()
    assert "anthropic-beta" not in {k.lower() for k in headers}


def test_get_file_request_has_no_beta_header(monkeypatch):
    h = HttpHarness()
    h.install(monkeypatch, responses=[{"id": "file_a", "filename": "a.pdf"}])
    meta = make_api().get_file("file_a")
    assert meta["id"] == "file_a"
    sent = dict(h.requests[0].header_items())
    value = sent.get("Anthropic-beta") or sent.get("anthropic-beta")
    assert not value or FILES_API_BETA not in value


def test_ask_about_file_request_has_no_beta_header(monkeypatch):
    h = HttpHarness()
    h.install(monkeypatch, responses=[{"content": [{"type": "text", "text": "answer"}]}])
    out = make_api().ask_about_file("file_a", "what is this?")
    assert out == "answer"
    sent = dict(h.requests[0].header_items())
    value = sent.get("Anthropic-beta") or sent.get("anthropic-beta")
    assert not value or FILES_API_BETA not in value


# ── Upload parses GA expiration ───────────────────────────────────────────


def _upload(monkeypatch, api_result, tmp_path):
    payload_file = tmp_path / "report.pdf"
    payload_file.write_bytes(b"%PDF-1.4 fake")
    h = HttpHarness()
    h.install(monkeypatch, responses=[api_result])
    return make_api().upload(str(payload_file)), h


def test_upload_ga_shape_parses_expires_in_seconds(monkeypatch, tmp_path):
    result, _ = _upload(
        monkeypatch,
        {"id": "file_ga", "filename": "report.pdf", "size": 13, "expires_in_seconds": 2592000},
        tmp_path,
    )
    assert result["id"] == "file_ga"
    assert isinstance(result["expires_at"], str) and result["expires_at"]
    reg = registry.list_local()
    assert reg["file_ga"]["filename"] == "report.pdf"


def test_upload_legacy_shape_still_works(monkeypatch, tmp_path):
    result, _ = _upload(
        monkeypatch,
        {"id": "file_old", "filename": "report.pdf", "size": 13},
        tmp_path,
    )
    assert result["id"] == "file_old"
    assert "expires_at" not in result


def test_upload_missing_id_raises_cleanly(monkeypatch, tmp_path):
    with pytest.raises(RuntimeError, match="no file id"):
        _upload(monkeypatch, {"error": "boom"}, tmp_path)


def test_upload_too_large_rejected_before_http(monkeypatch, tmp_path):
    big = tmp_path / "big.bin"
    big.write_bytes(b"xxxxx")
    monkeypatch.setattr(gw, "MAX_FILE_SIZE_BYTES", 4)
    with pytest.raises(RuntimeError, match="File too large"):
        make_api().upload(str(big))


# ── List pagination: GA next_page + legacy has_more/after_id ─────────────


def test_list_files_passes_ga_page_param(monkeypatch):
    h = HttpHarness()
    h.install(monkeypatch, responses=[{"data": [], "next_page": None}])
    make_api().list_files(limit=10, page="tok_2")
    assert "page=tok_2" in h.requests[0].full_url


def test_list_files_all_follows_ga_next_page_cursor(monkeypatch):
    h = HttpHarness()
    h.install(
        monkeypatch,
        responses=[
            {
                "data": [
                    {"id": "file_1", "expires_at": "2026-09-01T00:00:00Z"},
                    {"id": "file_2", "expires_in_seconds": 60},
                ],
                "next_page": "tok_2",
                "has_more": True,
            },
            {
                "data": [{"id": "file_3"}],
                "next_page": None,
                "has_more": False,
            },
        ],
    )
    files = make_api().list_files_all()
    assert [f["id"] for f in files] == ["file_1", "file_2", "file_3"]
    # GA relative expiry on page items normalized to absolute expires_at
    assert isinstance(files[1]["expires_at"], str)
    assert "after_id" not in h.requests[0].full_url
    assert "page=tok_2" in h.requests[1].full_url


def test_list_files_all_falls_back_to_legacy_after_id_paging(monkeypatch):
    h = HttpHarness()
    h.install(
        monkeypatch,
        responses=[
            {"data": [{"id": "file_1"}, {"id": "file_2"}], "has_more": True},
            {"data": [{"id": "file_3"}], "has_more": False},
        ],
    )
    files = make_api().list_files_all()
    assert [f["id"] for f in files] == ["file_1", "file_2", "file_3"]
    assert "after_id=file_2" in h.requests[1].full_url
    assert all("page=" not in r.full_url for r in h.requests)


def test_list_files_all_tolerates_malformed_pages(monkeypatch):
    h = HttpHarness()
    h.install(
        monkeypatch,
        responses=[
            {"data": ["not-a-dict", {"id": "file_x"}], "has_more": False},
        ],
    )
    files = make_api().list_files_all()
    assert "not-a-dict" in files
    assert {"id": "file_x"} in files


def test_list_files_all_null_data_page_returns_empty_without_crash(monkeypatch):
    h = HttpHarness()
    h.install(monkeypatch, responses=[{"data": None}])
    assert make_api().list_files_all() == []


def test_download_not_downloadable_precheck_still_works(monkeypatch):
    h = HttpHarness()
    h.install(monkeypatch, responses=[{"id": "file_a", "downloadable": False}])
    with pytest.raises(RuntimeError, match="not downloadable"):
        make_api().download("file_a", "/tmp/nope.pdf")
