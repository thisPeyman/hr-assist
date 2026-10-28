"""Bounded local document routes. All external commands use private temp dirs."""

import io
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.parsing.extract_text import ExtractionError, extract_text, sniff_kind


@dataclass
class PreparedDocument:
    text: str = ""
    truncated: bool = False
    route: str = "extracted"
    images: list[bytes] = field(default_factory=list)
    raw_text: str | None = None


def run_command(arguments: list[str]) -> None:
    try:
        result = subprocess.run(
            arguments,
            capture_output=True,
            timeout=settings.document_command_timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExtractionError("document_tool_unavailable") from exc
    if result.returncode:
        raise ExtractionError("document_conversion_failed")


def scan_attachment(data: bytes) -> None:
    """Fail closed: unavailable scanner never permits an inbound attachment."""
    with tempfile.TemporaryDirectory(prefix="hr-scan-") as temporary:
        source = Path(temporary) / "attachment"
        source.write_bytes(data)
        try:
            result = subprocess.run(
                [settings.clamav_command, "--no-summary", str(source)],
                capture_output=True,
                timeout=settings.document_command_timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ExtractionError("scanner_unavailable") from exc
        if result.returncode == 1:
            raise ExtractionError("malware_detected")
        if result.returncode != 0:
            raise ExtractionError("scanner_unavailable")


def render_images(data: bytes, *, pdf: bool) -> list[bytes]:
    from PIL import Image

    result: list[bytes] = []
    try:
        if pdf:
            import pypdfium2 as pdfium

            with pdfium.PdfDocument(data) as document:
                if len(document) > settings.resume_max_pages:
                    raise ExtractionError("too_many_pages")
                for index in range(len(document)):
                    page = document[index]
                    try:
                        if page.get_width() * page.get_height() * 4 > 20_000_000:
                            raise ExtractionError("document_too_large")
                        bitmap = page.render(scale=2)
                        try:
                            output = io.BytesIO()
                            bitmap.to_pil().save(output, format="PNG")
                            result.append(output.getvalue())
                        finally:
                            bitmap.close()
                    finally:
                        page.close()
        else:
            with Image.open(io.BytesIO(data)) as image:
                if image.width * image.height > 20_000_000:
                    raise ExtractionError("document_too_large")
                if getattr(image, "n_frames", 1) > settings.resume_max_pages:
                    raise ExtractionError("too_many_pages")
                for index in range(getattr(image, "n_frames", 1)):
                    image.seek(index)
                    frame = image.convert("RGB")
                    frame.thumbnail((2400, 2400))
                    output = io.BytesIO()
                    frame.save(output, format="PNG")
                    result.append(output.getvalue())
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError("image_unreadable") from exc
    if not result or sum(map(len, result)) > settings.resume_max_bytes * 2:
        raise ExtractionError("document_too_large")
    return result


def prepare_document(data: bytes, filename: str) -> PreparedDocument:
    kind = sniff_kind(data, filename)
    if kind in {"doc", "rtf"}:
        if not settings.legacy_conversion_enabled:
            raise ExtractionError("legacy_reupload")
        with tempfile.TemporaryDirectory(prefix="hr-office-") as temporary:
            root = Path(temporary)
            source = root / f"resume.{kind}"
            source.write_bytes(data)
            try:
                run_command(
                    [
                        settings.libreoffice_command,
                        f"-env:UserInstallation={(root / 'profile').as_uri()}",
                        "--headless",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        str(root),
                        str(source),
                    ]
                )
                data = (root / "resume.pdf").read_bytes()
            except (ExtractionError, OSError) as exc:
                raise ExtractionError("legacy_reupload") from exc
            return prepare_document(data, "resume.pdf")
    if kind == "image":
        if not settings.vision_enabled:
            raise ExtractionError("vision_unavailable")
        return PreparedDocument(route="vision_used", images=render_images(data, pdf=False))
    try:
        extracted = extract_text(data, filename)
        return PreparedDocument(extracted.text, extracted.truncated, raw_text=extracted.raw_text)
    except ExtractionError as exc:
        if kind != "pdf" or exc.reason != "scanned_or_empty":
            raise
    if settings.ocr_enabled:
        with tempfile.TemporaryDirectory(prefix="hr-ocr-") as temporary:
            source, output = Path(temporary) / "source.pdf", Path(temporary) / "ocr.pdf"
            source.write_bytes(data)
            try:
                run_command(
                    [
                        settings.ocr_command,
                        "--skip-text",
                        "--language",
                        "fas+eng",
                        "--output-type",
                        "pdf",
                        str(source),
                        str(output),
                    ]
                )
                extracted = extract_text(output.read_bytes(), "ocr.pdf")
                return PreparedDocument(
                    extracted.text, extracted.truncated, "ocr_applied", raw_text=extracted.raw_text
                )
            except ExtractionError, OSError:
                pass  # unusable OCR falls through to bounded image extraction
    if settings.vision_enabled:
        return PreparedDocument(route="vision_used", images=render_images(data, pdf=True))
    raise ExtractionError("scanned_or_empty")
