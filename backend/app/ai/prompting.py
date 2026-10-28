"""Reusable versioned audience, grounding, contract, and guardrails skeleton."""

from pathlib import Path


def action_prompt(action: str, version: str = "v1", shared_version: str = "v1") -> str:
    if action not in {"resume_summary"}:
        raise ValueError("unknown AI action")
    folder = Path(__file__).parent / "prompts"
    return (
        (folder / f"shared_{shared_version}.md").read_text(encoding="utf-8")
        + "\n\n"
        + (folder / f"{action}_{version}.md").read_text(encoding="utf-8")
    )
