import type { CandidateProfile } from "./api"

const record = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}
const text = (value: unknown) => typeof value === "string" ? value : null
const strings = (value: unknown) => Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : []
const rows = (value: unknown) => Array.isArray(value) ? value.map(record) : []

/** Invalid partial model output is data: never spread it directly into form state. */
export function reviewProfile(raw: Record<string, unknown> | null): CandidateProfile {
  const data = raw ?? {}
  const contact = record(data.contact)
  return {
    contact: {
      full_name: text(contact.full_name), email: text(contact.email),
      phone: text(contact.phone), location: text(contact.location),
      links: rows(contact.links).map(link => ({ type: text(link.type), url: text(link.url) })),
    },
    headline: text(data.headline), summary: text(data.summary),
    skills: strings(data.skills), industries: strings(data.industries),
    work_experience: rows(data.work_experience).map(row => ({
      title: text(row.title), company: text(row.company), location: text(row.location),
      start_date: text(row.start_date), end_date: text(row.end_date),
      current: row.current === true, bullets: strings(row.bullets),
    })),
    education: rows(data.education).map(row => ({
      degree: text(row.degree), field: text(row.field), institution: text(row.institution),
      start_date: text(row.start_date), end_date: text(row.end_date),
    })),
    certifications: rows(data.certifications).map(row => ({
      name: text(row.name), issuer: text(row.issuer), date: text(row.date),
    })),
    languages: rows(data.languages).map(row => ({
      language: text(row.language), proficiency: text(row.proficiency),
    })),
    document_language: text(data.document_language), extraction_notes: strings(data.extraction_notes),
  }
}
