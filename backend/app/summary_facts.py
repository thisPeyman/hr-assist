"""Deterministic projections, not model-authored claims or a live Profile view.

Evidence paths address the professional grounding snapshot passed to the model.
Unknown means insufficient supplied data, never a negative fact about a person.
"""

LABELS = {
    "headline": "عنوان حرفه‌ای",
    "current_titles": "عنوان شغلی فعلی",
    "current_employers": "کارفرمای فعلی",
    "experience_years": "سابقهٔ کل",
    "skills": "مهارت‌ها",
    "employers": "کارفرماها",
    "industries": "صنایع",
    "education": "تحصیلات",
    "languages": "زبان‌ها",
    "residence": "محل زندگی",
    "locations": "مکان‌ها",
}


def meaningful(value):
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(meaningful(v) for v in value.values())
    if isinstance(value, list):
        return any(meaningful(v) for v in value)
    return value is not None and value is not False


def project_facts(data):
    facts = {key: {"state": "unknown", "items": []} for key in LABELS}

    def add(category, value, *paths):
        if meaningful(value):
            facts[category]["items"].append({"value": value, "evidence": list(paths)})

    add("headline", data.get("headline"), "headline")
    add("residence", data.get("location"), "location")
    add("locations", data.get("location"), "location")
    for key in ("skills", "industries"):
        for index, value in enumerate(data.get(key) or []):
            add(key, value, f"{key}.{index}")
    for key, fields in (
        ("education", ("degree", "field", "institution", "start_date", "end_date")),
        ("languages", ("language", "proficiency")),
    ):
        for index, record in enumerate(data.get(key) or []):
            # A proficiency without a named language cannot identify a language.
            if key == "languages" and not meaningful(record.get("language")):
                continue
            value = {field: record[field] for field in fields if meaningful(record.get(field))}
            add(key, value, *(f"{key}.{index}.{field}" for field in value))
    jobs = data.get("work_experience") or []
    incomplete = {"current_titles": False, "current_employers": False}
    for index, job in enumerate(jobs):
        prefix = f"work_experience.{index}"
        add("employers", job.get("company"), f"{prefix}.company")
        add("locations", job.get("location"), f"{prefix}.location")
        if job.get("current") is True:
            for key, field in (("current_titles", "title"), ("current_employers", "company")):
                add(key, job.get(field), f"{prefix}.{field}", f"{prefix}.current")
                incomplete[key] |= not meaningful(job.get(field))
    if data.get("experience_years") is not None:
        paths = []
        for index, job in enumerate(jobs):
            paths.append(f"work_experience.{index}.start_date")
            if job.get("current") and not job.get("end_date"):
                paths.extend([f"work_experience.{index}.current", "current_date"])
            else:
                paths.append(f"work_experience.{index}.end_date")
        add("experience_years", data["experience_years"], *paths)
    for key, category in facts.items():
        if category["items"]:
            category["state"] = "partial" if incomplete.get(key) else "supplied"
    return facts


def evidence_snapshot(data, facts):
    """Retain only cited professional values, including dates behind derived years.

    Paths stay useful after Profile edits. Never persist contact identifiers or
    whole work bullets merely to support an evidence pointer.
    """
    evidence = {}
    for category in facts.values():
        for item in category["items"]:
            for path in item["evidence"]:
                value = data
                for part in path.split("."):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                evidence[path] = value
    return evidence


def missing_labels(data, facts):
    gaps = [
        f"{LABELS[key]} در رزومه ذکر نشده است یا اطلاعات آن کامل نیست"
        for key, category in facts.items()
        if category["state"] != "supplied" and key != "experience_years"
    ]
    if not meaningful(data.get("work_experience")):
        gaps.append("سوابق کاری در رزومه ذکر نشده است")
    if facts["experience_years"]["state"] == "unknown":
        gaps.append("سابقهٔ کل از تاریخ‌های رزومه به‌طور قطعی قابل محاسبه نیست")
    return gaps
