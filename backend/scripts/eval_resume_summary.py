"""Deterministic contract checks; neither mode certifies semantic acceptance."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings
from app.parsing.llm import OpenAIResumeExtractor
from app.summaries import PROMPT_VERSION, generate_summary_data, grounding
from app.summary_facts import missing_labels, project_facts


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Call the configured cloud model")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--output", type=Path, help="Save results/prose for subsequent human semantic review"
    )
    args = parser.parse_args()
    cases = json.loads(
        (Path(__file__).resolve().parents[1] / "tests/golden/resume_summary_v1.json").read_text(
            encoding="utf-8"
        )
    )[: args.limit]
    extractor = OpenAIResumeExtractor()
    results = []
    for index, case in enumerate(cases):
        data = grounding(case["profile"])
        assert "summary" not in data and "full_name" not in data
        assert "email" not in (data.get("contact") or {})
        facts = project_facts(data)
        gaps = missing_labels(data, facts)
        for key, values in case.get("expected", {}).items():
            assert [item["value"] for item in facts[key]["items"]] == values, (case["name"], key)
            assert facts[key]["state"] == ("supplied" if values else "unknown")
        for label in case["missing"]:
            assert any(label in gap for gap in gaps), (case["name"], label)
        report = {
            "case": case["name"],
            "mode": "live_automatic_contract" if args.live else "offline_deterministic_only",
            "prompt_version": PROMPT_VERSION,
            "run_at": datetime.now(UTC).isoformat(),
            "as_of_date": data["current_date"],
            "model": settings.resume_summary_model or settings.resume_extract_model,
            "provider": settings.resume_ai_provider,
            "deterministic_checks": "passed",
            "category_states": {key: value["state"] for key, value in facts.items()},
            "expected_categories_checked": list(case.get("expected", {})),
            "semantic_acceptance": "NOT_EVALUATED_REQUIRES_HUMAN_REVIEW",
        }
        if args.live:
            try:
                result = await generate_summary_data(case["profile"], extractor)
                for label in case["missing"]:
                    assert any(label in gap for gap in result.unclear_or_missing)
                assert not any(
                    phrase in result.text
                    for phrase in ("پیشنهاد استخدام", "بهترین گزینه", "مناسب استخدام")
                )
                report.update(
                    text=result.text,
                    words=len(result.text.split()),
                    facts=result.facts,
                    evidence=result.evidence,
                    unclear_or_missing=result.unclear_or_missing,
                )
            except Exception as exc:
                cause = exc.__cause__ or exc
                print(
                    f"FAIL {case['name']} type={type(exc).__name__} "
                    f"http={getattr(cause, 'status_code', None)}",
                    flush=True,
                )
                raise SystemExit(1) from None
            if index + 1 < len(cases):
                await asyncio.sleep(8)
        results.append(report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    if args.output:
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"{len(cases)} automatic contract checks only; Persian factual coverage, non-invention, "
        "unknown-vs-negative and safety semantics remain UNVERIFIED."
    )


if __name__ == "__main__":
    asyncio.run(main())
