# 21: Parse hardening — OCR, vision, legacy formats

**What to build:** The long tail of real-world resumes, verified through the `needs_review` queue. Scanned PDF pages detected by text density route to OCR (OCRmyPDF/Tesseract with Persian + English language packs) and re-extract; still-junk pages fall back to the vision route — page images into the LLM call. Legacy `.doc`/RTF convert through config-gated LibreOffice; when the gate is off (or conversion fails) the document lands in the queue with a "re-upload as PDF/DOCX" nudge. Terminal statuses record which route ran (`ocr_applied`, `vision_used`) so re-parse campaigns stay possible. (Spec §7.3 extraction layer.)

**Blocked by:** 20 (`needs_review` queue — the verification surface for these routes).

**Status:** ready-for-agent

- [ ] Scanned PDF → OCR applied → structured Profile extracted; row records `ocr_applied`
- [ ] OCR works on Persian and English scanned text (fas+eng packs)
- [ ] OCR-junk pages → vision route extracts; row records `vision_used`; if that fails too, explicit `needs_review` — never a silent drop
- [ ] `.doc`/RTF converts when the LibreOffice gate is on; otherwise lands in the queue with the re-upload nudge
- [ ] All routes verified end-to-end through the queue UI
