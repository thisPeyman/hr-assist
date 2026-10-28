import { describe, expect, it } from "vitest"

import {
  formatDateRange,
  formatResumeDate,
  parseStatusLabel,
} from "./profile"

describe("provider access errors", () => {
  it("shows denied access for new and previously stored provider errors", () => {
    expect(parseStatusLabel("failed", "api_error:provider_access_denied")).toContain("403")
    expect(parseStatusLabel("failed", "api_error:Error code: 403 - Forbidden")).toContain("مجوز")
  })
})

/*
 * Anchors from the Persian calendar's public record (cross-checked against
 * jalali.test.ts): Nowruz 1403 = 2024-03-20; derived with jalaali-js:
 * 2022-03-01 = 10 Esfand 1400, 2024-08-15 = 25 Mordad 1403.
 */

describe("formatResumeDate", () => {
  it("renders exact Gregorian ISO dates in Jalali", () => {
    expect(formatResumeDate("2022-03-01")).toBe("۱۰ اسفند ۱۴۰۰")
    expect(formatResumeDate("2024-08-15")).toBe("۲۵ مرداد ۱۴۰۳")
  })

  it("renders month precision via its midpoint (display rounding only)", () => {
    // 2022-03-15 = 24 Esfand 1400 → اسفند ۱۴۰۰
    expect(formatResumeDate("2022-03")).toBe("اسفند ۱۴۰۰")
    expect(formatResumeDate("2024-03")).toBe("اسفند ۱۴۰۲")
  })

  it("renders year-only Gregorian years as written, Persian digits", () => {
    // A bare Gregorian year straddles two Jalali years — picking one would
    // invent precision, so the digits convert and the claim stays as-is.
    expect(formatResumeDate("2020")).toBe("۲۰۲۰")
  })

  it("keeps verbatim what is not confidently Gregorian", () => {
    // Persian-calendar dates written in the resume are already Jalali.
    expect(formatResumeDate("۱۳۹۸/۱۰/۰۵")).toBe("۱۳۹۸/۱۰/۰۵")
    expect(formatResumeDate("مهر ۱۴۰۱")).toBe("مهر ۱۴۰۱")
    expect(formatResumeDate("Present")).toBe("Present")
    expect(formatResumeDate("بهار ۱۳۹۸")).toBe("بهار ۱۳۹۸")
  })

  it("returns null for missing dates", () => {
    expect(formatResumeDate(null)).toBeNull()
    expect(formatResumeDate(undefined)).toBeNull()
    expect(formatResumeDate("")).toBeNull()
  })
})

describe("formatDateRange", () => {
  it("composes a Jalali range", () => {
    expect(formatDateRange("2022-03-01", "2024-08-15", false)).toBe(
      "۱۰ اسفند ۱۴۰۰ – ۲۵ مرداد ۱۴۰۳"
    )
  })

  it("marks current roles with «تا کنون» from the flag, not a guess", () => {
    expect(formatDateRange("2022-03", null, true)).toBe("اسفند ۱۴۰۰ – تا کنون")
    expect(formatDateRange("2022-03", "Present", false)).toBe(
      "اسفند ۱۴۰۰ – Present"
    )
  })

  it("handles one-sided ranges", () => {
    expect(formatDateRange("2022-03-01", null, false)).toBe("از ۱۰ اسفند ۱۴۰۰")
    expect(formatDateRange(null, "2024-08-15", false)).toBe("تا ۲۵ مرداد ۱۴۰۳")
  })

  it("returns null when both ends are missing", () => {
    expect(formatDateRange(null, null, false)).toBeNull()
  })
})

describe("parseStatusLabel", () => {
  it("maps machine statuses and reasons to Persian, human words", () => {
    expect(parseStatusLabel("extracted")).toBe("استخراج شد")
    expect(parseStatusLabel("needs_review")).toBe("نیازمند بازبینی")
    expect(parseStatusLabel("failed")).toBe("ناموفق")
    expect(parseStatusLabel("not_a_resume")).toBe("رزومه نیست")
    expect(parseStatusLabel("pending")).toBe("در صف پردازش")
  })

  it("maps needs_review reasons to their own labels", () => {
    expect(parseStatusLabel("needs_review", "low_confidence")).toBe(
      "نیازمند بازبینی — اطمینان مدل پایین است"
    )
    expect(parseStatusLabel("needs_review", "extraction:encrypted")).toBe(
      "نیازمند بازبینی — فایل قفل شده است"
    )
    expect(parseStatusLabel("needs_review", "extraction:scanned_or_empty")).toBe(
      "نیازمند بازبینی — متن قابل استخراج نیست (اسکن؟)"
    )
    expect(parseStatusLabel("needs_review", "extraction:unsupported_format")).toBe(
      "نیازمند بازبینی — قالب پشتیبانی نمی‌شود؛ PDF یا DOCX بارگذاری کنید"
    )
    expect(parseStatusLabel("needs_review", "missing_identity")).toBe(
      "نیازمند بازبینی — نام و راه تماس در رزومه نیست"
    )
    expect(parseStatusLabel("needs_review", "model_flagged")).toBe(
      "نیازمند بازبینی — مدل درخواست بازبینی کرده است"
    )
  })

  it("falls back to the status label for unknown reasons", () => {
    expect(parseStatusLabel("needs_review", "something_new")).toBe(
      "نیازمند بازبینی"
    )
  })
})
