import { useCallback, useEffect, useRef, useState, type DragEvent } from "react"
import { Link } from "react-router"
import { FileUpIcon, LoaderCircleIcon, UsersIcon } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { AppShell } from "@/components/shell"
import {
  fetchCandidates,
  persianError,
  uploadResume,
  type CandidateSummary,
} from "@/lib/api"
import { formatJalali, toPersianDigits } from "@/lib/jalali"
import { parseStatusLabel } from "@/lib/profile"

const ACCEPT = ".pdf,.docx,.txt"

/** The upload tray: drag-and-drop or pick — one resume, sub-minute parse. */
function UploadTray({ onUploaded }: { onUploaded: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [retryFile, setRetryFile] = useState<File | null>(null)
  const [retryAvailable, setRetryAvailable] = useState(false)
  const [message, setMessage] = useState<{
    tone: "info" | "warn" | "error"
    text: string
    link?: { to: string; label: string }
  } | null>(null)

  const upload = useCallback(
    async (file: File) => {
      setBusy(true)
      setMessage(null)
      setRetryFile(file)
      setRetryAvailable(false)
      try {
        const result = await uploadResume(file)
        const status = result.job?.status
        if (result.duplicate) {
          setMessage({
            tone: "warn",
            text: "این فایل قبلاً بارگذاری شده است؛ پروفایل موجود دوباره ساخته نمی‌شود.",
            link: result.candidate
              ? {
                  to: `/candidates/${result.candidate.id}`,
                  label: "نمایش پرونده استعداد",
                }
              : undefined,
          })
        } else if (status === "extracted" && result.candidate) {
          setRetryFile(null)
          window.location.assign(`/candidates/${result.candidate.id}`)
          return
        } else if (status && result.job) {
          const detail = parseStatusLabel(status, result.job.reason)
          if (status === "needs_review" && result.candidate) {
            setMessage({
              tone: "warn",
              text: `رزومه ثبت شد اما ${detail}.`,
              link: {
                to: `/candidates/${result.candidate.id}`,
                label: "نمایش پرونده استعداد",
              },
            })
          } else if (status === "failed") {
            setRetryAvailable(true)
            setMessage({ tone: "error", text: `این سند پردازش نشد: ${detail}.` })
          } else {
            setMessage({ tone: "error", text: `این سند پردازش شد: ${detail}.` })
          }
        }
        onUploaded()
      } catch (e) {
        setRetryAvailable(true)
        setMessage({ tone: "error", text: persianError(e) })
      } finally {
        setBusy(false)
        if (inputRef.current) inputRef.current.value = ""
      }
    },
    [onUploaded]
  )

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files?.[0]
    if (file && !busy) void upload(file)
  }

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        aria-label="بارگذاری رزومه"
        onClick={() => {
          if (!busy && inputRef.current) {
            // Clear before opening the picker so choosing the same file fires
            // change even when the previous request failed.
            inputRef.current.value = ""
            inputRef.current.click()
          }
        }}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !busy) {
            e.preventDefault()
            if (inputRef.current) {
              inputRef.current.value = ""
              inputRef.current.click()
            }
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          if (!busy) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={[
          "flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors",
          "border-t-2 border-t-accent border-t-solid", // the saffron tray rule
          dragging ? "border-primary bg-secondary/60" : "border-border bg-card hover:bg-secondary/40",
          busy ? "cursor-progress opacity-80" : "",
        ].join(" ")}
      >
        {busy ? (
          <>
            <LoaderCircleIcon className="size-6 animate-spin text-primary" />
            <p className="text-sm font-medium text-foreground">
              در حال خواندن رزومه…
            </p>
            <p className="text-xs text-muted-foreground">
              استخراج متن و ساخت پروفایل معمولاً کمتر از یک دقیقه طول می‌کشد.
            </p>
          </>
        ) : (
          <>
            <FileUpIcon className="size-6 text-primary" />
            <p className="text-sm font-medium text-foreground">
              رزومه را اینجا بیندازید یا انتخاب کنید
            </p>
            <p className="text-xs text-muted-foreground">
              PDF ،DOCX یا TXT — تا ۱۰ مگابایت؛ متن فارسی و انگلیسی، عیناً همان‌طور
              که نوشته شده.
            </p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.currentTarget.value = ""
            if (file) void upload(file)
          }}
        />
      </div>

      {message && (
        <Alert variant={message.tone === "error" ? "destructive" : "default"}>
          <AlertDescription>
            {message.text}{" "}
            {message.link && (
              <Link
                to={message.link.to}
                className="font-medium text-primary underline underline-offset-4"
              >
                {message.link.label}
              </Link>
            )}
            {retryAvailable && retryFile && !busy && (
              <button
                type="button"
                onClick={() => void upload(retryFile)}
                className="ms-2 font-medium text-primary underline underline-offset-4"
              >
                تلاش دوباره
              </button>
            )}
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}

function CandidateRow({ candidate }: { candidate: CandidateSummary }) {
  return (
    <Link
      to={`/candidates/${candidate.id}`}
      className="flex items-center justify-between gap-4 px-4 py-3 transition-colors hover:bg-secondary/40 focus-visible:bg-secondary/40 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
    >
      <div className="min-w-0">
        <p className="truncate font-semibold text-foreground">
          {candidate.full_name}
        </p>
        {candidate.headline && (
          <p className="truncate text-sm text-muted-foreground">
            {candidate.headline}
          </p>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-0.5">
        {candidate.email && (
          <span dir="ltr" className="text-xs text-muted-foreground">
            {candidate.email}
          </span>
        )}
        <span className="text-xs text-muted-foreground">
          {formatJalali(candidate.created_at)}
        </span>
      </div>
    </Link>
  )
}

export function PoolPage() {
  const [candidates, setCandidates] = useState<CandidateSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const requested = useRef(false)

  const load = useCallback(async () => {
    try {
      setCandidates(await fetchCandidates())
    } catch (e) {
      setError(persianError(e))
    }
  }, [])

  // Fetch the pool on mount. React 18 StrictMode double-invokes effects in
  // dev; the ref guard keeps that to one request.
  useEffect(() => {
    if (requested.current) return
    requested.current = true
    void load()
  }, [load])

  if (error) {
    return (
      <AppShell>
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </AppShell>
    )
  }

  if (candidates === null) {
    return (
      <AppShell>
        <p className="py-16 text-center text-sm text-muted-foreground">
          در حال بارگذاری…
        </p>
      </AppShell>
    )
  }

  return (
    <AppShell>
      {/* The pool's ledger header — same saffron rule as the desk diary. */}
      <section className="border-s-2 border-accent ps-4">
        <p className="text-sm text-muted-foreground">مجموعه استعدادهای سازمان</p>
        <h1 className="mt-1 flex items-center gap-3 text-2xl font-bold text-foreground sm:text-3xl">
          استعدادها
          <Badge variant="secondary">{toPersianDigits(candidates.length)}</Badge>
        </h1>
      </section>

      <div className="mt-6">
        <UploadTray onUploaded={load} />
      </div>

      <div className="mt-8">
        {candidates.length === 0 ? (
          <Card>
            <CardContent className="py-10">
              <Empty>
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <UsersIcon />
                  </EmptyMedia>
                  <EmptyTitle>هنوز استعدادی در مجموعه نیست</EmptyTitle>
                  <EmptyDescription>
                    اولین رزومه را بارگذاری کنید؛ پروفایل ساخت‌یافته به‌طور خودکار
                    ساخته می‌شود.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            </CardContent>
          </Card>
        ) : (
          <Card className="divide-y overflow-hidden p-0">
            {candidates.map((candidate) => (
              <CandidateRow key={candidate.id} candidate={candidate} />
            ))}
          </Card>
        )}
      </div>
    </AppShell>
  )
}
