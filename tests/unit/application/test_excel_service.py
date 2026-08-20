"""tests/unit/application/test_excel_service.py

Covers application/excel_service.py — the use-case layer for the Excel
chat bounded context, extracted 2026-08-18 (Phase C, Context #4). Fake
Coder/SkillsApiClient/FilesAPI substituted in — no real network. Mirrors
tests/unit/application/test_pptx_service.py's structure one-for-one.
"""

from infrastructure.local_storage.excel_workbook_store import ExcelSession
import application.excel_service as service


# ── resolve_output_path ──────────────────────────────────────────────────

def test_resolve_output_path_explicit_wins():
    assert service.resolve_output_path("in.xlsx", "out.xlsx") == "out.xlsx"


def test_resolve_output_path_derives_from_input():
    assert service.resolve_output_path("notes.csv", None) == "notes.xlsx"


def test_resolve_output_path_defaults_when_neither_given():
    assert service.resolve_output_path(None, None) == "excel_session.xlsx"


# ── run_turn ──────────────────────────────────────────────────────────────

class FakeCoder:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def generate(self, prompt, system=None, history=None):
        self.calls.append((prompt, system, list(history) if history is not None else None))
        return self.reply


def test_run_turn_applies_code_block_and_saves(tmp_path):
    coder = FakeCoder('```python\nsheets["Sheet1"]["x"] = [1, 2]\n```')
    session = ExcelSession()
    history = []
    out = str(tmp_path / "wb.xlsx")

    result = service.run_turn(coder, session, "add a column", history, out)

    assert result["code_block_found"] is True
    assert result["applied"] is True
    assert "Sheet1: 2x1" in result["shapes"]
    assert (tmp_path / "wb.xlsx").exists()
    assert history == [
        {"role": "user", "content": "add a column"},
        {"role": "assistant", "content": coder.reply},
    ]


def test_run_turn_no_code_block_returns_reply_text():
    coder = FakeCoder("There are 0 rows.")
    session = ExcelSession()
    history = []

    result = service.run_turn(coder, session, "how many rows?", history, "out.xlsx")

    assert result["code_block_found"] is False
    assert result["reply"] == "There are 0 rows."
    assert result["applied"] is None


def test_run_turn_denylisted_code_does_not_save(tmp_path):
    coder = FakeCoder('```python\nimport os\nsheets["Sheet1"]["x"] = [1]\n```')
    session = ExcelSession()
    history = []
    out = str(tmp_path / "wb.xlsx")

    result = service.run_turn(coder, session, "do something sneaky", history, out)

    assert result["code_block_found"] is True
    assert result["applied"] is False
    assert "blocked" in result["message"]
    assert not (tmp_path / "wb.xlsx").exists()


# ── upload_input_workbook ────────────────────────────────────────────────

class FakeFilesAPI:
    def __init__(self, upload_result=None, raise_exc=None):
        self.upload_result = upload_result
        self.raise_exc = raise_exc
        self.downloaded = None

    def upload(self, path):
        if self.raise_exc:
            raise self.raise_exc
        return self.upload_result

    def download(self, file_id, output_path):
        self.downloaded = (file_id, output_path)


def test_upload_input_workbook_returns_file_id():
    fa = FakeFilesAPI(upload_result={"id": "file_abc"})
    assert service.upload_input_workbook(fa, "wb.xlsx") == "file_abc"


def test_upload_input_workbook_raises_on_api_error():
    fa = FakeFilesAPI(raise_exc=RuntimeError("boom"))
    try:
        service.upload_input_workbook(fa, "wb.xlsx")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "Could not upload" in str(e)
        assert "boom" in str(e)


def test_upload_input_workbook_raises_when_no_file_id_returned():
    fa = FakeFilesAPI(upload_result={"filename": "wb.xlsx"})  # no "id" key
    try:
        service.upload_input_workbook(fa, "wb.xlsx")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "returned no file id" in str(e)


# ── run_native_turn ──────────────────────────────────────────────────────

class FakeSkillsClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def call_with_skills_turn(self, messages, skills, container_id, has_file_uploads):
        self.calls.append((list(messages), skills, container_id, has_file_uploads))
        return self.response


def test_run_native_turn_success_with_text():
    client = FakeSkillsClient({
        "container": {"id": "cont_1"},
        "content": [{"type": "text", "text": "Done!"}],
    })
    fa = FakeFilesAPI()
    messages = []

    result = service.run_native_turn(client, fa, messages, "clean this data",
                                      pending_file_ids=[], container_id=None,
                                      output_path="out.xlsx")

    assert result["error"] is None
    assert result["text"] == "Done!"
    assert result["container_id"] == "cont_1"
    assert result["downloaded"] is False
    assert len(messages) == 2


def test_run_native_turn_downloads_generated_file(monkeypatch):
    client = FakeSkillsClient({
        "container": {"id": "cont_1"},
        "content": [{"type": "text", "text": "Here's your workbook."}],
    })
    fa = FakeFilesAPI()

    import claude_skills_api
    monkeypatch.setattr(claude_skills_api, "extract_output_file_ids", lambda data: ["file_out"])

    result = service.run_native_turn(client, fa, [], "build a model",
                                      pending_file_ids=[], container_id=None,
                                      output_path="out.xlsx")
    assert result["downloaded"] is True
    assert fa.downloaded == ("file_out", "out.xlsx")


def test_run_native_turn_error_pops_user_message():
    client = FakeSkillsClient({"error": "container failed"})
    fa = FakeFilesAPI()
    messages = []

    result = service.run_native_turn(client, fa, messages, "build a model",
                                      pending_file_ids=[], container_id=None,
                                      output_path="out.xlsx")

    assert result["error"] == "container failed"
    assert messages == []
