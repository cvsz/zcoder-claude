"""
domain/artifacts.py — Artifacts subsystem domain layer
AI Model Coder CLI v1.42.0 (Clean Architecture refactor)

Pure data: the artifact type registry and its suggested file extensions.
No I/O of any kind. Extracted 2026-08-22 from artifacts.py's non-I/O
tables when that module was split into the 4-layer architecture.
"""

ARTIFACT_TYPES = {
    "code": "Source code in any language",
    "docs": "Documentation, README, API reference",
    "tests": "Test suites and test cases",
    "schema": "Database schemas, JSON schemas, Pydantic models",
    "config": "Config files, YAML/TOML/JSON settings",
    "diagram": "Architecture / flow diagrams (Mermaid or ASCII)",
    "report": "Analysis, audit, or performance reports",
    "plan": "Project plans, task breakdowns, roadmaps",
    "changelog": "CHANGELOG entries and release notes",
    "prompt": "Reusable system prompts and few-shot examples",
    "script": "Shell / build / deployment scripts",
    "template": "Code or document templates",
}

# Extensions to suggest for each type
TYPE_EXTENSIONS = {
    "code": ".py",
    "docs": ".md",
    "tests": ".py",
    "schema": ".json",
    "config": ".yaml",
    "diagram": ".md",
    "report": ".md",
    "plan": ".md",
    "changelog": ".md",
    "prompt": ".txt",
    "script": ".sh",
    "template": ".txt",
}
