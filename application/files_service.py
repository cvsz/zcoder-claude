"""
application/files_service.py — use-case layer for the Files API
bounded context
AI Model Coder CLI v1.50.0 (Clean Architecture refactor, Phase C, Context #4)

Orchestrates infrastructure/anthropic_api/files_gateway.py — no I/O of
its own beyond what FilesAPI already does, no print(). Extracted
2026-08-18 alongside claude_files.py's split; the original cmd_*
bodies were already thin (mostly one FilesAPI call + prints), so this
layer's ops are thin too — same shape as Phase A's Admin/Compliance
ops for equally thin original call sites.
"""


from infrastructure.anthropic_api.files_gateway import FilesAPI


def upload_file(file_path: str, api_key: str, model: str) -> dict:
    fa = FilesAPI(api_key=api_key, model=model)
    return fa.upload(file_path)


def list_all_files(api_key: str, model: str, max_items: int | None = None) -> tuple:
    """Returns (files, local_registry) — files from the API, local_registry
    is the local-disk cache of filenames/local paths for files this
    machine uploaded (used to fill in a filename when the API's own
    metadata doesn't have one)."""
    fa = FilesAPI(api_key=api_key, model=model)
    files = fa.list_files_all(max_items=max_items)
    local = fa.list_local()
    return files, local


def delete_file(file_id: str, api_key: str) -> None:
    fa = FilesAPI(api_key=api_key)
    fa.delete(file_id)


def ask_about_file(
    file_id: str, prompt: str, api_key: str, model: str, media_type: str = "application/pdf"
) -> str:
    fa = FilesAPI(api_key=api_key, model=model)
    return fa.ask_about_file(file_id, prompt, media_type=media_type)


def download_file(file_id: str, output_path: str, api_key: str) -> str:
    fa = FilesAPI(api_key=api_key)
    return fa.download(file_id, output_path)
