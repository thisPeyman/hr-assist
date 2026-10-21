import { toJalaali as convert } from "jalaali-js"

/*
 * Jalali (Shamsi) rendering for the presentation layer.
 *
 * Storage and APIs stay Gregorian ISO 8601 (spec §3); this module is the only
 * place dates become Jalali + Persian digits for users.
 */

export const JALALI_MONTHS = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
] as const

const PERSIAN_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"] as const

export type JalaliDate = { jy: number; jm: number; jd: number }

export function toPersianDigits(value: number | string): string {
  return String(value).replace(/\d/g, (d) => PERSIAN_DIGITS[Number(d)]!)
}

/** Convert the date part of a Gregorian ISO string to Jalali. */
export function toJalali(iso: string): JalaliDate {
  const datePart = iso.split("T")[0]!
  const [gy, gm, gd] = datePart.split("-").map(Number)
  const { jy, jm, jd } = convert(gy!, gm!, gd!)
  return { jy, jm, jd }
}

/** e.g. "2026-10-21" → "۲۹ مهر ۱۴۰۵" */
export function formatJalali(iso: string): string {
  const { jy, jm, jd } = toJalali(iso)
  return `${toPersianDigits(jd)} ${JALALI_MONTHS[jm - 1]} ${toPersianDigits(jy)}`
}
