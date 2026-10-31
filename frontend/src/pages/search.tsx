import { useEffect, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router"
import { Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Divider, MenuItem, Paper, Snackbar, Stack, TextField, Typography } from "@mui/material"
import { ArrowUpRight, Columns3, Plus, Search, SlidersHorizontal } from "lucide-react"
import { AppShell } from "@/components/shell"
import { ApiError, persianError } from "@/lib/api"
import { enumLabels, fieldLabels, filterLabel, opLabels, searchWarning, streamSearch, type SearchCandidate, type SearchDSL, type SearchFilter } from "@/lib/search"

const emptyDSL: SearchDSL = { filters: [], semantic_query: "" }

function FilterEditor({ filter, onClose, onSave }: { filter: SearchFilter; onClose: () => void; onSave: (value: SearchFilter) => void }) {
  const [value, setValue] = useState(filter)
  const numeric = value.field === "years_experience_total"
  const exact = ["stage", "role_status", "role_id", "owner_id"].includes(value.field)
  const operators: SearchFilter["op"][] = numeric ? ["gte", "lte", "gt", "lt", "eq", "ne"] : exact ? ["eq", "ne"] : ["contains", "not_contains", "eq", "ne"]
  const enums = value.field === "stage" ? ["sourced", "screening", "interview", "offer", "hired", "rejected", "withdrawn"] : value.field === "role_status" ? ["draft", "open", "paused", "closed"] : null
  return <Dialog open onClose={onClose} fullWidth maxWidth="sm">
    <DialogTitle>ویرایش شرط جست‌وجو</DialogTitle>
    <DialogContent><Stack spacing={2} sx={{ pt: 1 }}>
      <TextField select label="فیلد" value={value.field} onChange={e => {
        const field = e.target.value as SearchFilter["field"]
        setValue({ ...value, field, op: field === "years_experience_total" ? "gte" : ["stage", "role_status", "role_id", "owner_id"].includes(field) ? "eq" : "contains", value: "" })
      }}>{Object.entries(fieldLabels).map(([field, label]) => <MenuItem key={field} value={field}>{label}</MenuItem>)}</TextField>
      <TextField select label="رابطه" value={value.op} onChange={e => setValue({ ...value, op: e.target.value as SearchFilter["op"] })}>
        {operators.map(op => <MenuItem key={op} value={op}>{opLabels[op]}</MenuItem>)}
      </TextField>
      <TextField select={Boolean(enums)} label="مقدار" value={value.value} onChange={e => setValue({ ...value, value: e.target.value })}
        helperText={numeric ? "فقط سال‌های قابل محاسبه از تاریخ‌های کامل؛ سابقهٔ نامشخص شامل نمی‌شود." : value.field.endsWith("_id") ? "شناسهٔ دقیق فرصت یا کاربر را وارد کنید." : "مقدار مطابق پروفایل؛ فارسی یا انگلیسی"}>
        {enums?.map(item => <MenuItem key={item} value={item}>{enumLabels[item]}</MenuItem>)}
      </TextField>
      <TextField select label="امکان کنار گذاشتن در جست‌وجوی خالی" value={value.constraint_softness} onChange={e => setValue({ ...value, constraint_softness: Number(e.target.value) })}>
        <MenuItem value={0}>هرگز؛ شرط قطعی</MenuItem><MenuItem value={0.3}>کم</MenuItem><MenuItem value={0.6}>متوسط</MenuItem><MenuItem value={1}>زیاد؛ اولین پیشنهاد برای حذف</MenuItem>
        {![0, 0.3, 0.6, 1].includes(value.constraint_softness) ? <MenuItem value={value.constraint_softness}>برداشت اولیه ({value.constraint_softness.toLocaleString("fa-IR")})</MenuItem> : null}
      </TextField>
      <Alert severity="info">تغییر شرط‌ها فقط روی جست‌وجو اثر دارد؛ مرحلهٔ هیچ کاندیدایی تغییر نمی‌کند.</Alert>
    </Stack></DialogContent>
    <DialogActions><Button onClick={onClose}>انصراف</Button><Button variant="contained" disabled={!value.value.trim()} onClick={() => onSave(value)}>اعمال و جست‌وجو</Button></DialogActions>
  </Dialog>
}

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const initial = params.get("q") ?? ""
  const [query, setQuery] = useState(initial)
  const [dsl, setDSL] = useState<SearchDSL>(emptyDSL)
  const [items, setItems] = useState<SearchCandidate[]>([])
  const [loading, setLoading] = useState(false)
  const [started, setStarted] = useState(false)
  const [mode, setMode] = useState("")
  const [warnings, setWarnings] = useState<string[]>([])
  const [toast, setToast] = useState("")
  const [error, setError] = useState("")
  const [relax, setRelax] = useState<string | null>(null)
  const [editing, setEditing] = useState<SearchFilter | null>(null)
  const controller = useRef<AbortController | null>(null)
  const sequence = useRef(0)

  async function run(input: { query: string } | { dsl: SearchDSL; relax?: boolean }) {
    controller.current?.abort()
    const abort = new AbortController()
    controller.current = abort
    const request = ++sequence.current
    if ("query" in input) setDSL(emptyDSL)
    setLoading(true); setStarted(true); setItems([]); setError(""); setWarnings([]); setRelax(null)
    try {
      await streamSearch(input, abort.signal, event => {
        if (abort.signal.aborted || sequence.current !== request) return
        if (event.type === "filters") {
          setDSL(event.dsl); setMode(event.mode); setWarnings(event.warnings)
          if (event.warnings.includes("SEARCH_PARSE_FAILED")) setToast(searchWarning.SEARCH_PARSE_FAILED)
        } else if (event.type === "candidate") setItems(old => [...old, event.candidate])
        else if (event.type === "warning") setWarnings(old => old.includes(event.code) ? old : [...old, event.code])
        else setRelax(event.relax_filter_id)
      })
    } catch (e) {
      if (!abort.signal.aborted) setError(e instanceof ApiError && e.code === "INVALID_SEARCH" ? "شرط جست‌وجو معتبر نیست. ویژگی‌های حساس قابل جست‌وجو نیستند؛ عددها و نفی را در شرط‌ها وارد کنید." : persianError(e))
    } finally { if (!abort.signal.aborted) setLoading(false) }
  }
  useEffect(() => {
    if (initial.trim()) { setQuery(initial); void run({ query: initial }) }
    return () => controller.current?.abort()
    // URL submissions, not typing, initiate a new parse.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    if (query.trim() === initial) void run({ query: query.trim() })
    else setParams({ q: query.trim() })
  }
  function update(next: SearchDSL) { setDSL(next); void run({ dsl: next }) }
  const softest = dsl.filters.find(f => f.id === relax)

  return <AppShell>
    <Stack spacing={3}>
      <Paper variant="outlined" component="header" sx={{ p: { xs: 2, sm: 3 }, borderTop: "4px solid", borderTopColor: "primary.main" }}>
        <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", gap: 2, mb: 2 }}>
          <Box><Typography variant="h5" sx={{ fontWeight: 750 }}>چه کسی را جست‌وجو می‌کنید؟</Typography><Typography color="text.secondary" sx={{ mt: 1, fontSize: 13 }}>تمام بانک کاندیداها؛ حتی بدون درخواست شغلی فعال</Typography></Box>
          <Button component={Link} to="/board" startIcon={<Columns3 size={18} />} sx={{ flexShrink: 0 }}>برد استخدام</Button>
        </Stack>
        <Box component="form" onSubmit={submit} sx={{ display: "flex", gap: 1 }}>
          <TextField fullWidth label="جست‌وجوی کاندیدا" placeholder="مهندس بک‌اند، فین‌تک، دست‌کم ۵ سال سابقه، بدون Java" value={query} onChange={e => setQuery(e.target.value)} slotProps={{ htmlInput: { maxLength: 1000, dir: "auto" } }} />
          <Button type="submit" variant="contained" disabled={!query.trim()} startIcon={<Search size={18} />}>جست‌وجو</Button>
        </Box>
      </Paper>

      {started ? <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 2 }}><SlidersHorizontal size={18} /><Typography sx={{ fontWeight: 650 }}>برداشت از جست‌وجو</Typography><Typography color="text.secondary" sx={{ fontSize: 12 }}>برای اصلاح، روی شرط بزنید</Typography></Stack>
        <Stack direction="row" useFlexGap sx={{ flexWrap: "wrap", gap: 1 }}>
          {dsl.filters.map(filter => <Chip key={filter.id} label={filterLabel(filter)} color={filter.op === "ne" || filter.op === "not_contains" ? "warning" : "primary"} variant="outlined" onClick={() => setEditing(filter)} onDelete={() => update({ ...dsl, filters: dsl.filters.filter(f => f.id !== filter.id) })} />)}
          <Button size="small" startIcon={<Plus size={16} />} onClick={() => setEditing({ id: crypto.randomUUID().replaceAll("-", "").slice(0, 16), field: "skill", op: "contains", value: "", constraint_softness: 0 })}>افزودن شرط</Button>
        </Stack>
        <TextField sx={{ mt: 2 }} size="small" fullWidth label="مفهوم مثبت برای جست‌وجوی واژه‌ای پس از ویرایش" value={dsl.semantic_query} onChange={e => setDSL({ ...dsl, semantic_query: e.target.value })} onKeyDown={e => { if (e.key === "Enter") update(dsl) }} helperText="عدد و نفی را در شرط‌ها نگه دارید. ویرایش‌ها بدون پردازش هوشمند، فقط در پایگاه داده اجرا می‌شوند." />
        <Button size="small" onClick={() => update(dsl)}>اجرای شرط‌ها و واژه‌ها</Button>
        {mode === "sql" ? <Typography sx={{ mt: 1, fontSize: 12 }} color="text.secondary">حالت اصلاح دستی؛ بدون فراخوانی مدل</Typography> : null}
      </Paper> : null}
      {warnings.map(code => <Alert severity="warning" key={code}>{searchWarning[code] ?? "بخشی از جست‌وجو در دسترس نیست."}</Alert>)}
      {error ? <Alert severity="error">{error}</Alert> : null}
      <Box aria-live="polite" aria-busy={loading}>
        {loading ? <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 2 }}><CircularProgress size={20} aria-label="در حال جست‌وجو" /><Typography>در حال یافتن کاندیداها…</Typography></Stack> : null}
        {items.length ? <Paper variant="outlined"><Stack divider={<Divider />}>
          {items.map(item => <Box key={item.id} sx={{ p: 2.5, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
            <Box sx={{ minWidth: 0 }}><Typography component={Link} to={`/candidates/${item.id}`} sx={{ fontWeight: 750, color: "primary.main", textDecoration: "none" }} dir="auto">{item.full_name}</Typography><Typography dir="auto" sx={{ mt: 0.75 }}>{item.headline ?? "عنوان حرفه‌ای ثبت نشده"}</Typography><Typography color="text.secondary" sx={{ mt: 0.5, fontSize: 12 }} dir="auto">{item.location ?? "محل سکونت نامشخص"} · {item.years_experience_total === null ? "سابقهٔ قابل محاسبه نامشخص" : `${item.years_experience_total.toLocaleString("fa-IR")} سال سابقهٔ قابل محاسبه`}</Typography></Box>
            <Button component={Link} to={`/candidates/${item.id}`} endIcon={<ArrowUpRight size={16} />} sx={{ flexShrink: 0 }}>پرونده</Button>
          </Box>)}
        </Stack></Paper> : started && !loading && !error ? <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
          <Typography sx={{ fontWeight: 700 }}>کاندیدایی با این شرط‌ها پیدا نشد</Typography><Typography color="text.secondary" sx={{ my: 1 }}>شرط‌ها را اصلاح کنید یا یکی از شرط‌های قابل انعطاف را کنار بگذارید.</Typography>
          {softest ? <Button variant="outlined" onClick={() => void run({ dsl, relax: true })}>کنار گذاشتن «{filterLabel(softest)}»</Button> : <Typography sx={{ fontSize: 12 }}>شرط قابل انعطافی انتخاب نشده است.</Typography>}
        </Paper> : !started ? <Typography color="text.secondary">جست‌وجو را با مهارت، صنعت یا سابقه شروع کنید. تصمیم استخدام و تغییر مرحله همیشه با شماست.</Typography> : null}
        {items.length && !loading ? <Typography sx={{ mt: 1, fontSize: 12 }} color="text.secondary">{items.length.toLocaleString("fa-IR")} نتیجه (حداکثر ۵۰)؛ ترتیب جست‌وجو ارزیابی شایستگی یا توصیهٔ استخدام نیست.</Typography> : null}
      </Box>
    </Stack>
    {editing ? <FilterEditor key={editing.id} filter={editing} onClose={() => setEditing(null)} onSave={value => { setEditing(null); update({ ...dsl, filters: [...dsl.filters.filter(f => f.id !== value.id), value] }) }} /> : null}
    <Snackbar open={Boolean(toast)} autoHideDuration={10000} onClose={() => setToast("")} message={toast} />
  </AppShell>
}
