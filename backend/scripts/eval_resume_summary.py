"""Grounding checks, or explicit live golden evaluation after prompt changes."""

import argparse
import asyncio
import json
from pathlib import Path

from app.parsing.llm import OpenAIResumeExtractor
from app.summaries import generate_summary_data, grounding


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Call the configured cloud model")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    cases = json.loads(
        (Path(__file__).resolve().parents[1] / "tests/golden/resume_summary_v1.json").read_text(
            encoding="utf-8"
        )
    )[: args.limit]
    extractor = OpenAIResumeExtractor()
    for index, case in enumerate(cases):
        data = grounding(case["profile"])
        assert "summary" not in data and "full_name" not in data
        if args.live:
            try:
                result = await generate_summary_data(case["profile"], extractor)
                for label in case["missing"]:
                    assert any(label in gap for gap in result.unclear_or_missing)
                assert not any(
                    phrase in result.text
                    for phrase in ("پیشنهاد استخدام", "بهترین گزینه", "مناسب استخدام")
                )
                print(f"PASS {case['name']} words={len(result.text.split())}", flush=True)
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
        else:
            print(f"PASS grounding {case['name']}")
    print(f"{len(cases)} golden cases checked ({'live' if args.live else 'offline grounding'})")


if __name__ == "__main__":
    asyncio.run(main())
