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
  LOGIN_BAD_CREDENTIALS: "رایانامه یا گذرواژه نادرست است.",
  REGISTER_USER_ALREADY_EXISTS: "این رایانامه قبلاً ثبت شده است.",
  PASSWORD_TOO_SHORT: "گذرواژه باید دست‌کم ۸ نویسه باشد.",
  EMPTY_FILE: "فایل خالی است.",
  FILE_TOO_LARGE: "حجم فایل بیش از حد مجاز است (۱۰ مگابایت).",
  NETWORK: "ارتباط با سرور برقرار نشد؛ دوباره تلاش کنید.",
  UNKNOWN: "خطایی رخ داد؛ دوباره تلاش کنید.",
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
  return (await res.json()) as UploadResult
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
