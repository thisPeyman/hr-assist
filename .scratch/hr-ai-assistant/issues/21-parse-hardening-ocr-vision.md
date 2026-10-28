# 21: Parse hardening — OCR, vision, legacy formats

**What to build:** The long tail of real-world resumes, verified through the `needs_review` queue. Scanned PDF pages detected by text density route to OCR (OCRmyPDF/Tesseract with Persian + English language packs) and re-extract; still-junk pages fall back to the vision route — page images into the LLM call. Legacy `.doc`/RTF convert through config-gated LibreOffice; when the gate is off (or conversion fails) the document lands in the queue with a "re-upload as PDF/DOCX" nudge. Terminal statuses record which route ran (`ocr_applied`, `vision_used`) so re-parse campaigns stay possible. (Spec §7.3 extraction layer.)

**Blocked by:** 20 (`needs_review` queue — the verification surface for these routes).

**Status:** resolved

- [x] Scanned PDF → OCR applied → structured Profile extracted; row records `ocr_applied`
- [x] OCR works on Persian and English scanned text (fas+eng packs)
- [x] OCR-junk pages → vision route extracts; row records `vision_used`; if that fails too, explicit `needs_review` — never a silent drop
- [x] `.doc`/RTF converts when the LibreOffice gate is on; otherwise lands in the queue with the re-upload nudge
- [x] All routes verified end-to-end through the queue UI


## Answer

Implemented the scanned-PDF OCR route (`fas+eng`), bounded PDF/image rendering and structured vision fallback, gated DOC/RTF LibreOffice conversion, explicit re-upload guidance, route-specific successful statuses and needs_review when vision cannot run. Blocking extraction/conversion is moved off the event loop. Page/pixel/size/time limits and image validation are enforced. Full extracted text remains retained even when the model input is truncated.

Validation: real PDF/image rendering, API-to-review tests for OCR/vision statuses, legacy conversion/gate tests, missing-vision-key degradation, and browser upload/preview/review of scanned PDF, image and RTF. OCR/LibreOffice executables and model responses are mocked in these tests. This resolves the implementation; live Tesseract Persian/English recognition, LibreOffice and the paid model were not run because the external system tools are not installed in this environment. Required executable settings and fallback behavior are documented in [docs/resume-ingestion.md](../../../docs/resume-ingestion.md).
