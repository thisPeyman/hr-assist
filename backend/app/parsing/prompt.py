"""Versioned prompts (spec §4.5): prompt text lives in files, versions in
the filename; nothing prompt-shaped is load-bearing in code."""

from functools import lru_cache
from pathlib import Path

PROMPT_NAME = "resume_extract"
PROMPT_VERSION = "v1"

_FILE = Path(__file__).parent / "prompts" / f"{PROMPT_NAME}_{PROMPT_VERSION}.md"


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    return _FILE.read_text(encoding="utf-8")
