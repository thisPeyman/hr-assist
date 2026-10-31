import { useCallback, useEffect, useState, type FormEvent } from "react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router"
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material"
import {
  ArrowRight,
  Download,
  GitMerge,
  Pencil,
  RefreshCw,
  Sparkles,
} from "lucide-react"
import { AppShell } from "@/components/shell"
import { ProfileEditor } from "@/components/profile-editor"
import {
  candidateAction,
  fetchCandidateWorkspace,
  fetchResume,
  persianError,
  saveCandidateProfile,
  type CandidateProfile,
  type CandidateWorkspace,
  type ResumeDetail,
} from "@/lib/api"
import { formatJalali } from "@/lib/jalali"
import { reviewProfile } from "@/lib/review"
import { formatResumeDate } from "@/lib/profile"
import { Preview, Profile } from "@/pages/resumes"

const fieldLabels: Record<string, string> = {
  "contact.full_name": "نام و نام خانوادگی",
  "contact.email": "ایمیل",
  "contact.phone": "تلفن",
  "contact.location": "محل زندگی",
  "contact.links": "پیوندها",
  headline: "عنوان حرفه‌ای",
  summary: "معرفی رزومه",
  skills: "مهارت‌ها",
  industries: "صنایع",
  work_experience: "سوابق کاری",
  education: "تحصیلات",
  languages: "زبان‌ها",
  certifications: "گواهی‌ها",
  document_language: "زبان سند",
  extraction_notes: "یادداشت‌های استخراج",
  title: "عنوان",
  company: "کارفرما",
  location: "محل",
  start_date: "شروع",
  end_date: "پایان",
  current: "شغل فعلی",
  bullets: "فعالیت‌ها",
  degree: "مقطع",
  field: "رشته",
  institution: "مؤسسه",
  language: "زبان",
  proficiency: "سطح",
  name: "نام",
  issuer: "صادرکننده",
  date: "تاریخ",
  type: "نوع",
  url: "نشانی",
}
const eventLabels: Record<string, string> = {
  resume_added: "رزومه دریافت شد",
  resume_deleted: "فایل رزومه حذف شد؛ پرونده و تاریخچه حفظ شدند",
  new_resume_added: "نسخهٔ جدید رزومه دریافت شد",
  profile_reconciled: "فیلدهای خالی تکمیل و اختلاف‌ها پیشنهاد شدند",
  profile_edited: "پروفایل توسط HR ویرایش شد",
  resume_profile_edited: "اطلاعات اصلی ویرایش شد",
  profile_review_accepted: "اطلاعات توسط HR تأیید شد",
  profile_change_accepted: "پیشنهاد تغییر پذیرفته شد",
  profile_change_rejected: "پیشنهاد تغییر رد شد",
  candidate_merged: "دو پرونده ادغام شدند",
  ai_summary_regenerated: "خلاصهٔ هوشمند با درخواست HR بازتولید شد",
  new_resume_acknowledged: "دریافت رزومهٔ جدید تأیید شد",
  note_added: "یادداشت اضافه شد",
}

function Value({ value }: { value: unknown }) {
  if (
    value === null ||
    value === undefined ||
    value === "" ||
    (Array.isArray(value) && value.length === 0)
  )
    return (
      <Typography color="text.secondary" sx={{ fontSize: 13 }}>
        ثبت نشده
      </Typography>
    )
  if (Array.isArray(value))
    return (
      <Stack spacing={1.5}>
        {value.map((item, index) => (
          <Box key={index}>
            <Value value={item} />
          </Box>
        ))}
      </Stack>
    )
  if (typeof value === "object")
    return (
      <Stack spacing={0.5}>
        {Object.entries(value as Record<string, unknown>)
          .filter(([, item]) => item !== null && item !== "" && item !== false)
          .map(([key, item]) => (
            <Box key={key}>
              <Typography
                component="span"
                sx={{ fontSize: 11, color: "text.secondary" }}
              >
                {fieldLabels[key] ?? key}:{" "}
              </Typography>
              {typeof item === "object" ? (
                <Value value={item} />
              ) : (
                <Typography component="span" dir="auto" sx={{ fontSize: 13 }}>
                  {item === true ? "بله" : ["start_date", "end_date", "date"].includes(key) && typeof item === "string" ? formatResumeDate(item) : String(item)}
                </Typography>
              )}
            </Box>
          ))}
      </Stack>
    )
  return (
    <Typography
      dir="auto"
      sx={{ fontSize: 13, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
    >
      {String(value)}
    </Typography>
  )
}

export function CandidatePage() {
  const { id = "" } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [data, setData] = useState<CandidateWorkspace | null>(null)
  const [resume, setResume] = useState<ResumeDetail | null>(null)
  const [draft, setDraft] = useState<CandidateProfile>(() =>
    reviewProfile(null),
  )
  const [editing, setEditing] = useState(params.get("edit") === "1")
  const [tab, setTab] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [mergeTarget, setMergeTarget] = useState<
    CandidateWorkspace["duplicates"][number] | null
  >(null)
  const [note, setNote] = useState("")
  const load = useCallback(
    async (signal?: AbortSignal) => {
      const workspace = await fetchCandidateWorkspace(id, signal)
      const file = workspace.resume_id
        ? await fetchResume(workspace.resume_id, signal)
        : null
      if (signal?.aborted) return
      setData(workspace)
      setResume(file)
      setDraft(reviewProfile(workspace.profile))
    },
    [id],
  )
  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal).catch((cause) => {
      if (!controller.signal.aborted) setError(persianError(cause))
    })
    return () => controller.abort()
  }, [load])
  async function action(path: string, body?: unknown) {
    setBusy(path)
    setError(null)
    try {
      const result = await candidateAction(id, path, body)
      await load()
      return result
    } catch (cause) {
      setError(persianError(cause))
      return null
    } finally {
      setBusy(null)
    }
  }
  async function save(event: FormEvent) {
    event.preventDefault()
    setBusy("profile")
    setError(null)
    try {
      await saveCandidateProfile(id, draft)
      await load()
      setEditing(false)
    } catch (cause) {
      setError(persianError(cause))
    } finally {
      setBusy(null)
    }
  }
  async function merge() {
    if (!mergeTarget) return
    setBusy("merge")
    setError(null)
    try {
      const result = await candidateAction(id, "merge", {
        target_id: mergeTarget.id,
      })
      navigate(`/candidates/${result.candidate_id}`, { replace: true })
      setMergeTarget(null)
    } catch (cause) {
      setError(persianError(cause))
    } finally {
      setBusy(null)
    }
  }
  const detail: ResumeDetail = resume
    ? { ...resume, profile: data?.profile ?? null }
    : {
        id: "",
        filename: "",
        created_at: "",
        status: "extracted",
        reason: null,
        latest_job_id: null,
        candidate_id: id,
        candidate_name: data?.full_name ?? null,
        candidate_email: null,
        profile: data?.profile ?? null,
      }
  return (
    <AppShell>
      <Button
        component={Link}
        to="/candidates"
        startIcon={<ArrowRight size={16} />}
        sx={{ mb: 2 }}
      >
        بانک کاندیداها
      </Button>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {!data && !error && <CircularProgress aria-label="بارگذاری پروفایل" />}
      {data && (
        <>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            spacing={2}
            sx={{ justifyContent: "space-between", mb: 3 }}
          >
            <Box>
              <Typography variant="h4" dir="auto">
                {data.full_name}
              </Typography>
              <Typography color="text.secondary" dir="auto" sx={{ mt: 1 }}>
                {reviewProfile(data.profile).headline}
              </Typography>
            </Box>
            {!editing && (
              <Button
                variant="outlined"
                startIcon={<Pencil size={16} />}
                onClick={() => {
                  setEditing(true)
                  setTab(0)
                }}
              >
                ویرایش کامل پروفایل
              </Button>
            )}
          </Stack>
          {data.new_resume_received && (
            <Alert
              severity="info"
              sx={{ mb: 2 }}
              action={
                <Button
                  disabled={Boolean(busy)}
                  onClick={() => void action("acknowledge-resume")}
                >
                  متوجه شدم
                </Button>
              }
            >
              رزومهٔ جدید به همین پرونده متصل شده است. اصلاحات قبلی حفظ شده‌اند؛
              اختلاف‌ها را در بخش «تغییرات جدید» بررسی کنید.
            </Alert>
          )}
          <Paper
            variant="outlined"
            sx={{
              p: { xs: 2, sm: 3 },
              mb: 3,
              bgcolor: "#f3f7fe",
              borderColor: "#c9dcf6",
            }}
          >
            <Stack
              direction={{ xs: "column", sm: "row" }}
              spacing={2}
              sx={{
                justifyContent: "space-between",
                alignItems: { sm: "center" },
                mb: 2,
              }}
            >
              <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                <Sparkles size={20} color="#1565c0" />
                <Typography variant="h6">خلاصهٔ هوشمند رزومه</Typography>
              </Stack>
              <Button
                size="small"
                disabled={Boolean(busy) || !data.resume_version}
                startIcon={
                  busy === "summary/regenerate" ? (
                    <CircularProgress size={15} />
                  ) : (
                    <RefreshCw size={15} />
                  )
                }
                onClick={() => void action("summary/regenerate")}
              >
                {busy === "summary/regenerate"
                  ? "در حال تولید…"
                  : data.summary?.content
                    ? "بازتولید دستی"
                    : "تولید خلاصه"}
              </Button>
            </Stack>
            {data.summary?.content ? (
              <>
                <Typography
                  sx={{ lineHeight: 2.2, fontSize: 14, whiteSpace: "pre-wrap" }}
                >
                  {data.summary.content.text}
                </Typography>
                <Typography color="text.secondary" sx={{ fontSize: 11, mt: 1 }}>
                  {data.summary.content.text
                    .split(/\s+/)
                    .length.toLocaleString("fa-IR")}{" "}
                  کلمه
                  {data.summary.generated_at
                    ? ` · تولیدشده در ${formatJalali(data.summary.generated_at)}`
                    : ""}
                </Typography>
                {data.summary.content.unclear_or_missing.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography sx={{ fontWeight: 650, fontSize: 13 }}>
                      موارد نامشخص یا ذکرنشده
                    </Typography>
                    <Box
                      component="ul"
                      sx={{ m: 0, mt: 1, paddingInlineStart: 3 }}
                    >
                      {data.summary.content.unclear_or_missing.map(
                        (missing, i) => (
                          <Typography
                            component="li"
                            key={i}
                            sx={{ fontSize: 12, lineHeight: 2 }}
                          >
                            {missing}
                          </Typography>
                        ),
                      )}
                    </Box>
                  </Box>
                )}
              </>
            ) : (
              <Typography color="text.secondary" sx={{ fontSize: 13 }}>
                خلاصه‌ای برای این نسخه ذخیره نشده است. با «تولید خلاصه» آن را
                یک‌بار ایجاد کنید.
              </Typography>
            )}
            {data.summary?.error && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                {data.summary.error === "provider_access_denied"
                  ? "سرویس AI دسترسی را رد کرده است (403)."
                  : data.summary.error === "provider_authentication_failed"
                    ? "کلید سرویس AI پذیرفته نشد."
                    : data.summary.error === "provider_limit_reached"
                      ? "محدودیت اعتبار یا تعداد درخواست سرویس AI اعمال شده است."
                      : "تولید آخر خلاصه موفق نبود."}{" "}
                پس از بررسی اتصال AI، بازتولید دستی را اجرا کنید.
              </Alert>
            )}
          </Paper>
          {data.duplicates.length > 0 && (
            <Alert severity="warning" sx={{ mb: 3 }}>
              <Typography sx={{ fontWeight: 650 }}>
                احتمال پروندهٔ تکراری بر اساس شباهت نام
              </Typography>
              <Typography sx={{ fontSize: 12, mb: 1 }}>
                شباهت نام به‌تنهایی باعث ادغام نمی‌شود. هویت فرد را قبل از تأیید
                بررسی کنید.
              </Typography>
              {data.duplicates.map((peer) => (
                <Stack
                  key={peer.id}
                  direction={{ xs: "column", sm: "row" }}
                  spacing={1}
                  sx={{ justifyContent: "space-between", mt: 1 }}
                >
                  <Box>
                    <Button component={Link} to={`/candidates/${peer.id}`}>
                      {peer.full_name}
                    </Button>
                    <Typography
                      component="span"
                      dir="auto"
                      sx={{ fontSize: 12 }}
                    >
                      {peer.email ?? peer.phone}
                    </Typography>
                  </Box>
                  <Button
                    size="small"
                    startIcon={<GitMerge size={16} />}
                    onClick={() => setMergeTarget(peer)}
                  >
                    بررسی و ادغام در این فرد
                  </Button>
                </Stack>
              ))}
            </Alert>
          )}
          <Paper variant="outlined" sx={{ overflow: "hidden" }}>
            <Tabs
              value={tab}
              onChange={(_, value: number) => setTab(value)}
              variant="scrollable"
              scrollButtons="auto"
              aria-label="بخش‌های پروفایل"
            >
              <Tab label="پروفایل" />
              <Tab
                label={`تغییرات جدید (${data.changes.length.toLocaleString("fa-IR")})`}
              />
              <Tab label="یادداشت‌ها و درخواست‌ها" />
              <Tab label="تاریخچه" />
            </Tabs>
            <Divider />
            <Box sx={{ p: { xs: 2, sm: 3 } }}>
              {tab === 0 &&
                (editing ? (
                  <ProfileEditor
                    profile={draft}
                    onChange={setDraft}
                    onSave={(event) => void save(event)}
                    busy={busy === "profile"}
                    onCancel={() => {
                      setDraft(reviewProfile(data.profile))
                      setEditing(false)
                    }}
                  />
                ) : (
                  <Box
                    sx={{
                      display: "grid",
                      gap: 4,
                      gridTemplateColumns: {
                        xs: "1fr",
                        lg: "minmax(0,1.2fr) minmax(0,1fr)",
                      },
                    }}
                  >
                    <Profile detail={detail} />
                    <Stack spacing={2}>
                      {resume?.latest_job_id ? (
                        <>
                          <Typography variant="h6">
                            جدیدترین فایل رزومه
                          </Typography>
                          <Typography dir="auto" sx={{ fontSize: 13 }}>
                            {resume.filename}
                          </Typography>
                          <Button
                            component="a"
                            href={`/api/review/${resume.latest_job_id}/document`}
                            variant="outlined"
                            startIcon={<Download size={17} />}
                          >
                            دریافت فایل اصلی
                          </Button>
                          <Preview jobId={resume.latest_job_id} />
                        </>
                      ) : (
                        <Alert severity="info">فایل رزومه‌ای متصل نیست.</Alert>
                      )}
                    </Stack>
                  </Box>
                ))}
              {tab === 1 && (
                <Stack spacing={2}>
                  {!data.changes.length && (
                    <Alert severity="success">
                      پیشنهاد تغییر تعیین‌تکلیف‌نشده‌ای وجود ندارد.
                    </Alert>
                  )}
                  {data.changes.map((change) => (
                    <Paper key={change.id} variant="outlined" sx={{ p: 2 }}>
                      <Typography variant="h6" sx={{ mb: 2 }}>
                        {fieldLabels[change.field_path] ?? change.field_path}
                      </Typography>
                      <Box
                        sx={{
                          display: "grid",
                          gap: 2,
                          gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
                        }}
                      >
                        <Box sx={{ p: 2, bgcolor: "#f8fafc", borderRadius: 1 }}>
                          <Typography
                            sx={{ fontSize: 11, fontWeight: 650, mb: 1 }}
                          >
                            اطلاعات فعلی
                          </Typography>
                          <Value value={change.old_value} />
                        </Box>
                        <Box sx={{ p: 2, bgcolor: "#eff6ff", borderRadius: 1 }}>
                          <Typography
                            sx={{ fontSize: 11, fontWeight: 650, mb: 1 }}
                          >
                            پیشنهاد رزومهٔ جدید
                          </Typography>
                          <Value value={change.new_value} />
                        </Box>
                      </Box>
                      <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                        <Button
                          variant="contained"
                          size="small"
                          disabled={Boolean(busy)}
                          onClick={() =>
                            void action(`changes/${change.id}`, {
                              action: "accept",
                            })
                          }
                        >
                          پذیرش تغییر
                        </Button>
                        <Button
                          size="small"
                          disabled={Boolean(busy)}
                          onClick={() =>
                            void action(`changes/${change.id}`, {
                              action: "reject",
                            })
                          }
                        >
                          حفظ اطلاعات فعلی
                        </Button>
                      </Stack>
                    </Paper>
                  ))}
                </Stack>
              )}
              {tab === 2 && (
                <Box
                  sx={{
                    display: "grid",
                    gap: 3,
                    gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
                  }}
                >
                  <Stack spacing={2}>
                    <Typography variant="h6">یادداشت‌های HR</Typography>
                    <TextField
                      label="یادداشت جدید"
                      multiline
                      minRows={3}
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                    />
                    <Button
                      variant="outlined"
                      disabled={Boolean(busy) || !note.trim()}
                      onClick={async () => {
                        if (await action("notes", { body: note })) setNote("")
                      }}
                    >
                      ثبت یادداشت
                    </Button>
                    {data.notes.map((item) => (
                      <Paper variant="outlined" key={item.id} sx={{ p: 2 }}>
                        <Typography
                          sx={{ whiteSpace: "pre-wrap", fontSize: 13 }}
                        >
                          {item.body}
                        </Typography>
                        <Typography
                          color="text.secondary"
                          sx={{ fontSize: 11, mt: 1 }}
                        >
                          {formatJalali(item.created_at)}
                        </Typography>
                      </Paper>
                    ))}
                  </Stack>
                  <Stack spacing={2}>
                    <Typography variant="h6">درخواست‌های شغلی مرتبط</Typography>
                    {!data.applications.length && (
                      <Typography color="text.secondary" sx={{ fontSize: 13 }}>
                        درخواستی برای این فرد ثبت نشده است.
                      </Typography>
                    )}
                    {data.applications.map((application) => (
                      <Paper
                        variant="outlined"
                        sx={{ p: 2 }}
                        key={application.id}
                      >
                        <Typography sx={{ fontWeight: 650 }}>
                          {application.role_title}
                        </Typography>
                        <Chip
                          size="small"
                          sx={{ mt: 1 }}
                          label={
                            application.stage === "received"
                              ? "دریافت‌شده"
                              : application.stage
                          }
                        />
                      </Paper>
                    ))}
                  </Stack>
                </Box>
              )}
              {tab === 3 && (
                <Stack spacing={0}>
                  {data.activity.map((event) => (
                    <Box
                      key={event.id}
                      sx={{ py: 2, borderBottom: 1, borderColor: "divider" }}
                    >
                      <Typography sx={{ fontWeight: 650, fontSize: 13 }}>
                        {eventLabels[event.event_type] ?? "تغییر در پرونده"}
                      </Typography>
                      <Typography
                        color="text.secondary"
                        sx={{ fontSize: 11, mt: 0.5 }}
                      >
                        {formatJalali(event.created_at)}
                      </Typography>
                      {typeof event.data.field === "string" && (
                        <Typography sx={{ fontSize: 12, mt: 1 }}>
                          {fieldLabels[event.data.field] ?? event.data.field}
                        </Typography>
                      )}
                      {event.event_type === "profile_edited" && (
                        <Typography sx={{ fontSize: 12, mt: 1 }}>
                          {Object.keys((event.data.changes as object) ?? {})
                            .map((key) => fieldLabels[key] ?? key)
                            .join("، ")}
                        </Typography>
                      )}
                      {typeof event.data.source_name === "string" && (
                        <Typography sx={{ fontSize: 12, mt: 1 }}>
                          پروندهٔ منتقل‌شده: {event.data.source_name}
                        </Typography>
                      )}
                      {event.data.status === "error" && (
                        <Typography color="error" sx={{ fontSize: 12 }}>
                          تولید خلاصه ناموفق بود.
                        </Typography>
                      )}
                    </Box>
                  ))}
                </Stack>
              )}
            </Box>
          </Paper>
          <Dialog
            open={Boolean(mergeTarget)}
            onClose={busy ? undefined : () => setMergeTarget(null)}
            maxWidth="sm"
            fullWidth
          >
            <DialogTitle>تأیید ادغام دو کاندیدا</DialogTitle>
            <DialogContent>
              <DialogContentText>
                پروندهٔ «{data.full_name}» در «{mergeTarget?.full_name}» ادغام
                می‌شود. یادداشت‌ها، درخواست‌ها و تاریخچه منتقل می‌شوند و فقط
                جدیدترین فایل رزومه نگهداری می‌شود. اختلاف اطلاعات برای تصمیم HR
                باقی می‌ماند. این ادغام قابل بازگشت خودکار نیست.
              </DialogContentText>
              {mergeTarget && (
                <Typography dir="auto" sx={{ mt: 2 }}>
                  {mergeTarget.email ?? mergeTarget.phone}
                </Typography>
              )}
            </DialogContent>
            <DialogActions sx={{ p: 2 }}>
              <Button
                disabled={Boolean(busy)}
                onClick={() => setMergeTarget(null)}
              >
                انصراف
              </Button>
              <Button
                variant="contained"
                disabled={Boolean(busy)}
                onClick={() => void merge()}
              >
                تأیید ادغام
              </Button>
            </DialogActions>
          </Dialog>
        </>
      )}
    </AppShell>
  )
}
