"""Send synthetic MIME or replay a backup .eml to the authenticated local webhook.

Run from backend/: uv run python -m scripts.mock_inbound --recipient ADDRESS
No SMTP connection, real recipient email, or real domain is required.
"""

import argparse
import uuid
from email.message import EmailMessage
from pathlib import Path

import httpx

from app.config import settings


def synthetic_mail(message_id: str) -> bytes:
    message = EmailMessage()
    message["From"] = "local-hr@example.test"
    message["To"] = "local-testing@example.test"
    message["Message-ID"] = message_id
    message["Subject"] = "رزومهٔ آزمایشی فارسی و انگلیسی"
    message.set_content("رزومه در پیوست است.\n-- \nامضای آزمایشی")
    resume = (
        "علی رضایی\nBackend Engineer\nali@example.test\n"
        "مهارت‌ها: Python, PostgreSQL\nصنعت: نرم‌افزار\n"
        "شرکت آزمایشی، مهندس نرم‌افزار، 2020-01 تا 2024-01\n"
        "تحصیلات: کارشناسی مهندسی کامپیوتر\n"
    )
    message.add_attachment(
        resume.encode("utf-8"), maintype="text", subtype="plain", filename="رزومه-آزمایشی.txt"
    )
    return message.as_bytes()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipient", required=True, help="Org email-in address shown in settings")
    parser.add_argument("--url", default="http://127.0.0.1:8000/hooks/inbound-mail")
    parser.add_argument("--file", type=Path, help="Optional backup .eml to replay")
    parser.add_argument(
        "--save", type=Path, help="Save synthetic MIME for duplicate-delivery tests"
    )
    parser.add_argument("--message-id", default=None)
    args = parser.parse_args()
    if not settings.inbound_webhook_secret:
        parser.error("Set HR_INBOUND_WEBHOOK_SECRET locally before sending")
    raw = (
        args.file.read_bytes()
        if args.file
        else synthetic_mail(args.message_id or f"<{uuid.uuid4()}@local.example.test>")
    )
    if args.save:
        args.save.write_bytes(raw)
    response = httpx.post(
        args.url,
        content=raw,
        timeout=30,
        headers={
            "Content-Type": "application/octet-stream",
            "X-Webhook-Secret": settings.inbound_webhook_secret,
            "X-Envelope-To": args.recipient,
        },
    )
    print(f"HTTP {response.status_code}: {response.text}")
    response.raise_for_status()


if __name__ == "__main__":
    main()
