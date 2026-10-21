"""Pipeline seam: the structured-extraction schema (research 02 §4).

One strict structured-output contract: everything optional except
``is_resume`` + ``confidence`` + ``needs_review`` (the pipeline must degrade,
not crash); dates stay strings — normalized in Python post-processing only
when confidently Gregorian, otherwise verbatim (Persian resumes legitimately
carry Jalali dates; those are already in the user's calendar and language).
"""

import pytest
from pydantic import ValidationError

from app.parsing.schema import (
    SCHEMA_VERSION,
    ResumeExtraction,
    build_profile,
    strict_json_schema,
)


def valid_payload(**overrides) -> dict:
    payload = {
        "is_resume": True,
        "confidence": 0.92,
        "needs_review": False,
        "contact": {
            "full_name": "پیمان رضایی",
            "email": "peyman@example.com",
            "phone": "+98 912 345 6789",
            "location": "تهران",
            "links": [{"type": "github", "url": "https://github.com/peyman"}],
        },
        "headline": "Senior Backend Engineer",
        "summary": "مهندس ارشد نرم‌افزار با ۱۰ سال تجربه",
        "work_experience": [
            {
                "title": "Senior Backend Engineer",
                "company": "دیجی‌کالا",
                "location": "تهران",
                "start_date": "2022-03-01",
                "end_date": "2024-08-15",
                "current": False,
                "bullets": ["Led the payments team", "طراحی سامانه پرداخت"],
            }
        ],
        "education": [
            {
                "degree": "کارشناسی",
                "field": "مهندسی کامپیوتر",
                "institution": "دانشگاه تهران",
                "start_date": "1392",
                "end_date": "1396",
            }
        ],
        "skills": ["Python", "PostgreSQL", "Docker"],
        "industries": ["فین‌تک", "e-commerce"],
        "certifications": [{"name": "AWS Solutions Architect", "issuer": None, "date": "2023"}],
        "languages": [{"language": "English", "proficiency": "Fluent"}],
        "document_language": "fa",
        "extraction_notes": [],
    }
    payload.update(overrides)
    return payload


class TestValidation:
    def test_full_payload_validates_verbatim(self):
        extraction = ResumeExtraction.model_validate(valid_payload())
        assert extraction.contact.full_name == "پیمان رضایی"
        assert extraction.work_experience[0].company == "دیجی‌کالا"
        assert extraction.skills == ["Python", "PostgreSQL", "Docker"]

    def test_minimal_payload_validates(self):
        extraction = ResumeExtraction.model_validate(
            {
                "is_resume": True,
                "confidence": 0.5,
                "needs_review": False,
                "contact": {},
                "headline": None,
                "summary": None,
                "work_experience": [],
                "education": [],
                "skills": [],
                "industries": [],
                "certifications": [],
                "languages": [],
                "document_language": None,
                "extraction_notes": [],
            }
        )
        assert extraction.contact.full_name is None

    def test_missing_is_resume_rejected(self):
        payload = valid_payload()
        del payload["is_resume"]
        with pytest.raises(ValidationError):
            ResumeExtraction.model_validate(payload)

    def test_confidence_out_of_range_rejected(self):
        """Out-of-range confidence is exactly what the repair-retry ladder
        catches before any Candidate is created."""
        with pytest.raises(ValidationError):
            ResumeExtraction.model_validate(valid_payload(confidence=1.5))


class TestStrictJsonSchema:
    """The OpenAI wire schema must satisfy strict structured outputs:
    every object declares additionalProperties: false and lists every
    property in required (OpenAI platform docs)."""

    def test_every_object_strict(self):
        schema = strict_json_schema()

        def check(node: dict) -> None:
            if node.get("type") == "object" or "properties" in node:
                assert node.get("additionalProperties") is False
                assert set(node["required"]) == set(node["properties"])
                for child in node["properties"].values():
                    check(child)
            for branch in node.get("anyOf", []):
                check(branch)
            if "items" in node:
                check(node["items"])

        assert schema["type"] == "object"
        check(schema)

    def test_schema_version_constant(self):
        assert SCHEMA_VERSION == 1

    def test_no_unsupported_keywords_anywhere(self):
        schema = strict_json_schema()
        banned = {
            "minimum",
            "maximum",
            "pattern",
            "format",
            "default",
            "title",
            "minItems",
            "maxItems",
        }

        def walk(node: dict) -> None:
            assert not banned & set(node), f"strict mode rejects: {banned & set(node)}"
            for child in node.get("properties", {}).values():
                walk(child)
            for branch in node.get("anyOf", []):
                walk(branch)
            if "items" in node:
                walk(node["items"])

        walk(schema)


class TestDateNormalization:
    """build_profile normalizes confidently-Gregorian dates to ISO prefixes
    and keeps everything else verbatim (spec §7.3: dates as strings)."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2020-01-15", "2020-01-15"),
            ("2020-1-5", "2020-01-05"),
            ("2020/01", "2020-01"),
            ("2020/1", "2020-01"),
            ("2020", "2020"),
            ("Jan 2020", "2020-01"),
            ("March 2020", "2020-03"),
            ("SEPTEMBER 2019", "2019-09"),
            # Persian-calendar dates are already Jalali — verbatim, never
            # reinterpreted as Gregorian
            ("مهر ۱۴۰۱", "مهر ۱۴۰۱"),
            ("۱۳۹۸/۱۰/۰۵", "۱۳۹۸/۱۰/۰۵"),
            ("1398-10-05", "1398-10-05"),
            ("Present", "Present"),
            ("اکنون", "اکنون"),
            ("بهار ۱۳۹۸", "بهار ۱۳۹۸"),
            ("", ""),
            (None, None),
        ],
    )
    def test_date_forms(self, raw, expected):
        payload = valid_payload()
        payload["work_experience"][0]["start_date"] = raw
        profile = build_profile(ResumeExtraction.model_validate(payload))
        assert profile["work_experience"][0]["start_date"] == expected


class TestProfile:
    def test_profile_carries_structured_fields_verbatim(self):
        profile = build_profile(ResumeExtraction.model_validate(valid_payload()))
        assert profile["contact"]["full_name"] == "پیمان رضایی"
        assert profile["skills"] == ["Python", "PostgreSQL", "Docker"]
        assert profile["industries"] == ["فین‌تک", "e-commerce"]
        assert profile["work_experience"][0]["bullets"] == [
            "Led the payments team",
            "طراحی سامانه پرداخت",
        ]
        assert profile["education"][0]["degree"] == "کارشناسی"
        # Routing fields stay out of the HR-editable Profile
        assert "is_resume" not in profile
        assert "confidence" not in profile
        assert "needs_review" not in profile

    def test_profile_dates_normalized(self):
        payload = valid_payload()
        payload["work_experience"][0]["start_date"] = "Jan 2020"
        profile = build_profile(ResumeExtraction.model_validate(payload))
        assert profile["work_experience"][0]["start_date"] == "2020-01"
