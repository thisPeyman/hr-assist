"""Durable, authenticated email-in. MIME work happens only in the worker."""

import asyncio
import hashlib
import hmac
import logging
import os
import re
import tempfile
import uuid
from datetime import UTC, datetime
from email import policy
from email.parser import BytesHeaderParser, BytesParser
from html.parser import HTMLParser
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db import get_session
from app.models import InboundMail, Org, ParseJob, ParseJobStatus, ResumeFile
from app.parsing.documents import scan_attachment
from app.parsing.extract_text import ExtractionError, sniff_kind
from app.rls import set_current_org

logger = logging.getLogger(__name__)
inbound_router = APIRouter(prefix="/hooks", tags=["inbound"])


def storage_path(key: str) -> Path:
    root = Path(settings.inbound_storage_dir).resolve()
    target = (root / key).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Invalid storage key")
    return target


def save_raw(org_id: uuid.UUID, raw: bytes) -> str:
    key = f"{org_id}/{hashlib.sha256(raw).hexdigest()}.eml"
    if settings.inbound_s3_bucket:
        import boto3

        client = boto3.client("s3", endpoint_url=settings.inbound_s3_endpoint_url or None)
        client.put_object(
            Bucket=settings.inbound_s3_bucket, Key=key, Body=raw, ContentType="message/rfc822"
        )
        return key
    target = storage_path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return key


def read_raw(key: str) -> bytes:
    if settings.inbound_s3_bucket:
        import boto3

        client = boto3.client("s3", endpoint_url=settings.inbound_s3_endpoint_url or None)
        response = client.get_object(Bucket=settings.inbound_s3_bucket, Key=key)
        try:
            return response["Body"].read(settings.inbound_max_bytes + 1)
        finally:
            response["Body"].close()
    return storage_path(key).read_bytes()


@inbound_router.post("/inbound-mail")
async def receive_mail(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    x_webhook_secret: Annotated[str, Header()] = "",
    x_envelope_to: Annotated[str, Header()] = "",
) -> dict:
    if not settings.inbound_webhook_secret or not settings.inbound_domain:
        raise HTTPException(503, "INBOUND_NOT_CONFIGURED")
    if not hmac.compare_digest(x_webhook_secret, settings.inbound_webhook_secret):
        raise HTTPException(403, "INVALID_WEBHOOK_SECRET")
    recipient = x_envelope_to.strip().lower()
    match = re.fullmatch(r"resumes\+([a-z0-9-]+)@" + re.escape(settings.inbound_domain), recipient)
    if not match:
        raise HTTPException(404, "UNKNOWN_RECIPIENT")
    org = (await session.execute(select(Org).where(Org.slug == match[1]))).scalar_one_or_none()
    if org is None:
        raise HTTPException(404, "UNKNOWN_RECIPIENT")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > settings.inbound_max_bytes:
            raise HTTPException(413, "FILE_TOO_LARGE")
    if not raw:
        raise HTTPException(400, "EMPTY_FILE")
    data = bytes(raw)
    headers = BytesHeaderParser(policy=policy.default).parsebytes(data)
    message_id = str(headers.get("Message-ID") or hashlib.sha256(data).hexdigest()).strip()
    if len(message_id) > 998:
        raise HTTPException(400, "INVALID_MESSAGE_ID")
    await set_current_org(session, org.id)
    # Blob durability precedes the receipt commit and HTTP acknowledgement.
    key = await asyncio.to_thread(save_raw, org.id, data)
    inserted = (
        await session.execute(
            insert(InboundMail)
            .values(
                id=uuid.uuid4(),
                org_id=org.id,
                message_id=message_id,
                recipient=recipient,
                raw_key=key,
                status="pending",
            )
            .on_conflict_do_nothing(index_elements=["message_id", "recipient"])
            .returning(InboundMail.id)
        )
    ).scalar_one_or_none()
    await session.commit()
    return {"accepted": True, "duplicate": inserted is None}


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "blockquote"}:
            self.hidden += 1
        if tag in {"p", "div", "br", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "blockquote"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def strip_quoted_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if re.match(r"^(On .+wrote:|در .+نوشت:|--\s*$|_{5,}|-{5,}Original Message)", line):
            break
        if not line.lstrip().startswith(">"):
            lines.append(line)
    return "\n".join(lines).strip()


def mime_documents(raw: bytes) -> list[tuple[str, bytes]]:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    attachments = []
    for index, part in enumerate(message.walk()):
        if index >= settings.inbound_max_parts:
            raise ExtractionError("too_many_parts")
        if part.is_multipart():
            continue
        if part.get_filename() or part.get_content_disposition() == "attachment":
            attachments.append(
                (str(part.get_filename() or "attachment"), part.get_payload(decode=True) or b"")
            )
    if attachments:
        return attachments
    body = message.get_body(preferencelist=("plain", "html"))
    if body is None:
        raise ExtractionError("empty_mail")
    text = body.get_content()
    if not isinstance(text, str):
        raise ExtractionError("empty_mail")
    if body.get_content_type() == "text/html":
        parser = TextHTML()
        parser.feed(text)
        text = "".join(parser.parts)
    return [("email-body.txt", strip_quoted_text(text).encode("utf-8"))]


async def store_document(
    session: AsyncSession,
    org_id: uuid.UUID,
    filename: str,
    data: bytes,
) -> None:
    reason = None
    try:
        if not data:
            raise ExtractionError("empty_text")
        if len(data) > settings.resume_max_bytes:
            raise ExtractionError("document_too_large")
        kind = sniff_kind(data, filename)
        if Path(filename).suffix.lower() not in {
            ".pdf",
            ".docx",
            ".txt",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".tif",
            ".tiff",
            ".doc",
            ".rtf",
        }:
            raise ExtractionError("unsupported_format")
        await asyncio.to_thread(scan_attachment, data)
    except ExtractionError as exc:
        kind = "blocked"
        reason = f"inbound:{exc.reason}"
    mime = {
        "txt": "text/plain",
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(kind, "application/octet-stream")
    resume_id = (
        await session.execute(
            insert(ResumeFile)
            .values(
                org_id=org_id,
                original_filename=filename[:255],
                mime_type=mime,
                sha256=hashlib.sha256(data).hexdigest(),
                bytes=data,
            )
            .on_conflict_do_nothing(index_elements=["org_id", "sha256"])
            .returning(ResumeFile.id)
        )
    ).scalar_one_or_none()
    if resume_id is not None:
        session.add(
            ParseJob(
                org_id=org_id,
                resume_file_id=resume_id,
                status=ParseJobStatus.NEEDS_REVIEW if reason else ParseJobStatus.PENDING,
                reason=reason,
                finished_at=datetime.now(UTC) if reason else None,
            )
        )


async def drain_inbound_mail(session_factory: async_sessionmaker) -> int:
    processed = 0
    attempted: set[uuid.UUID] = set()
    while True:
        async with session_factory() as session:
            row = (
                await session.execute(
                    select(InboundMail.id, InboundMail.org_id)
                    .where(InboundMail.status == "pending", InboundMail.id.not_in(attempted))
                    .order_by(InboundMail.created_at, InboundMail.id)
                    .limit(1)
                )
            ).first()
            if row is None:
                return processed
            mail_id, org_id = row
            await set_current_org(session, org_id)
            mail = (
                await session.execute(
                    select(InboundMail)
                    .where(InboundMail.id == mail_id)
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()
            if mail is None:
                attempted.add(mail_id)
                continue
            if mail.status != "pending":
                continue
            try:
                raw = await asyncio.to_thread(read_raw, mail.raw_key)
                if len(raw) > settings.inbound_max_bytes:
                    raise ExtractionError("document_too_large")
                documents = await asyncio.to_thread(mime_documents, raw)
                for filename, data in documents:
                    await store_document(session, org_id, filename, data)
                mail.status = "processed"
            except Exception as exc:
                logger.warning("Inbound processing failed: %s", type(exc).__name__)
                mail.status = "failed"
                mail.reason = (
                    exc.reason if isinstance(exc, ExtractionError) else "mail_processing_failed"
                )
            await session.commit()
            processed += 1
