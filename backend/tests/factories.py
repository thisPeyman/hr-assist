"""Shared payload factories for parsing tests."""



def extraction_payload(**overrides) -> dict:
    """A complete, valid ResumeExtractionData wire payload (mixed Persian/English,
    verbatim values) that tests can override per-case."""
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
                "start_date": "2014",
                "end_date": "2018",
            }
        ],
        "skills": ["Python", "PostgreSQL", "Docker"],
        "industries": ["فین‌تک", "e-commerce"],
        "certifications": [
            {"name": "AWS Solutions Architect", "issuer": None, "date": "2023"}
        ],
        "languages": [{"language": "English", "proficiency": "Fluent"}],
        "document_language": "fa",
        "extraction_notes": [],
    }
    payload.update(overrides)
    return payload


def invalid_payload() -> dict:
    """A payload that fails pydantic validation (confidence out of range)."""
    return extraction_payload(confidence=1.5)
