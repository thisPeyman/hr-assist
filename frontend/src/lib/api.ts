export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string) {
    super(code)
    this.status = status
    this.code = code
  }
}

export interface Me {
  id: string
  email: string
  org: { id: string; name: string; slug: string }
  role: "admin" | "member"
}

export interface SignupInput {
  email: string
  password: string
  org_name: string
}

/** One parse job — every submitted document ends in an explicit status. */
export interface ParseJobInfo {
  id: string
  status:
    | "pending"
    | "extracted"
    | "ocr_applied"
    | "vision_used"
    | "needs_review"
    | "failed"
    | "not_a_resume"
  reason: string | null
  attempts: number
  model: string | null
  prompt_version: string | null
  schema_version: number | null
}

export interface CandidateSummary {
  id: string
  full_name: string
  headline: string | null
  email: string | null
  created_at: string
  new_resume_received?: boolean
}

export interface ProfileLink {
  type: string | null
  url: string | null
}

export interface ProfileContact {
  full_name: string | null
  email: string | null
  phone: string | null
  location: string | null
  links: ProfileLink[] | null
}

export interface ProfileWorkExperience {
  title: string | null
  company: string | null
  location: string | null
  start_date: string | null
  end_date: string | null
  current: boolean
  bullets: string[] | null
}

export interface ProfileEducation {
  degree: string | null
  field: string | null
  institution: string | null
  start_date: string | null
  end_date: string | null
}

export interface ProfileCertification {
  name: string | null
  issuer: string | null
  date: string | null
}

export interface ProfileLanguage {
  language: string | null
  proficiency: string | null
}

/** The structured, HR-editable Profile of a Candidate's latest resume. */
export interface CandidateProfile {
  contact: ProfileContact
  headline: string | null
  summary: string | null
  work_experience: ProfileWorkExperience[]
  education: ProfileEducation[]
  skills: string[]
  industries: string[]
  certifications: ProfileCertification[]
  languages: ProfileLanguage[]
  document_language: string | null
  extraction_notes: string[]
}

export interface CandidateResume {
  id: string
  filename: string
  parse_status: ParseJobInfo["status"]
  parse_reason: string | null
  uploaded_at: string
}

export interface CandidateDetail extends CandidateSummary {
  phone: string | null
  location: string | null
  profile: CandidateProfile | null
  resume: CandidateResume | null
}

export interface UploadResult {
  duplicate: boolean
  job: ParseJobInfo | null
  candidate: CandidateSummary | null
}

const PERSIAN_ERRORS: Record<string, string> = {
  CANDIDATE_NOT_FOUND: "کاندیدا پیدا نشد؛ ممکن است ادغام یا حذف شده باشد.",
  INVALID_PROFILE: "ساختار اطلاعات پروفایل معتبر نیست؛ فیلدها را بررسی کنید.",
  PROFILE_CHANGED_REFRESH: "این فیلد پس از پیشنهاد تغییر کرده است؛ صفحه را تازه کنید.",
  CHANGE_ALREADY_RESOLVED: "این اختلاف قبلاً تعیین تکلیف شده است.",
  RESUME_VERSION_MISSING: "برای تولید خلاصه، ابتدا رزومهٔ این فرد را بارگذاری کنید.",
  RESUME_NOT_FOUND: "رزومه پیدا نشد؛ فهرست را تازه کنید.",
  DOCUMENT_QUARANTINED: "این سند تا تکمیل بررسی ایمنی قابل پذیرش یا دریافت نیست.",
  DOCUMENT_ALREADY_RESOLVED: "این سند قبلاً تعیین تکلیف شده است؛ فهرست را تازه کنید.",
  PROFILE_NAME_REQUIRED: "نام کاندیدا را وارد کنید.",
  RESUME_SUPERSEDED: "نسخهٔ جدیدتری از این رزومه دریافت شده است؛ پروندهٔ فرد را باز کنید.",
  LOGIN_BAD_CREDENTIALS: "رایانامه یا گذرواژه نادرست است.",
  REGISTER_USER_ALREADY_EXISTS: "این رایانامه قبلاً ثبت شده است.",
  PASSWORD_TOO_SHORT: "گذرواژه باید دست‌کم ۸ نویسه باشد.",
  EMPTY_FILE: "فایل خالی است.",
  FILE_TOO_LARGE: "حجم فایل بیش از حد مجاز است (۱۰ مگابایت).",
  NETWORK: "ارتباط با سرور برقرار نشد؛ دوباره تلاش کنید.",
  UNKNOWN: "خطایی رخ داد؛ دوباره تلاش کنید.",
}

export interface CandidateWorkspace {
  id: string
  full_name: string
  profile: Record<string, unknown> | null
  resume_id: string | null
  resume_version: string | null
  new_resume_received: boolean
  summary: { status: string; content: { text: string; unclear_or_missing: string[]; grounded_fields: string[] } | null; error: string | null; generated_at: string | null; model: string | null; prompt_version: string } | null
  changes: { id: string; field_path: string; old_value: unknown; new_value: unknown; resume_version: string }[]
  duplicates: { id: string; full_name: string; email: string | null; phone: string | null; similarity: number }[]
  activity: { id: number; event_type: string; data: Record<string, unknown>; created_at: string }[]
  notes: { id: string; body: string; created_at: string }[]
  applications: { id: string; role_title: string; stage: string }[]
}

export async function fetchCandidateWorkspace(id: string, signal?: AbortSignal): Promise<CandidateWorkspace> {
  const res = await request(`/api/candidates/${id}/workspace`, { signal })
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function saveCandidateProfile(id: string, profile: CandidateProfile): Promise<void> {
  const res = await request(`/api/candidates/${id}/profile`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile }) })
  if (!res.ok) await throwApiError(res)
}

export async function candidateAction(id: string, action: string, body?: unknown): Promise<Record<string, unknown>> {
  const res = await request(`/api/candidates/${id}/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) })
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export interface ResumeItem {
  id: string
  filename: string
  created_at: string
  status: ParseJobInfo["status"]
  reason: string | null
  latest_job_id: string | null
  candidate_id: string | null
  candidate_name: string | null
  candidate_email: string | null
}

export interface ResumeDetail extends ResumeItem {
  profile: Record<string, unknown> | null
}

export interface ResumeEdit {
  full_name: string
  email: string | null
  phone: string | null
  location: string | null
  headline: string | null
  summary: string | null
  skills: string[]
  expected_values?: Record<string, unknown>
}

export async function fetchResumes(search = "", before?: string, signal?: AbortSignal): Promise<{ items: ResumeItem[]; next_cursor: string | null }> {
  const params = new URLSearchParams({ search, limit: "20" })
  if (before) params.set("before", before)
  const res = await request(`/api/resumes?${params}`, { signal })
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function fetchResume(id: string, signal?: AbortSignal): Promise<ResumeDetail> {
  const res = await request(`/api/resumes/${id}`, { signal })
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function updateResume(id: string, changes: ResumeEdit): Promise<ResumeDetail> {
  const res = await request(`/api/resumes/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes),
  })
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function deleteResume(id: string): Promise<void> {
  const res = await request(`/api/resumes/${id}`, { method: "DELETE" })
  if (!res.ok) await throwApiError(res)
}

/** Map an API error to a Persian, user-facing message. */
export function persianError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code in PERSIAN_ERRORS) return PERSIAN_ERRORS[error.code]!
    if (error.code.startsWith("PASSWORD_")) return PERSIAN_ERRORS.PASSWORD_TOO_SHORT!
  }
  return PERSIAN_ERRORS.UNKNOWN!
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(path, { credentials: "same-origin", ...init })
  } catch {
    throw new ApiError(0, "NETWORK")
  }
}

/** Always throws: turn a non-2xx response into an ApiError. */
async function throwApiError(res: Response): Promise<never> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    const detail = body.detail
    // Prefer the machine-readable reason (e.g. PASSWORD_TOO_SHORT) over the
    // generic code (REGISTER_INVALID_PASSWORD) when one is present.
    if (typeof detail === "string") throw new ApiError(res.status, detail)
    if (detail && typeof detail === "object" && "code" in detail) {
      const obj = detail as Record<string, unknown>
      const reason = typeof obj.reason === "string" ? obj.reason : undefined
      const code = typeof obj.code === "string" ? obj.code : undefined
      if (reason && reason in PERSIAN_ERRORS) throw new ApiError(res.status, reason)
      if (code) throw new ApiError(res.status, code)
    }
  } catch (e) {
    if (e instanceof ApiError) throw e
  }
  throw new ApiError(res.status, "UNKNOWN")
}

export async function fetchMe(): Promise<Me | null> {
  const res = await request("/api/me")
  if (res.status === 401) return null
  if (!res.ok) await throwApiError(res)
  return (await res.json()) as Me
}

export async function login(email: string, password: string): Promise<void> {
  const res = await request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }),
  })
  if (!res.ok) await throwApiError(res)
}

export async function signup(input: SignupInput): Promise<Me> {
  const res = await request("/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  })
  if (!res.ok) await throwApiError(res)
  return (await res.json()) as Me
}

export async function logout(): Promise<void> {
  const res = await request("/auth/logout", { method: "POST" })
  if (!res.ok && res.status !== 401) await throwApiError(res)
}

/** Upload a resume — the sync path; the outcome carries the terminal status. */
export async function uploadResume(file: File): Promise<UploadResult> {
  const body = new FormData()
  body.append("file", file)
  let res: Response
  try {
    res = await fetch("/api/candidates/upload", {
      method: "POST",
      credentials: "same-origin",
      body,
    })
  } catch {
    throw new ApiError(0, "NETWORK")
  }
  if (!res.ok) await throwApiError(res)
  const result = (await res.json()) as UploadResult
  window.dispatchEvent(new Event("ingestion-changed"))
  return result
}

export async function fetchCandidates(): Promise<CandidateSummary[]> {
  const res = await request("/api/candidates")
  if (!res.ok) await throwApiError(res)
  const body = (await res.json()) as { items: CandidateSummary[] }
  return body.items
}

export async function fetchCandidate(id: string): Promise<CandidateDetail> {
  const res = await request(`/api/candidates/${id}`)
  if (res.status === 404) throw new ApiError(404, "CANDIDATE_NOT_FOUND")
  if (!res.ok) await throwApiError(res)
  return (await res.json()) as CandidateDetail
}

export interface IngestionSettings {
  email_address: string | null
  email_enabled: boolean
  review_count: number
}

export interface ReviewItem {
  id: string
  filename: string
  status: ParseJobInfo["status"]
  reason: string | null
  created_at: string
  candidate_id: string | null
  blocked: boolean
}

export interface ReviewDetail extends ReviewItem {
  raw_text: string | null
  raw_json: Record<string, unknown> | null
  candidate_profile: Record<string, unknown> | null
}

export interface ReviewList {
  items: ReviewItem[]
  mail_failures: { id: string; reason: string | null; created_at: string }[]
}

export async function fetchIngestionSettings(): Promise<IngestionSettings> {
  const res = await request("/api/ingestion/settings")
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function fetchReview(view: "review" | "all" = "review"): Promise<ReviewList> {
  const res = await request(`/api/review?view=${view}`)
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function fetchReviewDetail(id: string): Promise<ReviewDetail> {
  const res = await request(`/api/review/${id}`)
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function resolveReview(
  id: string, action: "accept" | "not_a_resume" | "failed" | "rescan", profile?: CandidateProfile,
  edits?: { edited_fields: string[]; expected_values: Record<string, unknown> },
): Promise<{ candidate_id: string | null }> {
  const res = await request(`/api/review/${id}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, ...edits, extraction: profile ? {
      ...profile, is_resume: true, confidence: 1, needs_review: false,
    } : null }),
  })
  if (!res.ok) await throwApiError(res)
  return res.json()
}
