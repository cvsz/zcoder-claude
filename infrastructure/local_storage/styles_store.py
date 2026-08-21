"""infrastructure/local_storage/styles_store.py — Output Styles local-disk persistence
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Local-disk I/O for discovering custom output styles from project and user
directories. No network calls, no print().
"""

from pathlib import Path

from domain.output_styles import PROJECT_STYLES_DIR, USER_STYLES_DIR, _parse_style_file


def discover_custom_styles() -> dict:
    out = {}
    for d in (USER_STYLES_DIR, PROJECT_STYLES_DIR):
        if d.exists():
            for f in d.glob("*.md"):
                style = _parse_style_file(f)
                if style:
                    out[style["name"]] = style
    return out


def load_plugin_output_styles(plugin_dirs: list) -> list:
    out = []
    for plug_dir in plugin_dirs:
        styles_dir = Path(plug_dir) / "output-styles"
        if not styles_dir.exists():
            continue
        for f in styles_dir.glob("*.md"):
            style = _parse_style_file(f)
            if style:
                style["plugin"] = Path(plug_dir).name
                out.append(style)
    return out
