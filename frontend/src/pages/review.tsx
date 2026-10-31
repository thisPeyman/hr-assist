import { useCallback, useEffect, useState, type FormEvent } from "react"
import { Link } from "react-router"
import { Alert, Box, Button, Chip, CircularProgress, Dialog, DialogContent,
  DialogActions, DialogTitle, Paper, Stack, Tab, Tabs, Typography } from "@mui/material"
import { AppShell } from "@/components/shell"
import { ProfileEditor } from "@/components/profile-editor"
import { fetchReview, fetchReviewDetail, persianError, resolveReview,
  type CandidateProfile, type ReviewDetail, type ReviewList } from "@/lib/api"
import { formatJalali } from "@/lib/jalali"
import { parseStatusLabel } from "@/lib/profile"
import { reviewProfile } from "@/lib/review"
import { Preview } from "@/pages/resumes"

function profileFields(profile: CandidateProfile): Record<string, unknown> {
  const { contact, ...rest } = profile
  return { ...rest, ...Object.fromEntries(Object.entries(contact).map(([key, value]) => [`contact.${key}`, value])) }
}

export function ReviewPage() {
  const [view, setView] = useState<"review" | "all">("review")
  const [data, setData] = useState<ReviewList | null>(null)
  const [detail, setDetail] = useState<ReviewDetail | null>(null)
  const [draft, setDraft] = useState(() => reviewProfile(null))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [opening, setOpening] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const load = useCallback(async () => {
    const rows = await fetchReview(view)
    setData(rows)
    window.dispatchEvent(new Event("ingestion-changed"))
  }, [view])
  useEffect(() => {
    let active = true
    fetchReview(view).then(rows => { if (active) setData(rows) })
      .catch(cause => { if (active) setError(persianError(cause)) })
    return () => { active = false }
  }, [view])
  async function open(id: string) {
    setOpening(true)
    setError(null)
    try {
      const item = await fetchReviewDetail(id)
      setDetail(item)
      setDraft(reviewProfile(item.raw_json))
    } catch (cause) { setError(persianError(cause)) }
    finally { setOpening(false) }
  }
  async function decide(action: "accept" | "not_a_resume" | "failed" | "rescan") {
    if (!detail) return
    setBusy(true)
    setError(null)
    try {
      const initial = profileFields(reviewProfile(detail.raw_json))
      const current = profileFields(draft)
      const edited_fields = Object.keys(current).filter(key => JSON.stringify(current[key]) !== JSON.stringify(initial[key]))
      const baseline = detail.candidate_profile ? profileFields(reviewProfile(detail.candidate_profile)) : initial
      const response = await resolveReview(detail.id, action, action === "accept" ? draft : undefined,
        { edited_fields, expected_values: baseline })
      if (action === "rescan") {
        const refreshed = await fetchReviewDetail(detail.id)
        setDetail(refreshed)
      } else {
        setDetail(null)
        setResult(response.candidate_id)
      }
      await load()
    } catch (cause) { setError(persianError(cause)) }
    finally { setBusy(false) }
  }
  const actionable = detail && ["needs_review", "failed"].includes(detail.status) && !detail.reason?.startsWith("human_dismissed")
  return <AppShell>
    <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ justifyContent: "space-between", mb: 3 }}>
      <Box><Typography variant="h4">صف بازبینی رزومه‌ها</Typography>
        <Typography color="text.secondary" sx={{ mt: 1 }}>اطلاعات ناقص را تکمیل کنید؛ تصمیم نهایی با شماست.</Typography></Box>
      <Button component={Link} to="/settings/ingestion">تنظیمات دریافت رزومه</Button>
    </Stack>
    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
    {result && <Alert severity="success" sx={{ mb: 2 }}>پروفایل ذخیره شد. <Button component={Link} to={`/candidates/${result}`}>مشاهدهٔ پرونده و اختلاف‌ها</Button></Alert>}
    <Tabs value={view} onChange={(_, value) => { setData(null); setView(value) }} aria-label="نمای اسناد">
      <Tab value="review" label="نیازمند بازبینی" /><Tab value="all" label="تاریخچهٔ همهٔ اسناد" />
    </Tabs>
    {!data && <CircularProgress aria-label="بارگذاری صف" sx={{ mt: 3 }} />}
    <Stack spacing={2} sx={{ mt: 2 }}>
      {data?.mail_failures.map(mail => <Alert severity="error" key={mail.id}>
        <Typography sx={{ fontWeight: 650 }}>دریافت ایمیل ناموفق — {formatJalali(mail.created_at)}</Typography>
        <Typography>پیام پردازش نشد؛ رزومه را دستی بارگذاری کنید یا با مدیر برای بازپخش پیام پشتیبان هماهنگ کنید.</Typography>
        <Typography dir="auto" sx={{ overflowWrap: "anywhere", fontSize: 12 }}>{mail.reason}</Typography>
        <Button component={Link} to="/upload">بارگذاری دستی رزومه</Button>
      </Alert>)}
      {data && !data.items.length && <Alert severity="info">{view === "review" ? "سندی در انتظار بازبینی نیست." : "هنوز سندی دریافت نشده است."}</Alert>}
      {data?.items.map(item => <Paper variant="outlined" key={item.id} sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ justifyContent: "space-between", alignItems: { sm: "center" } }}>
          <Box sx={{ minWidth: 0 }}><Typography dir="auto" sx={{ fontWeight: 650, overflowWrap: "anywhere" }}>{item.filename}</Typography>
            <Typography color="text.secondary" sx={{ fontSize: 12, mt: 1 }}>{formatJalali(item.created_at)}</Typography>
            <Chip size="small" sx={{ mt: 1, maxWidth: "100%", height: "auto", "& .MuiChip-label": { whiteSpace: "normal", py: 0.5 } }} label={parseStatusLabel(item.status, item.reason)} />
          </Box>
          <Button variant="outlined" disabled={opening} onClick={() => void open(item.id)}>بررسی سند</Button>
        </Stack>
      </Paper>)}
    </Stack>
    <Dialog open={Boolean(detail)} onClose={busy ? undefined : () => setDetail(null)} maxWidth="xl" fullWidth>
      <DialogTitle>بررسی سند — <Box component="span" dir="auto">{detail?.filename}</Box></DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {detail && <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", lg: "minmax(0,1fr) minmax(0,1.2fr)" } }}>
          <Stack spacing={2} sx={{ minWidth: 0 }}>
            <Alert severity={detail.blocked ? "error" : "info"}>{parseStatusLabel(detail.status, detail.reason)}</Alert>
            {detail.blocked ? <Alert severity="warning">دریافت، پیش‌نمایش و پذیرش تا تکمیل بررسی ایمنی مسدود است.</Alert> : <>
              <Button component="a" href={`/api/review/${detail.id}/document`} variant="outlined">دریافت فایل اصلی</Button>
              <Preview key={detail.id} jobId={detail.id} />
              {detail.raw_text && <Paper variant="outlined" sx={{ p: 2, maxHeight: 400, overflow: "auto" }}><Typography dir="auto" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", fontSize: 12 }}>{detail.raw_text}</Typography></Paper>}
            </>}
            {actionable && <Stack spacing={1}>
              {detail.blocked && ["inbound:scanner_unavailable", "inbound:malware_detected"].includes(detail.reason ?? "") && <Button disabled={busy} variant="outlined" onClick={() => void decide("rescan")}>بررسی دوبارهٔ ایمنی</Button>}
              <Button disabled={busy} onClick={() => void decide("not_a_resume")}>رزومه نیست</Button>
              <Button disabled={busy} color="error" onClick={() => void decide("failed")}>ثبت به‌عنوان ناموفق</Button>
            </Stack>}
            {detail.candidate_id && <Button component={Link} to={`/candidates/${detail.candidate_id}`}>پروندهٔ فعلی و اختلاف‌ها</Button>}
          </Stack>
          <Box sx={{ minWidth: 0 }}>
            {actionable && !detail.blocked ? <>
              <Alert severity="info" sx={{ mb: 2 }}>فقط فیلدهایی که ویرایش می‌کنید اصلاح انسانی محسوب می‌شوند. اختلاف‌های دیگر بدون بازنویسی اطلاعات فعلی، در پرونده پیشنهاد می‌شوند.</Alert>
              <ProfileEditor profile={draft} onChange={setDraft} busy={busy} onCancel={() => setDetail(null)} onSave={(event: FormEvent) => { event.preventDefault(); void decide("accept") }} />
            </> : <Alert severity="info">{detail.blocked ? "پس از بررسی موفق ایمنی، سند دوباره پردازش می‌شود." : "این سند تعیین تکلیف شده است. اصلاحات بعدی را در پروندهٔ فرد انجام دهید."}</Alert>}
          </Box>
        </Box>}
      </DialogContent>
      <DialogActions><Button disabled={busy} onClick={() => setDetail(null)}>بستن بررسی سند</Button></DialogActions>
    </Dialog>
  </AppShell>
}
