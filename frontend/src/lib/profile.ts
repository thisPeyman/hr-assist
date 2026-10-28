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
import type { ParseJobInfo } from "./api"

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

const STATUS_LABELS: Record<ParseJobInfo["status"], string> = {
  pending: "در صف پردازش",
  extracted: "استخراج شد",
  ocr_applied: "استخراج با OCR",
  vision_used: "استخراج با بینایی ماشین",
  needs_review: "نیازمند بازبینی",
  failed: "ناموفق",
  not_a_resume: "رزومه نیست",
}

const REASON_LABELS: Record<string, string> = {
  "api_error:provider_access_denied": "سرویس هوش مصنوعی دسترسی درخواست را رد کرد (403)؛ کلید و مجوز حساب سرویس را بررسی کنید",
  "api_error:provider_authentication_failed": "کلید سرویس هوش مصنوعی پذیرفته نشد (401)؛ تنظیمات کلید را بررسی کنید",
  older_resume_discarded: "نسخهٔ قدیمی‌تر کنار گذاشته شد؛ فایل جدیدتر حفظ شد",
  missing_contact: "راه تماس در رزومه نیست",
  "extraction:legacy_reupload": "تبدیل فایل قدیمی در دسترس نیست؛ PDF یا DOCX بارگذاری کنید",
  "extraction:too_many_pages": "تعداد صفحات بیش از حد مجاز است",
  "extraction:document_too_large": "سند برای پردازش بیش از حد بزرگ است",
  "extraction:vision_unavailable": "پردازش تصویری در دسترس نیست",
  "extraction:image_unreadable": "تصویر قابل خواندن نیست",
  "inbound:malware_detected": "پیوست ناامن تشخیص داده شد",
  "inbound:scanner_unavailable": "بررسی ایمنی پیوست در دسترس نیست",
  "inbound:unsupported_format": "نوع پیوست مجاز نیست؛ PDF یا DOCX بفرستید",
  "inbound:document_too_large": "پیوست بیش از حد بزرگ است",
  "inbound:empty_text": "پیوست خالی است",
  vision_unavailable: "پردازش تصویری در دسترس نیست؛ اتصال سرویس هوش مصنوعی را بررسی کنید",
  "api_error:openai_not_configured": "اتصال هوش مصنوعی تنظیم نشده است؛ مدیر باید کلید OpenAI API را در سرور ثبت کند",
  "api_error:vision_unavailable": "پردازش تصویری در سرویس هوش مصنوعی در دسترس نیست",
  "api_error:credit_balance_exhausted": "اعتبار API هوش مصنوعی تمام شده است؛ مدیر باید اعتبار حساب OpenAI را شارژ کند",
  "api_error:invalid_api_key": "کلید OpenAI API نامعتبر است؛ مدیر باید کلید سرور را بررسی کند",
  existing_profile: "پروفایل موجود حفظ شد؛ اطلاعات جدید را بررسی کنید",
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
export function parseStatusLabel(
  status: ParseJobInfo["status"],
  reason?: string | null
): string {
  const base = STATUS_LABELS[status]
  const detail = reason ? REASON_LABELS[reason]
    ?? (reason.startsWith("api_error:") && reason.includes("403") ? REASON_LABELS["api_error:provider_access_denied"] : undefined)
    ?? (reason.includes("credit_balance_exhausted") ? REASON_LABELS["api_error:credit_balance_exhausted"] : undefined)
    ?? (reason.startsWith("api_error:") ? "ارتباط با سرویس هوش مصنوعی برقرار نشد" : undefined)
    : undefined
  return detail ? `${base} — ${detail}` : base
}
