"""tests/unit/application/test_files_service.py

Covers application/files_service.py — the use-case layer for the Files
API bounded context, extracted 2026-08-18 (Phase C, Context #4). Fake
FilesAPI substituted in — no real network.
"""

import application.files_service as service


class FakeFilesAPI:
    instances = []

    def __init__(self, api_key, model="claude-sonnet-5"):
        self.api_key = api_key
        self.model = model
        self.deleted = None
        self.downloaded = None
        FakeFilesAPI.instances.append(self)

    def upload(self, file_path):
        self.uploaded_path = file_path
        return {"id": "file_123", "filename": "x.pdf"}

    def list_files_all(self, max_items=None):
        self.max_items = max_items
        return [{"id": "file_1"}, {"id": "file_2"}]

    def list_local(self):
        return {"file_1": {"local_path": "/tmp/x.pdf"}}

    def delete(self, file_id):
        self.deleted = file_id
        return True

    def ask_about_file(self, file_id, prompt, media_type="application/pdf"):
        self.asked = (file_id, prompt, media_type)
        return "the answer"

    def download(self, file_id, output_path):
        self.downloaded = (file_id, output_path)
        return output_path


def setup_function(_):
    FakeFilesAPI.instances.clear()


def test_upload_file_delegates(monkeypatch):
    monkeypatch.setattr(service, "FilesAPI", FakeFilesAPI)
    result = service.upload_file("/tmp/report.pdf", "key", "claude-sonnet-5")
    assert result["id"] == "file_123"
    assert FakeFilesAPI.instances[0].uploaded_path == "/tmp/report.pdf"


def test_list_all_files_returns_files_and_local(monkeypatch):
    monkeypatch.setattr(service, "FilesAPI", FakeFilesAPI)
    files, local = service.list_all_files("key", "claude-sonnet-5", max_items=5)
    assert len(files) == 2
    assert local["file_1"]["local_path"] == "/tmp/x.pdf"
    assert FakeFilesAPI.instances[0].max_items == 5


def test_delete_file_delegates(monkeypatch):
    monkeypatch.setattr(service, "FilesAPI", FakeFilesAPI)
    service.delete_file("file_123", "key")
    assert FakeFilesAPI.instances[0].deleted == "file_123"


def test_ask_about_file_forwards_media_type(monkeypatch):
    monkeypatch.setattr(service, "FilesAPI", FakeFilesAPI)
    result = service.ask_about_file(
        "file_123", "what is this?", "key", "claude-sonnet-5", media_type="image/png"
    )
    assert result == "the answer"
    assert FakeFilesAPI.instances[0].asked == ("file_123", "what is this?", "image/png")


def test_download_file_delegates(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "FilesAPI", FakeFilesAPI)
    out = str(tmp_path / "out.pdf")
    result = service.download_file("file_123", out, "key")
    assert result == out
    assert FakeFilesAPI.instances[0].downloaded == ("file_123", out)
