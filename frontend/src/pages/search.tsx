import { useEffect, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router"
import { Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Divider, MenuItem, Paper, Snackbar, Stack, TextField, Typography } from "@mui/material"
import { ArrowUpRight, BriefcaseBusiness, Columns3, MapPin, Plus, Search, SlidersHorizontal } from "lucide-react"
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

  return <>
    <Stack spacing={1.5}>
      <Paper variant="outlined" component="header" sx={{ p: { xs: 1.5, sm: 2 } }}>
        <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "flex-start", gap: 1, mb: 0.25 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography component="h1" sx={{ fontSize: { xs: 16, sm: 18 }, fontWeight: 750, lineHeight: 1.7 }}>چه کسی را جست‌وجو می‌کنید؟</Typography>
          </Box>
          <Button component={Link} to="/board" size="small" startIcon={<Columns3 size={16} />} sx={{ flexShrink: 0, px: 0.75, fontSize: 12 }}>برد استخدام</Button>
        </Stack>
        <Typography color="text.secondary" sx={{ mb: 1.5, fontSize: 12 }}>تمام بانک کاندیداها؛ حتی بدون درخواست شغلی فعال</Typography>
        <Box component="form" onSubmit={submit} sx={{ display: "flex", gap: 1, alignItems: "flex-start" }}>
          <TextField fullWidth size="small" label="جست‌وجوی کاندیدا" placeholder="نام، مهارت یا سابقه؛ مثلاً vahid یا توسعه‌دهنده React" value={query} onChange={e => setQuery(e.target.value)} slotProps={{ htmlInput: { maxLength: 1000, dir: "auto" } }} sx={{ minWidth: 0 }} />
          <Button type="submit" variant="contained" size="small" disabled={!query.trim()} startIcon={<Search size={16} />} sx={{ height: 40, px: 1.5, flexShrink: 0 }}>جست‌وجو</Button>
        </Box>
      </Paper>

      {started ? <Paper variant="outlined" sx={{ p: 1.5 }}>
        <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", gap: 1, mb: 1.25 }}>
          <Stack direction="row" spacing={0.75} sx={{ alignItems: "center" }}>
            <SlidersHorizontal size={16} />
            <Typography sx={{ fontWeight: 650, fontSize: 13 }}>برداشت از جست‌وجو</Typography>
          </Stack>
          <Button size="small" startIcon={<Plus size={16} />} onClick={() => setEditing({ id: crypto.randomUUID().replaceAll("-", "").slice(0, 16), field: "skill", op: "contains", value: "", constraint_softness: 0 })}>افزودن شرط</Button>
        </Stack>
        {dsl.filters.length > 0 ? <Stack direction="row" useFlexGap sx={{ flexWrap: "wrap", gap: 0.75, mb: 1.5 }}>
          {dsl.filters.map(filter => <Chip key={filter.id} size="small" label={filterLabel(filter)} color={filter.op === "ne" || filter.op === "not_contains" ? "warning" : "primary"} variant="outlined" onClick={() => setEditing(filter)} onDelete={() => update({ ...dsl, filters: dsl.filters.filter(f => f.id !== filter.id) })} />)}
        </Stack> : null}
        <Box sx={{ display: "flex", gap: 1, alignItems: "flex-start" }}>
          <TextField size="small" fullWidth label="واژه‌های جست‌وجو" value={dsl.semantic_query} onChange={e => setDSL({ ...dsl, semantic_query: e.target.value })} onKeyDown={e => { if (e.key === "Enter") update(dsl) }} sx={{ minWidth: 0 }} />
          <Button size="small" variant="outlined" aria-label="اجرای شرط‌ها و واژه‌ها" onClick={() => update(dsl)} sx={{ height: 40, flexShrink: 0 }}>اعمال</Button>
        </Box>
        <Typography sx={{ mt: 0.75, fontSize: 11 }} color="text.secondary">
          عدد و نفی را در شرط‌ها نگه دارید.{mode === "sql" ? " ویرایش دستی؛ بدون فراخوانی مدل." : " برای ویرایش هر شرط، روی آن بزنید."}
        </Typography>
      </Paper> : null}
      {warnings.map(code => <Alert severity="warning" key={code}>{searchWarning[code] ?? "بخشی از جست‌وجو در دسترس نیست."}</Alert>)}
      {error ? <Alert severity="error">{error}</Alert> : null}
      <Box aria-live="polite" aria-busy={loading}>
        {loading ? <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 2 }}><CircularProgress size={20} aria-label="در حال جست‌وجو" /><Typography>در حال یافتن کاندیداها…</Typography></Stack> : null}
        {items.length ? <Paper variant="outlined"><Stack divider={<Divider />}>
          {items.map(item => <Box key={item.id} sx={{
            px: { xs: 1.5, sm: 2 }, py: 1.5,
            display: "grid", alignItems: "center",
            gridTemplateColumns: { xs: "minmax(0, 1fr) auto", sm: "minmax(0, 1.15fr) minmax(0, 1fr) auto" },
            columnGap: 2, rowGap: 1,
          }}>
            <Box sx={{ minWidth: 0 }}>
              <Typography component={Link} to={`/candidates/${item.id}`} sx={{
                display: "block", width: "fit-content", maxWidth: "100%",
                fontWeight: 750, fontSize: 14, color: "primary.main", textDecoration: "none",
                "&:hover": { textDecoration: "underline" },
                "&:focus-visible": { outline: "2px solid", outlineColor: "primary.main", outlineOffset: 3 },
              }} dir="auto">{item.full_name}</Typography>
              <Typography noWrap title={item.headline ?? undefined} sx={{ mt: 0.25, fontSize: 12 }} color="text.secondary"><bdi>{item.headline ?? "عنوان حرفه‌ای ثبت نشده"}</bdi></Typography>
            </Box>
            <Stack direction="row" useFlexGap sx={{
              gridColumn: { xs: "1 / -1", sm: "auto" }, gridRow: { xs: 2, sm: "auto" },
              minWidth: 0, flexWrap: "wrap", columnGap: 2, rowGap: 0.5, color: "text.secondary",
            }}>
              <Stack direction="row" spacing={0.5} sx={{ alignItems: "center", minWidth: 0, maxWidth: "100%" }}>
                <MapPin size={13} aria-hidden="true" style={{ flexShrink: 0 }} />
                <Typography noWrap title={item.location ?? undefined} dir="auto" sx={{ fontSize: 12 }}>{item.location ?? "محل سکونت نامشخص"}</Typography>
              </Stack>
              <Stack direction="row" spacing={0.5} sx={{ alignItems: "center" }} title="سابقهٔ قابل محاسبه از تاریخ‌های رزومه">
                <BriefcaseBusiness size={13} aria-hidden="true" style={{ flexShrink: 0 }} />
                <Typography sx={{ fontSize: 12 }}>{item.years_experience_total === null ? "سابقه نامشخص" : `${item.years_experience_total.toLocaleString("fa-IR")} سال سابقهٔ قابل محاسبه`}</Typography>
              </Stack>
            </Stack>
            <Button component={Link} to={`/candidates/${item.id}`} size="small" endIcon={<ArrowUpRight size={14} />} sx={{ gridColumn: { xs: 2, sm: 3 }, gridRow: { xs: 1, sm: "auto" }, minWidth: 0, px: 0.75, fontSize: 12 }}>پرونده</Button>
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
  </>
}
