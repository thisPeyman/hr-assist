import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router"
import { Alert, Badge, Box, Button, CircularProgress, Divider, IconButton, Popover, Stack, Typography } from "@mui/material"
import { Bell } from "lucide-react"
import { fetchNotifications, persianError, setNotificationRead, type InAppNotification } from "@/lib/api"
import { formatJalali } from "@/lib/jalali"

export function NotificationBell() {
  const navigate = useNavigate()
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)
  const [data, setData] = useState<{ items: InAppNotification[]; unread_count: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const load = useCallback(async (signal?: AbortSignal) => {
    try { const result = await fetchNotifications(signal); if (!signal?.aborted) { setData(result); setError(null) } }
    catch (cause) { if (!signal?.aborted) setError(persianError(cause)) }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    const refresh = () => void load(controller.signal)
    refresh()
    window.addEventListener("focus", refresh)
    window.addEventListener("notifications-changed", refresh)
    const timer = window.setInterval(refresh, 60000)
    return () => { controller.abort(); window.clearInterval(timer); window.removeEventListener("focus", refresh); window.removeEventListener("notifications-changed", refresh) }
  }, [load])
  async function update(item: InAppNotification, read: boolean, open = false) {
    setBusy(item.id); setError(null)
    try {
      await setNotificationRead(item.id, read)
      await load()
      // Accept only the server's narrow, structured internal Candidate deep-link shape.
      if (open && item.href && /^\/candidates\/[0-9a-f-]{36}\?tab=notes(?:&[a-z]+=[0-9a-f-]{36})*$/.test(item.href)) {
        setAnchor(null); navigate(item.href)
      }
    } catch (cause) { setError(persianError(cause)) } finally { setBusy(null) }
  }
  return <>
    <IconButton aria-label={`اعلان‌ها؛ ${data && !error ? `${data.unread_count.toLocaleString("fa-IR")} خوانده‌نشده` : "شمارش در دسترس نیست"}`}
      aria-haspopup="dialog" aria-expanded={Boolean(anchor)} aria-controls={anchor ? "notifications-panel" : undefined}
      color={error ? "error" : "inherit"} onClick={event => { setAnchor(event.currentTarget); void load() }}>
      <Badge badgeContent={error ? "!" : data?.unread_count ?? 0} color={error ? "error" : "primary"} max={99}><Bell size={21} /></Badge>
    </IconButton>
    <Popover id="notifications-panel" open={Boolean(anchor)} anchorEl={anchor} onClose={() => setAnchor(null)} anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      slotProps={{ paper: { role: "dialog", "aria-label": "فهرست اعلان‌ها", sx: { width: 390, maxWidth: "calc(100vw - 24px)", maxHeight: "75svh" } } }}>
      <Stack spacing={1} sx={{ p: 2 }}><Typography variant="h6">اعلان‌های شما</Typography><Typography variant="caption" color="text.secondary">فقط در برنامه · ۱۰۰ اعلان اخیر</Typography>
        <Button size="small" onClick={() => void load()}>تازه‌سازی</Button>
        {error && <Alert severity="error">{error}</Alert>}
        {!data && !error && <CircularProgress size={20} aria-label="بارگذاری اعلان‌ها" />}
        {data && !data.items.length && <Typography variant="body2">هنوز اعلانی ندارید. اشارهٔ همکاران به شما اینجا نمایش داده می‌شود.</Typography>}
      </Stack><Divider />
      {data?.items.map(item => <Box key={item.id} sx={{ p: 2, borderBottom: 1, borderColor: "divider", bgcolor: item.read_at ? "background.paper" : "#f3f7fe", borderInlineStart: item.read_at ? "3px solid transparent" : "3px solid #1565c0" }}>
        <Typography sx={{ fontWeight: item.read_at ? 400 : 700, fontSize: 13 }}>{item.kind === "note_mention" ? "در یک یادداشت به شما اشاره شده است" : "رویداد جدید در درخواست شغلی"}</Typography>
        <Typography variant="caption" color="text.secondary">{formatJalali(item.created_at)} · {item.read_at ? "خوانده‌شده" : "خوانده‌نشده"}</Typography>
        <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
          {item.href && <Button size="small" disabled={Boolean(busy)} onClick={() => void update(item, true, true)}>مشاهدهٔ یادداشت</Button>}
          <Button size="small" disabled={Boolean(busy)} onClick={() => void update(item, !item.read_at)}>{item.read_at ? "علامت به‌عنوان خوانده‌نشده" : "علامت به‌عنوان خوانده‌شده"}</Button>
        </Stack>
      </Box>)}
    </Popover>
  </>
}
