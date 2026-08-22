"""tests/unit/application/test_pptx_service.py

Covers application/pptx_service.py — the use-case layer for the
PowerPoint chat bounded context, extracted 2026-08-18 (Phase C,
Context #4). Fake Coder/SkillsApiClient/FilesAPI substituted in — no
real network, no real python-pptx dependency beyond the real
PptxSession (in-memory only, no save() called in these tests).
"""

import application.pptx_service as service
from infrastructure.local_storage.pptx_deck_store import PptxSession

# ── resolve_output_path ──────────────────────────────────────────────────


def test_resolve_output_path_explicit_wins():
    assert service.resolve_output_path("in.pptx", "out.pptx") == "out.pptx"


def test_resolve_output_path_derives_from_input():
    assert service.resolve_output_path("notes.txt", None) == "notes.pptx"


def test_resolve_output_path_defaults_when_neither_given():
    assert service.resolve_output_path(None, None) == "pptx_session.pptx"


# ── run_turn ──────────────────────────────────────────────────────────────


class FakeCoder:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def generate(self, prompt, system=None, history=None):
        self.calls.append((prompt, system, list(history) if history is not None else None))
        return self.reply


def test_run_turn_applies_code_block_and_saves(tmp_path):
    coder = FakeCoder('```python\nadd_slide("Intro")\n```')
    session = PptxSession()
    history = []
    out = str(tmp_path / "deck.pptx")

    result = service.run_turn(coder, session, "add an intro slide", history, out)

    assert result["code_block_found"] is True
    assert result["applied"] is True
    assert result["num_slides"] == 1
    assert len(session.slides) == 1
    assert (tmp_path / "deck.pptx").exists()
    assert history == [
        {"role": "user", "content": "add an intro slide"},
        {"role": "assistant", "content": coder.reply},
    ]


def test_run_turn_no_code_block_returns_reply_text():
    coder = FakeCoder("You have 0 slides.")
    session = PptxSession()
    history = []

    result = service.run_turn(coder, session, "how many slides?", history, "out.pptx")

    assert result["code_block_found"] is False
    assert result["reply"] == "You have 0 slides."
    assert result["applied"] is None


def test_run_turn_denylisted_code_does_not_save(tmp_path, monkeypatch):
    coder = FakeCoder('```python\nimport os\nadd_slide("x")\n```')
    session = PptxSession()
    history = []
    out = str(tmp_path / "deck.pptx")

    result = service.run_turn(coder, session, "do something sneaky", history, out)

    assert result["code_block_found"] is True
    assert result["applied"] is False
    assert "blocked" in result["message"]
    assert not (tmp_path / "deck.pptx").exists()


# ── upload_input_deck ────────────────────────────────────────────────────


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


def test_upload_input_deck_returns_file_id():
    fa = FakeFilesAPI(upload_result={"id": "file_abc"})
    assert service.upload_input_deck(fa, "deck.pptx") == "file_abc"


def test_upload_input_deck_raises_on_api_error():
    fa = FakeFilesAPI(raise_exc=RuntimeError("boom"))
    try:
        service.upload_input_deck(fa, "deck.pptx")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as e:
        assert "Could not upload" in str(e)
        assert "boom" in str(e)


def test_upload_input_deck_raises_when_no_file_id_returned():
    fa = FakeFilesAPI(upload_result={"filename": "deck.pptx"})  # no "id" key
    try:
        service.upload_input_deck(fa, "deck.pptx")
        raise AssertionError("expected RuntimeError")
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
    client = FakeSkillsClient(
        {
            "container": {"id": "cont_1"},
            "content": [{"type": "text", "text": "Done!"}],
        }
    )
    fa = FakeFilesAPI()
    messages = []

    result = service.run_native_turn(
        client, fa, messages, "make a deck", pending_file_ids=[], container_id=None, output_path="out.pptx"
    )

    assert result["error"] is None
    assert result["text"] == "Done!"
    assert result["container_id"] == "cont_1"
    assert result["downloaded"] is False
    # user turn + assistant turn both recorded
    assert len(messages) == 2


def test_run_native_turn_downloads_generated_file(monkeypatch):
    client = FakeSkillsClient(
        {
            "container": {"id": "cont_1"},
            "content": [{"type": "text", "text": "Here's your deck."}],
        }
    )
    fa = FakeFilesAPI()

    # extract_output_file_ids is imported inside the function from
    # domain.skills_api, not as a service-module global — patch it there;
    # the local `from domain.skills_api import ...` re-resolves the
    # attribute at call time, so this takes effect.
    from domain import skills_api

    monkeypatch.setattr(skills_api, "extract_output_file_ids", lambda data: ["file_out"])

    result = service.run_native_turn(
        client, fa, [], "make a deck", pending_file_ids=[], container_id=None, output_path="out.pptx"
    )
    assert result["downloaded"] is True
    assert fa.downloaded == ("file_out", "out.pptx")


def test_run_native_turn_error_pops_user_message():
    client = FakeSkillsClient({"error": "container failed"})
    fa = FakeFilesAPI()
    messages = []

    result = service.run_native_turn(
        client, fa, messages, "make a deck", pending_file_ids=[], container_id=None, output_path="out.pptx"
    )

    assert result["error"] == "container failed"
    # user message appended then popped back off on error
    assert messages == []
