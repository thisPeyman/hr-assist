import { useEffect, useState } from "react"
import { Link } from "react-router"
import { Alert, Button, CircularProgress, Paper, Stack, Typography } from "@mui/material"
import { AppShell } from "@/components/shell"
import { fetchIngestionSettings, persianError, type IngestionSettings } from "@/lib/api"

export function IngestionSettingsPage() {
  const [data, setData] = useState<IngestionSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    let active = true
    fetchIngestionSettings().then(value => { if (active) setData(value) })
      .catch(cause => { if (active) setError(persianError(cause)) })
    return () => { active = false }
  }, [])
  return <AppShell>
    <Typography variant="h4" sx={{ mb: 3 }}>تنظیمات دریافت رزومه</Typography>
    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
    {!data && !error && <CircularProgress aria-label="بارگذاری تنظیمات" />}
    {data && <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, maxWidth: 800 }}>
      <Stack spacing={2}>
        <Typography variant="h6">نشانی دریافت رزومهٔ سازمان</Typography>
        <Typography>ایمیل حاوی رزومه را به این نشانی بفرستید. هر سند پس از پردازش در بانک کاندیداها یا صف بازبینی ظاهر می‌شود.</Typography>
        {!data.email_enabled && <Alert severity="warning">دریافت ایمیل هنوز فعال نیست. مدیر باید دامنه و اتصال دریافت ایمیل را در سرور تنظیم کند؛ تا آن زمان از بارگذاری دستی استفاده کنید.</Alert>}
        {data.email_address && <>
          <Typography dir="ltr" sx={{ p: 2, bgcolor: "background.default", overflowWrap: "anywhere", fontWeight: 650 }}>{data.email_address}</Typography>
          <Button variant="outlined" onClick={async () => {
            try { await navigator.clipboard.writeText(data.email_address!); setCopied(true) }
            catch { setError("کپی خودکار در دسترس نیست؛ نشانی را انتخاب و کپی کنید.") }
          }}>{copied ? "نشانی کپی شد" : "کپی نشانی"}</Button>
        </>}
        <Alert severity="info">هیچ رزومه‌ای بدون تصمیم باقی نمی‌ماند؛ خطاهای دریافت ایمیل و اسناد نیازمند اصلاح را در صف بازبینی پیگیری کنید.</Alert>
        <Button component={Link} to="/review">صف بازبینی ({data.review_count.toLocaleString("fa-IR")})</Button>
        <Button component={Link} to="/upload" variant="contained">بارگذاری دستی رزومه</Button>
      </Stack>
    </Paper>}
  </AppShell>
}
