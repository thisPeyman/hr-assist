/*
 * Profile display helpers — the presentation layer's only date/label logic.
 *
 * Storage and APIs stay Gregorian ISO (spec §3); values from the resume stay
 * verbatim in the resume's own language. These helpers decide, per value,
 * what becomes Jalali + Persian digits and what is shown exactly as the
 * resume wrote it (Persian-calendar dates are already Jalali — reinterpreting
 * them would corrupt work history).
 */

import { formatJalali, toPersianDigits } from "./jalali"

// Backend normalization emits: YYYY | YYYY-MM | YYYY-MM-DD — confidently
// Gregorian. Anything else is a verbatim fragment from the resume.
const ISO_DATE = /^\d{4}(-\d{2})?(-\d{2})?$/

/** A resume date → user-facing string, or null when absent. */
export function formatResumeDate(
  value: string | null | undefined
): string | null {
  if (!value) return null

  const match = ISO_DATE.exec(value)
  if (!match) return value // verbatim: «مهر ۱۴۰۱», "Present", …

  if (match[1] === undefined) {
    // Year-only: a Gregorian year straddles two Jalali years; converting
    // would invent precision. Persian digits, claim untouched.
    return toPersianDigits(value)
  }
  if (match[2] === undefined) {
    // Month precision: display-round via the month's midpoint.
    const [year, month] = value.split("-").map(Number)
    const j = formatJalali(`${year}-${String(month).padStart(2, "0")}-15`)
    return j.slice(j.indexOf(" ") + 1) // drop the day, keep «ماه سال»
  }
  return formatJalali(value) // exact day — exact Jalali
}

/** A work-history/education date range, «… – …»; null when both ends missing. */
export function formatDateRange(
  start: string | null | undefined,
  end: string | null | undefined,
  current: boolean
): string | null {
  const from = formatResumeDate(start)
  let to: string | null = null
  if (current && !end) {
    to = "تا کنون" // from the structured flag — never guessed from text
  } else if (end) {
    to = formatResumeDate(end)
  }
  if (from && to) return `${from} – ${to}`
  if (from) return `از ${from}`
  if (to) return `تا ${to}`
  return null
}

const STATUS_LABELS: Record<string, string> = {
  pending: "در صف پردازش",
  extracted: "استخراج شد",
  ocr_applied: "استخراج با OCR",
  vision_used: "استخراج با بینایی ماشین",
  needs_review: "نیازمند بازبینی",
  failed: "ناموفق",
  not_a_resume: "رزومه نیست",
}

const REASON_LABELS: Record<string, string> = {
  low_confidence: "اطمینان مدل پایین است",
  model_flagged: "مدل درخواست بازبینی کرده است",
  validation_failed: "خروجی مدل نامعتبر بود",
  missing_identity: "نام و راه تماس در رزومه نیست",
  missing_name: "نام در رزومه نیست",
  "extraction:encrypted": "فایل قفل شده است",
  "extraction:corrupt_pdf": "فایل PDF قابل خواندن نیست",
  "extraction:scanned_or_empty": "متن قابل استخراج نیست (اسکن؟)",
  "extraction:empty_text": "متن فایل خالی است",
  "extraction:docx_empty": "متن فایل Word خالی است",
  "extraction:unsupported_format": "قالب پشتیبانی نمی‌شود؛ PDF یا DOCX بارگذاری کنید",
}

/** Parse status (+ optional reason) as a Persian, human label. */
export function parseStatusLabel(status: string, reason?: string | null): string {
  const base = STATUS_LABELS[status] ?? status
  const detail = reason ? REASON_LABELS[reason] : undefined
  return detail ? `${base} — ${detail}` : base
}
