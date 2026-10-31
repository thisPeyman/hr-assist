import { ApiError } from "./api"

export interface SearchFilter {
  id: string
  field: "years_experience_total" | "skill" | "industry" | "location" | "name" | "headline" | "company" | "stage" | "role_status" | "role_id" | "owner_id"
  op: "eq" | "ne" | "gt" | "gte" | "lt" | "lte" | "contains" | "not_contains"
  value: string
  constraint_softness: number
}
export interface SearchDSL { filters: SearchFilter[]; semantic_query: string }
export interface SearchCandidate {
  id: string; full_name: string; headline: string | null; location: string | null
  years_experience_total: number | null
}
export type SearchEvent =
  | { type: "filters"; dsl: SearchDSL; mode: "hybrid" | "sql" | "lexical"; warnings: string[]; relaxed_filter_id: string | null }
  | { type: "candidate"; candidate: SearchCandidate }
  | { type: "warning"; code: string }
  | { type: "done"; count: number; relax_filter_id: string | null }

export const searchWarning: Record<string, string> = {
  SEARCH_PARSE_FAILED: "برداشت خودکار از پرس‌وجو انجام نشد؛ فقط جست‌وجوی واژه‌ای اجرا شد. شرط‌ها را دستی اضافه کنید.",
  SEARCH_VECTOR_FAILED: "جست‌وجوی معنایی در دسترس نیست؛ شرط‌ها و جست‌وجوی واژه‌ای همچنان اجرا شدند.",
  SEARCH_VECTOR_UNAVAILABLE: "برای بخشی از بانک، نمایهٔ معنایی آماده نیست؛ نتایج واژه‌ای و شرط‌ها همچنان در دسترس‌اند.",
}

/** Consume incrementally: chips are delivered before results/provider latency. */
export async function streamSearch(input: { query: string } | { dsl: SearchDSL; relax?: boolean }, signal: AbortSignal, receive: (event: SearchEvent) => void) {
  const response = await fetch("/api/search", {
    method: "POST", credentials: "same-origin", signal,
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(input),
  })
  if (!response.ok) throw new ApiError(response.status, response.status === 422 ? "INVALID_SEARCH" : "UNKNOWN")
  if (!response.body) throw new ApiError(0, "NETWORK")
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = "", doneEvent = false
  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      let end: number
      while ((end = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, end).trimEnd()
        buffer = buffer.slice(end + 1)
        if (line.startsWith("data: ")) {
          const event = JSON.parse(line.slice(6)) as SearchEvent
          if (event.type === "done") doneEvent = true
          receive(event)
        }
      }
      if (done) break
    }
    if (!doneEvent) throw new ApiError(0, "NETWORK")
  } finally { reader.releaseLock() }
}

export const fieldLabels: Record<SearchFilter["field"], string> = {
  years_experience_total: "سابقهٔ کاری (سال)", skill: "مهارت", industry: "صنعت", location: "محل سکونت",
  name: "نام", headline: "عنوان حرفه‌ای", company: "شرکت", stage: "مرحله", role_status: "وضعیت فرصت",
  role_id: "فرصت شغلی", owner_id: "مسئول درخواست",
}
export const opLabels: Record<SearchFilter["op"], string> = {
  eq: "برابر با", ne: "برابر نباشد با", gt: "بیش از", gte: "دست‌کم", lt: "کمتر از", lte: "حداکثر",
  contains: "شامل", not_contains: "شامل نباشد",
}
export const enumLabels: Record<string, string> = {
  sourced: "یافت‌شده", screening: "غربالگری", interview: "مصاحبه", offer: "پیشنهاد", hired: "استخدام‌شده",
  rejected: "ردشده", withdrawn: "انصراف‌داده", draft: "پیش‌نویس", open: "باز", paused: "متوقف", closed: "بسته",
}
export function filterLabel(filter: SearchFilter) {
  const value = enumLabels[filter.value] ?? (filter.field === "years_experience_total" ? Number(filter.value).toLocaleString("fa-IR") : filter.value)
  return `${fieldLabels[filter.field]} ${opLabels[filter.op]} ${value}`
}
