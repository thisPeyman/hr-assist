"""Stable stage kinds, independent of editable Persian labels and order."""

from app.models import PipelineStage

DEFAULT_STAGES = (
    ("sourced", "شناسایی‌شده"),
    ("screening", "بررسی اولیه"),
    ("interview", "مصاحبه"),
    ("offer", "پیشنهاد همکاری"),
    ("hired", "استخدام‌شده"),
    ("rejected", "ردشده"),
    ("withdrawn", "انصراف‌داده"),
)
ENDING_KINDS = frozenset({"hired", "rejected", "withdrawn"})


def seed_stages(session, org_id):
    session.add_all(
        [
            PipelineStage(org_id=org_id, kind=kind, name=name, position=position)
            for position, (kind, name) in enumerate(DEFAULT_STAGES)
        ]
    )
