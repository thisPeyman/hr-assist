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

const PERSIAN_ERRORS: Record<string, string> = {
  LOGIN_BAD_CREDENTIALS: "رایانامه یا گذرواژه نادرست است.",
  REGISTER_USER_ALREADY_EXISTS: "این رایانامه قبلاً ثبت شده است.",
  PASSWORD_TOO_SHORT: "گذرواژه باید دست‌کم ۸ نویسه باشد.",
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
