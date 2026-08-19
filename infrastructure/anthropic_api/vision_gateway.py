"""
infrastructure/anthropic_api/vision_gateway.py — Vision & Multimodal
(images + PDFs) live Anthropic API adapter
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Extracted 2026-08-16 from claude_vision.py. VisionCoder itself was
already print-free — only cmd_* had print(), now in
interfaces/cli/commands/tools_commands.py.
"""

import base64
import mimetypes
from pathlib import Path
from typing import List, Optional, Tuple

import anthropic

SUPPORTED_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
SUPPORTED_DOC_TYPES   = {".pdf"}


def encode_file(path: str) -> Tuple[str, str]:
    """Return (base64_data, media_type)."""
    p    = Path(path)
    ext  = p.suffix.lower()
    data = base64.standard_b64encode(p.read_bytes()).decode("utf-8")
    mt   = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if ext in SUPPORTED_IMAGE_TYPES:
        mt = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}[ext]
    elif ext == ".pdf":
        mt = "application/pdf"
    return data, mt


def _image_block(path: Optional[str] = None, url: Optional[str] = None) -> dict:
    if url:
        return {"type": "image", "source": {"type": "url", "url": url}}
    data, mt = encode_file(path)
    return {"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}}


def _doc_block(path: str) -> dict:
    data, _ = encode_file(path)
    return {"type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": data},
            "citations": {"enabled": True}}


class VisionCoder:
    """Claude client for image and PDF analysis."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-5", max_tokens: int = 4096):
        self.client     = anthropic.Anthropic(api_key=api_key)
        self.model      = model
        self.max_tokens = max_tokens

    def analyse_image(self, path: Optional[str] = None, url: Optional[str] = None,
                       prompt: str = "Describe this image in detail.",
                       system: Optional[str] = None) -> str:
        content = [_image_block(path=path, url=url), {"type": "text", "text": prompt}]
        return self._call(content, system)

    def analyse_pdf(self, path: str, prompt: str = "Summarise this document.",
                     system: Optional[str] = None) -> str:
        content = [_doc_block(path), {"type": "text", "text": prompt}]
        return self._call(content, system)

    def code_from_screenshot(self, path: Optional[str] = None, url: Optional[str] = None,
                              language: str = "auto") -> str:
        prompt = (
            f"This is a screenshot of a UI or code. "
            f"Generate {'the ' + language + ' ' if language != 'auto' else ''}code "
            f"that recreates or implements what you see. "
            f"Provide complete, runnable code with comments."
        )
        content = [_image_block(path=path, url=url), {"type": "text", "text": prompt}]
        system  = "You are an expert developer. Write clean, production-ready code."
        return self._call(content, system)

    def compare_images(self, paths: List[str], prompt: str = "") -> str:
        content = [_image_block(path=p) for p in paths]
        content.append({"type": "text",
                         "text": prompt or "Compare these images. Describe the differences and similarities."})
        return self._call(content)

    def extract_text(self, path: Optional[str] = None, url: Optional[str] = None) -> str:
        """OCR – extract all text from an image."""
        prompt  = "Extract and transcribe ALL text visible in this image. Preserve formatting."
        content = [_image_block(path=path, url=url), {"type": "text", "text": prompt}]
        return self._call(content)

    def _call(self, content: list, system: Optional[str] = None) -> str:
        kwargs = dict(model=self.model, max_tokens=self.max_tokens,
                      messages=[{"role": "user", "content": content}])
        if system:
            kwargs["system"] = system
        resp = self.client.messages.create(**kwargs)
        return resp.content[0].text
