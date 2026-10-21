import { describe, expect, it } from "vitest"

import { formatJalali, toJalali, toPersianDigits } from "./jalali"

// Anchors from the Persian calendar's public record, not from our code:
// - 22 Bahman 1357 (Iranian Revolution) = 1979-02-11
// - Nowruz 1403 = 2024-03-20, Nowruz 1405 = 2026-03-21
// - Khordad has 31 days; its last day in 1404 = 2025-06-21
describe("toJalali", () => {
  it("converts the revolution date", () => {
    expect(toJalali("1979-02-11")).toEqual({ jy: 1357, jm: 11, jd: 22 })
  })

  it("converts Nowruz 1403", () => {
    expect(toJalali("2024-03-20")).toEqual({ jy: 1403, jm: 1, jd: 1 })
  })

  it("converts Nowruz 1405", () => {
    expect(toJalali("2026-03-21")).toEqual({ jy: 1405, jm: 1, jd: 1 })
  })

  it("handles the day before Nowruz (leap-year Esfand)", () => {
    expect(toJalali("2025-03-20")).toEqual({ jy: 1403, jm: 12, jd: 30 })
  })

  it("handles the last day of a 31-day spring month", () => {
    expect(toJalali("2025-06-21")).toEqual({ jy: 1404, jm: 3, jd: 31 })
  })

  it("converts a mid-autumn date", () => {
    expect(toJalali("2026-10-21")).toEqual({ jy: 1405, jm: 7, jd: 29 })
  })

  it("accepts a full ISO timestamp, not just dates", () => {
    expect(toJalali("2026-10-21T14:05:00Z")).toEqual({ jy: 1405, jm: 7, jd: 29 })
  })
})

describe("formatJalali", () => {
  it("renders Persian month name and Persian digits", () => {
    expect(formatJalali("2026-10-21")).toBe("۲۹ مهر ۱۴۰۵")
  })

  it("renders Nowruz", () => {
    expect(formatJalali("2026-03-21")).toBe("۱ فروردین ۱۴۰۵")
  })
})

describe("toPersianDigits", () => {
  it("converts Western digits to Persian digits", () => {
    expect(toPersianDigits(1405)).toBe("۱۴۰۵")
    expect(toPersianDigits("29")).toBe("۲۹")
  })
})
