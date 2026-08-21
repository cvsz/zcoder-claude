"""
claude_vision.py — Vision & Multimodal (Images + PDFs) (compatibility shim)
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Real implementation moved 2026-08-16:
  - VisionCoder → infrastructure/anthropic_api/vision_gateway.py
  - cmd_vision, cmd_vision_url, cmd_vision_pdf, cmd_vision_compare,
    cmd_vision_ocr → interfaces/cli/commands/tools_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from infrastructure.anthropic_api.vision_gateway import (
    SUPPORTED_DOC_TYPES,
    SUPPORTED_IMAGE_TYPES,
    VisionCoder,
)
from interfaces.cli.commands.tools_commands import (
    cmd_vision,
    cmd_vision_compare,
    cmd_vision_ocr,
    cmd_vision_pdf,
    cmd_vision_url,
)

__all__ = [
    "VisionCoder",
    "SUPPORTED_IMAGE_TYPES",
    "SUPPORTED_DOC_TYPES",
    "cmd_vision",
    "cmd_vision_url",
    "cmd_vision_pdf",
    "cmd_vision_compare",
    "cmd_vision_ocr",
]
