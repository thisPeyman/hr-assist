import { useEffect, useState, type FormEvent } from "react"
import { useSearchParams } from "react-router"
import {
  Alert, Autocomplete, Box, Button, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, MenuItem, Paper, Stack, TextField, Typography,
} from "@mui/material"
import { AtSign, Pencil } from "lucide-react"
import { fetchMentionUsers, persianError, saveNote, type CandidateNote, type NotePerson, type PipelineApplication, type PipelineOwner } from "@/lib/api"
import { formatJalali } from "@/lib/jalali"

function personLabel(person: NotePerson) {
  return `${person.email ?? "نویسندهٔ پیشین"}${person.active ? "" : " (غیرفعال)"}`
}

/** Candidate aggregate and each Application's own notes share one editor/store. */
export function NotesPanel({ candidateId, notes, applications, onChanged }: {
  candidateId: string; notes: CandidateNote[]; applications: PipelineApplication[]; onChanged: () => Promise<void>
}) {
  const [params, setParams] = useSearchParams()
  const selected = params.get("application") ?? "all"
  const scope = selected === "candidate" || selected === "all" || applications.some(a => a.id === selected) ? selected : "all"
  const highlight = params.get("note")
  const [editing, setEditing] = useState<CandidateNote | "new" | null>(null)
  const [body, setBody] = useState("")
  const [target, setTarget] = useState<string>("")
  const [mentions, setMentions] = useState<PipelineOwner[]>([])
  const [users, setUsers] = useState<PipelineOwner[]>([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  useEffect(() => {
    if (!highlight) return
    document.getElementById(`note-${highlight}`)?.scrollIntoView({ block: "center" })
  }, [highlight, notes])
  useEffect(() => {
    if (!editing) return
    const controller = new AbortController()
    fetchMentionUsers(controller.signal).then(data => {
      if (!controller.signal.aborted) setUsers(data.items)
    }).catch(cause => { if (!controller.signal.aborted) setError(persianError(cause)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [editing])
  function open(note: CandidateNote | "new") {
    setEditing(note); setError(null); setSuccess(false); setLoading(true); setUsers([])
    setBody(note === "new" ? "" : note.body)
    setTarget(note === "new" ? (scope === "all" || scope === "candidate" ? "" : scope) : note.application_id ?? "")
    setMentions(note === "new" ? [] : note.mentions.filter((p): p is NotePerson & { id: string } => Boolean(p.id)).map(p => ({ id: p.id, email: p.email ?? "کاربر پیشین", active: p.active })))
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null)
    try {
      await saveNote(candidateId, target || null, editing && editing !== "new" ? editing.id : null, body.trim(), mentions.map(u => u.id))
      await onChanged()
      setEditing(null); setSuccess(true)
      window.dispatchEvent(new Event("notifications-changed"))
    } catch (cause) { setError(persianError(cause)) } finally { setBusy(false) }
  }
  const shown = notes.filter(note => scope === "all" || (scope === "candidate" ? note.application_id === null : note.application_id === scope))
  const options = [...users, ...mentions.filter(p => !users.some(u => u.id === p.id))]
  return <Stack spacing={2}>
    <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ justifyContent: "space-between", alignItems: { sm: "center" } }}>
      <Box><Typography variant="h6">یادداشت‌های تیم استخدام</Typography>
        <Typography variant="body2" color="text.secondary">نظرهای همکاران؛ جدا از رویدادهای تغییرناپذیر تاریخچه</Typography></Box>
      <Button variant="contained" onClick={() => open("new")}>یادداشت جدید</Button>
    </Stack>
    <TextField select label="نمایش یادداشت‌ها" value={scope} onChange={event => {
      const next = new URLSearchParams(params); next.set("tab", "notes"); next.delete("note")
      if (event.target.value === "all") next.delete("application"); else next.set("application", event.target.value)
      setParams(next, { replace: true })
    }}>
      <MenuItem value="all">همه؛ پرونده و تمام درخواست‌های شغلی</MenuItem>
      <MenuItem value="candidate">فقط یادداشت‌های پروندهٔ کاندیدا</MenuItem>
      {applications.map(a => <MenuItem key={a.id} value={a.id}>درخواست: {a.role_title}</MenuItem>)}
    </TextField>
    {success && <Alert severity="success" onClose={() => setSuccess(false)}>یادداشت ذخیره شد. اشاره‌ها فقط در برنامه اعلان دارند؛ ایمیلی ارسال نمی‌شود.</Alert>}
    {!shown.length && <Alert severity="info">در این نما یادداشتی ثبت نشده است. با «یادداشت جدید» بررسی خود را با تیم به اشتراک بگذارید.</Alert>}
    {shown.map(note => <Paper component="article" id={`note-${note.id}`} key={note.id} variant="outlined" sx={{ p: 2, borderInlineStart: "3px solid", borderInlineStartColor: note.application_id ? "primary.main" : "divider", bgcolor: highlight === note.id ? "#f3f7fe" : "background.paper", overflowWrap: "anywhere" }}>
      <Stack direction="row" spacing={1} sx={{ justifyContent: "space-between", alignItems: "flex-start", mb: 1 }}>
        <Chip size="small" variant="outlined" label={note.application_id ? `درخواست: ${applications.find(a => a.id === note.application_id)?.role_title ?? "فرصت شغلی پیشین"}` : "پروندهٔ کاندیدا"} sx={{ maxWidth: "100%", height: "auto", "& .MuiChip-label": { whiteSpace: "normal" } }} />
        <Button size="small" startIcon={<Pencil size={14} />} onClick={() => open(note)} aria-label={`ویرایش یادداشت ${personLabel(note.author)}`}>ویرایش</Button>
      </Stack>
      <Typography dir="auto" sx={{ whiteSpace: "pre-wrap", lineHeight: 2, fontSize: 14 }}>{note.body}</Typography>
      {note.mentions.length > 0 && <Stack direction="row" useFlexGap sx={{ flexWrap: "wrap", gap: 1, mt: 1.5 }}>{note.mentions.map(p => <Chip key={p.id} icon={<AtSign size={13} />} size="small" label={personLabel(p)} sx={{ color: p.active ? "primary.main" : "text.disabled" }} />)}</Stack>}
      <Typography variant="caption" component="p" color={note.author.active ? "text.secondary" : "text.disabled"} sx={{ mt: 1.5 }}>
        <bdi>{personLabel(note.author)}</bdi> · {formatJalali(note.created_at)}
      </Typography>
      {note.edited_at && <Typography variant="caption" color="text.secondary">ویرایش {formatJalali(note.edited_at)}{note.editor ? <> توسط <bdi>{personLabel(note.editor)}</bdi></> : null}</Typography>}
    </Paper>)}
    <Dialog open={editing !== null} onClose={busy ? undefined : () => setEditing(null)} fullWidth maxWidth="sm" aria-labelledby="note-editor-title">
      <form onSubmit={event => void submit(event)}>
        <DialogTitle id="note-editor-title">{editing === "new" ? "یادداشت جدید" : "ویرایش یادداشت"}</DialogTitle>
        <DialogContent><Stack spacing={2.5} sx={{ pt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField select label="محل ثبت" value={target} disabled={busy || editing !== "new"} onChange={e => setTarget(e.target.value)} helperText="پس از ثبت، محل یادداشت و نویسندهٔ اصلی ثابت می‌مانند.">
            <MenuItem value="">پروندهٔ کاندیدا (بدون درخواست شغلی)</MenuItem>
            {applications.map(a => <MenuItem key={a.id} value={a.id}>{a.role_title}</MenuItem>)}
          </TextField>
          <TextField autoFocus required label="متن یادداشت" multiline minRows={5} value={body} onChange={e => setBody(e.target.value)} disabled={busy} slotProps={{ htmlInput: { maxLength: 10000, dir: "auto" } }} />
          <Autocomplete multiple options={options} value={mentions} loading={loading} disabled={busy || loading} getOptionDisabled={u => !u.active}
            getOptionLabel={u => `${u.email}${u.active ? "" : " (غیرفعال)"}`} isOptionEqualToValue={(a, b) => a.id === b.id}
            noOptionsText="کاربر فعالی پیدا نشد" loadingText="بارگذاری همکاران…"
            onChange={(_, next) => {
              const added = next.filter(u => !mentions.some(p => p.id === u.id))
              const removed = mentions.filter(u => !next.some(p => p.id === u.id))
              setBody(previous => {
                let value = previous
                for (const user of removed) value = value.replaceAll(`@${user.email}`, "")
                return value + added.map(u => ` @${u.email}`).join("")
              })
              setMentions(next)
            }}
            renderInput={props => <TextField {...props} label="@اشاره به همکاران" helperText="گیرندگان را از این فهرست انتخاب کنید؛ نوشتن @ به‌تنهایی اعلان نمی‌سازد. اشارهٔ تکراری اعلان دوباره ندارد." />} />
          <Typography variant="caption" color="text.secondary">همهٔ اعضای فعال تیم می‌توانند یادداشت را ویرایش کنند؛ نام نویسنده و آخرین ویرایشگر حفظ می‌شود. اعلان‌ها فقط در برنامه‌اند.</Typography>
          {loading && <CircularProgress size={18} aria-label="بارگذاری فهرست همکاران" />}
        </Stack></DialogContent>
        <DialogActions sx={{ p: 3 }}><Button disabled={busy} onClick={() => setEditing(null)}>انصراف</Button><Button type="submit" variant="contained" disabled={busy || loading || !body.trim() || body.length > 10000}>{busy ? "در حال ذخیره…" : "ذخیرهٔ یادداشت"}</Button></DialogActions>
      </form>
    </Dialog>
  </Stack>
}
