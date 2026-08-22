"""
interfaces/cli/commands/files_commands.py — CLI presentation for the
Files API bounded context
AI Model Coder CLI v1.50.0 (Clean Architecture refactor, Phase C, Context #4)

Only print() lives here — all real work delegated to
application/files_service.py. Extracted 2026-08-18 from claude_files.py's
cmd_file_upload, cmd_file_list, cmd_file_delete, cmd_file_ask,
cmd_file_download.
"""

from application import files_service as service

__all__ = [
    "cmd_file_upload",
    "cmd_file_list",
    "cmd_file_delete",
    "cmd_file_ask",
    "cmd_file_download",
]


def cmd_file_upload(file_path: str, api_key: str, model: str):
    print(f"\033[94mℹ Uploading {file_path}…\033[0m")
    result = service.upload_file(file_path, api_key, model)
    print(f"\033[92m✓ Uploaded: {result['id']}\033[0m")
    print(f"  Filename: {result.get('filename', '')}")
    print(f"  Size:     {result.get('size', 0):,} bytes")
    print(f"  Created:  {result.get('created_at', '')}")
    print(f"\n  Use with: ai-coder --file-ask {result['id']} \"your question\"")
    return result["id"]


def cmd_file_list(api_key: str, model: str, max_items: int | None = None):
    files, local = service.list_all_files(api_key, model, max_items=max_items)
    if not files:
        print("No files uploaded yet.")
        return
    print(f"\n{'ID':<28}{'FILENAME':<30}{'SIZE':>10}  CREATED")
    print("─" * 80)
    for f in files:
        fid = f["id"]
        local_fn = local.get(fid, {}).get("local_path", "")
        fname = f.get("filename", local_fn)[:29]
        size = f"{f.get('size', 0):,}"
        created = str(f.get("created_at", ""))[:10]
        print(f"{fid:<28}{fname:<30}{size:>10}  {created}")
    print(f"\n{len(files)} file(s)")


def cmd_file_delete(file_id: str, api_key: str):
    service.delete_file(file_id, api_key)
    print(f"\033[92m✓ File {file_id} deleted.\033[0m")


def cmd_file_ask(file_id: str, prompt: str, api_key: str, model: str, media_type: str = "application/pdf"):
    print(f"\033[94mℹ Asking about file {file_id}…\033[0m\n")
    result = service.ask_about_file(file_id, prompt, api_key, model, media_type=media_type)
    print(result)
    return result


def cmd_file_download(file_id: str, output_path: str, api_key: str):
    path = service.download_file(file_id, output_path, api_key)
    print(f"\033[92m✓ Downloaded to {path}\033[0m")
