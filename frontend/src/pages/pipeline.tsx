import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router"
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, Divider, MenuItem, Paper, Stack, TextField, Typography,
} from "@mui/material"
import { AppShell } from "@/components/shell"
import { CreateRoleDialog, OwnerBadge, OwnerSelect } from "@/components/pipeline-controls"
import { ownerLabel, roleStatusLabels } from "@/lib/pipeline"
import {
  addToRole, assignApplication, editRole, fetchApplication, fetchCandidates,
  fetchPipelineBoard, fetchPipelineOwners, moveApplication, persianError,
  type ApplicationEvent, type CandidateSummary, type PipelineApplication,
  type PipelineBoard, type PipelineOwner,
} from "@/lib/api"
import { formatJalali } from "@/lib/jalali"

const reasons = { experience: "سابقهٔ مرتبط", skills: "مهارت‌های مورد نیاز", expectations: "انتظارات همکاری", timing: "زمان‌بندی", other: "سایر" }
const eventLabels: Record<string, string> = {
  application_added: "درخواست ایجاد شد", stage_changed: "مرحله با تصمیم HR تغییر کرد",
  application_reopened: "همان درخواست بازگشایی شد", owner_changed: "مسئول تغییر کرد",
  application_merged: "درخواست‌های هم‌فرصت ادغام شدند؛ مرحلهٔ مقصد حفظ شد",
  legacy_application_imported: "درخواست قبلی با حفظ داده‌ها منتقل شد",
  note_added: "یادداشت درخواست اضافه شد", note_edited: "یادداشت درخواست ویرایش شد",
}

export function PipelinePage() {
  const { roleId } = useParams()
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [data, setData] = useState<PipelineBoard | null>(null)
  const [owners, setOwners] = useState<PipelineOwner[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [creating, setCreating] = useState(false)
  const [expanded, setExpanded] = useState<string[]>([])
  const [dragging, setDragging] = useState<string | null>(null)
  const [moving, setMoving] = useState<PipelineApplication | null>(null)
  const [destination, setDestination] = useState("")
  const [context, setContext] = useState("")
  const [reason, setReason] = useState("")
  const [inspecting, setInspecting] = useState<PipelineApplication | null>(null)
  const [events, setEvents] = useState<ApplicationEvent[] | null>(null)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [sourcing, setSourcing] = useState(false)
  const [candidates, setCandidates] = useState<CandidateSummary[] | null>(null)
  const [candidateId, setCandidateId] = useState("")
  const [sourceRole, setSourceRole] = useState("")
  const [sourceOwner, setSourceOwner] = useState<string | null>(null)
  const [candidateSearch, setCandidateSearch] = useState("")
  const [roleTitleDraft, setRoleTitleDraft] = useState<{ id: string; value: string } | null>(null)
  const ownerFilter = params.get("owner") ?? "all"
  const roleFilter = roleId ?? params.get("role") ?? "all"
  const selectedRole = data?.roles.find(role => role.id === roleId)
  const roleTitle = roleTitleDraft?.id === selectedRole?.id ? roleTitleDraft?.value ?? "" : selectedRole?.title ?? ""
  const load = useCallback(async (signal?: AbortSignal) => {
    const [board, people] = await Promise.all([fetchPipelineBoard(signal), fetchPipelineOwners(signal)])
    if (!signal?.aborted) { setData(board); setOwners(people.items) }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    void Promise.resolve().then(() => load(controller.signal)).catch(cause => { if (!controller.signal.aborted) setError(persianError(cause)) })
    return () => controller.abort()
  }, [load])
  useEffect(() => {
    if (!inspecting) return
    const controller = new AbortController()
    fetchApplication(inspecting.id, controller.signal).then(result => {
      if (!controller.signal.aborted) setEvents(result.activity)
    }).catch(cause => { if (!controller.signal.aborted) setHistoryError(persianError(cause)) })
    return () => controller.abort()
  }, [inspecting])
  useEffect(() => {
    if (!sourcing) return
    let active = true
    fetchCandidates().then(result => { if (active) setCandidates(result) })
      .catch(cause => { if (active) setError(persianError(cause)) })
    return () => { active = false }
  }, [sourcing])
  async function mutate(action: () => Promise<unknown>, done?: () => void) {
    setBusy(true); setError(null)
    try { await action(); await load(); done?.() }
    catch (cause) { setError(persianError(cause)) }
    finally { setBusy(false) }
  }
  function startMove(application: PipelineApplication, stage = "") {
    setMoving(application); setDestination(stage); setContext(""); setReason(""); setError(null)
  }
  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value === "all") next.delete(key); else next.set(key, value)
    setParams(next)
  }
  const applications = (data?.applications ?? []).filter(application =>
    (roleFilter === "all" || application.role_id === roleFilter) &&
    (ownerFilter === "all" || (ownerFilter === "unassigned" ? !application.owner_id : application.owner_id === ownerFilter)))
  const ending = (data?.stages ?? []).filter(stage => ["rejected", "withdrawn"].includes(stage.kind))
  const live = (data?.stages ?? []).filter(stage => !["rejected", "withdrawn"].includes(stage.kind))
  const destinationStage = data?.stages.find(stage => stage.id === destination)
  const candidateList = (candidates ?? []).filter(candidate =>
    `${candidate.full_name} ${candidate.email ?? ""} ${candidate.headline ?? ""}`.toLocaleLowerCase().includes(candidateSearch.toLocaleLowerCase()))

  return <AppShell>
    <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ justifyContent: "space-between", mb: 3 }}>
      <Box><Typography variant="h4">{roleId ? selectedRole?.title ?? "فرصت شغلی" : "برد استخدام"}</Typography>
        <Typography color="text.secondary" sx={{ mt: 1, fontSize: 13 }}>هر کارت، یک کاندیدا در یک فرصت شغلی است. جابه‌جایی فقط با تصمیم شما ثبت می‌شود.</Typography>
      </Box>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
        <Button component={Link} to="/roles">فرصت‌های شغلی</Button>
        <Button variant="outlined" onClick={() => setCreating(true)}>فرصت جدید</Button>
        <Button variant="contained" disabled={!data?.roles.some(role => role.status === "open")} onClick={() => {
          setSourceRole(selectedRole?.status === "open" ? selectedRole.id : ""); setCandidateId(""); setCandidateSearch(""); setCandidates(null); setSourcing(true)
        }}>افزودن کاندیدا</Button>
      </Stack>
    </Stack>
    {error && <Alert severity="error" sx={{ mb: 2 }} action={<Button disabled={busy} onClick={() => void mutate(() => load())}>تازه‌سازی</Button>}>{error}</Alert>}
    {!data && !error && <CircularProgress aria-label="بارگذاری برد" />}
    {data && roleId && !selectedRole && <Alert severity="warning">این فرصت شغلی در سازمان شما پیدا نشد. <Button component={Link} to="/board">همهٔ فرصت‌ها</Button></Alert>}
    {selectedRole && <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
      <Stack direction={{ xs: "column", lg: "row" }} spacing={2} sx={{ alignItems: { lg: "center" } }}>
        <Chip label={roleStatusLabels[selectedRole.status]} color={selectedRole.status === "open" ? "success" : "default"} />
        <TextField label="عنوان فرصت شغلی" value={roleTitle} onChange={e => setRoleTitleDraft({ id: selectedRole.id, value: e.target.value })} slotProps={{ htmlInput: { maxLength: 200, dir: "auto" } }} />
        <Button disabled={busy || !roleTitle.trim() || roleTitle.trim() === selectedRole.title} onClick={() => void mutate(() => editRole(selectedRole.id, { title: roleTitle.trim() }))}>ذخیرهٔ عنوان</Button>
        <Box sx={{ minWidth: 230 }}><OwnerSelect owners={owners} value={selectedRole.owner_id} disabled={busy}
          label="مسئول فرصت شغلی" onChange={owner_id => void mutate(() => editRole(selectedRole.id, { owner_id }))} /></Box>
        {selectedRole.status === "draft" && <Button variant="contained" disabled={busy} onClick={() => void mutate(() => editRole(selectedRole.id, { status: "open" }))}>باز کردن فرصت شغلی</Button>}
      </Stack>
      {selectedRole.status === "draft" && <Typography color="text.secondary" sx={{ mt: 2, fontSize: 12 }}>این فرصت هنوز پیش‌نویس است؛ برای افزودن کاندیدا آن را باز کنید.</Typography>}
    </Paper>}
    {data && <>
      {!data.roles.length && <Alert severity="info" sx={{ mb: 3 }}>برای شروع، یک فرصت شغلی بسازید و آن را باز کنید. کاندیداهای بانک تا زمان افزودن به فرصت، روی برد قرار نمی‌گیرند.</Alert>}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mb: 3 }}>
        {!roleId && <TextField select label="فرصت شغلی" value={roleFilter} onChange={e => setFilter("role", e.target.value)} sx={{ minWidth: 230 }}>
          <MenuItem value="all">همهٔ فرصت‌ها</MenuItem>{data.roles.map(role => <MenuItem key={role.id} value={role.id}>{role.title} · {roleStatusLabels[role.status]}</MenuItem>)}
        </TextField>}
        <TextField select label="مسئول درخواست" value={ownerFilter} onChange={e => setFilter("owner", e.target.value)} sx={{ minWidth: 230 }}>
          <MenuItem value="all">همهٔ مسئول‌ها</MenuItem><MenuItem value="unassigned">بدون مسئول</MenuItem>
          {owners.map(owner => <MenuItem key={owner.id} value={owner.id}>{ownerLabel(owners, owner.id)}</MenuItem>)}
        </TextField>
        <Button disabled={busy} onClick={() => void mutate(() => load())}>تازه‌سازی برد</Button>
        <Typography color="text.secondary" sx={{ alignSelf: "center", fontSize: 12 }}>{applications.length.toLocaleString("fa-IR")} درخواست · برای لمس و صفحه‌کلید از «جابه‌جایی» استفاده کنید.</Typography>
      </Stack>
      {/* Explicit CSS grid direction fixes physical order independently of RTL text/Emotion flipping. */}
      <Box sx={{ overflowX: "auto", pb: 2 }} aria-label="ستون‌های مراحل استخدام">
        <Box style={{ direction: "rtl" }} sx={{ display: "grid", gridAutoFlow: "column", gridAutoColumns: "max-content", gap: 2, alignItems: "start", minHeight: 440 }}>
          {[...ending, ...live].map(stage => {
            const collapsed = ending.some(item => item.id === stage.id) && !expanded.includes(stage.id)
            const cards = applications.filter(application => application.stage_id === stage.id)
            return <Paper key={stage.id} variant="outlined" dir="rtl" onDragOver={event => { if (dragging) event.preventDefault() }}
              onDrop={event => {
                event.preventDefault()
                const id = event.dataTransfer.getData("application-id")
                const application = applications.find(item => item.id === id)
                setDragging(null)
                if (application && application.stage_id !== stage.id) startMove(application, stage.id)
              }} sx={{ width: collapsed ? 68 : 278, minHeight: 420, bgcolor: collapsed ? "#edf0f4" : "#f8fafc", borderColor: dragging ? "primary.light" : "divider" }}>
              <Box sx={{ p: collapsed ? 1 : 2, borderBottom: 1, borderColor: "divider", minHeight: 66 }}>
                {ending.some(item => item.id === stage.id) ? <Button fullWidth aria-expanded={!collapsed}
                  aria-label={`${collapsed ? "باز کردن" : "بستن"} ستون ${stage.name}؛ ${cards.length.toLocaleString("fa-IR")} درخواست`}
                  onClick={() => setExpanded(previous => previous.includes(stage.id) ? previous.filter(id => id !== stage.id) : [...previous, stage.id])}
                  sx={collapsed ? { writingMode: "vertical-rl", minWidth: 42, minHeight: 180, gap: 2 } : { justifyContent: "space-between" }}>
                  {stage.name} <Chip size="small" label={cards.length.toLocaleString("fa-IR")} />
                </Button> : <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center" }}>
                  <Typography variant="h6">{stage.name}</Typography><Chip size="small" label={cards.length.toLocaleString("fa-IR")} />
                </Stack>}
              </Box>
              {!collapsed && <Stack spacing={1.5} sx={{ p: 1.5 }}>
                {!cards.length && <Typography color="text.secondary" sx={{ p: 1, fontSize: 12 }}>درخواستی در این مرحله نیست.</Typography>}
                {cards.map(application => <Paper key={application.id} variant="outlined" draggable={!busy}
                  onDragStart={event => { event.dataTransfer.setData("application-id", application.id); event.dataTransfer.effectAllowed = "move"; setDragging(application.id) }}
                  onDragEnd={() => setDragging(null)} sx={{ p: 2, bgcolor: "background.paper", borderInlineStart: "3px solid", borderInlineStartColor: application.owner_id ? "primary.main" : "#aab6c5", overflowWrap: "anywhere" }}>
                  <Button component={Link} to={`/candidates/${application.candidate_id}`} sx={{ p: 0, fontWeight: 750, justifyContent: "start", textAlign: "start" }}><span dir="auto">{application.full_name}</span></Button>
                  <Typography dir="auto" sx={{ fontSize: 12, mt: 0.5, mb: 1 }}>{application.headline ?? "عنوان حرفه‌ای ثبت نشده"}</Typography>
                  <Typography dir="auto" color="text.secondary" sx={{ fontSize: 11, mb: 1 }}>{application.role_title}</Typography>
                   <OwnerBadge owners={owners} id={application.owner_id} />
                   <Button component={Link} to={`/candidates/${application.candidate_id}?tab=notes&application=${application.id}`} size="small" sx={{ mt: 1 }}>یادداشت‌های درخواست</Button>
                  <Stack direction="row" sx={{ mt: 1, justifyContent: "space-between" }}>
                    <Button size="small" disabled={busy} onClick={() => startMove(application)}>جابه‌جایی</Button>
                    <Button size="small" disabled={busy} onClick={() => { setEvents(null); setHistoryError(null); setInspecting(application) }}>مسئول و تاریخچه</Button>
                  </Stack>
                </Paper>)}
              </Stack>}
            </Paper>
          })}
        </Box>
      </Box>
    </>}
    <CreateRoleDialog open={creating} onClose={() => setCreating(false)} owners={owners} onCreated={role => { setCreating(false); void load(); navigate(`/roles/${role.id}`) }} />
    <Dialog open={Boolean(moving)} onClose={busy ? undefined : () => setMoving(null)} fullWidth maxWidth="sm">
      <DialogTitle>جابه‌جایی {moving?.full_name}</DialogTitle>
      <DialogContent><Stack spacing={3} sx={{ pt: 1 }}>
        {error && <Alert severity="error">{error}</Alert>}
        <Typography variant="body2" color="text.secondary">مرحلهٔ فعلی: {moving?.stage} · تنها پس از تأیید شما تغییر و در تاریخچه ثبت می‌شود.</Typography>
        <TextField select label="مرحلهٔ مقصد" value={destination} onChange={e => { setDestination(e.target.value); setReason("") }}>
          {data?.stages.filter(stage => stage.id !== moving?.stage_id).map(stage => <MenuItem key={stage.id} value={stage.id}>{stage.name}</MenuItem>)}
        </TextField>
        {destinationStage?.kind === "rejected" && <TextField select label="دلیل رد (اختیاری)" value={reason} onChange={e => setReason(e.target.value)}>
          <MenuItem value="">بدون دلیل ثبت‌شده</MenuItem>{Object.entries(reasons).map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}
        </TextField>}
        <TextField label="توضیح (اختیاری)" multiline minRows={3} value={context} onChange={e => setContext(e.target.value)} slotProps={{ htmlInput: { maxLength: 4000 } }} />
        <Typography variant="caption" color="text.secondary">هیچ ایمیلی ارسال نمی‌شود و مرحلهٔ درخواست‌های دیگر تغییر نمی‌کند.</Typography>
      </Stack></DialogContent>
      <DialogActions sx={{ p: 3 }}><Button disabled={busy} onClick={() => setMoving(null)}>انصراف</Button>
        <Button variant="contained" disabled={busy || !destination || !moving} onClick={() => moving && void mutate(() => moveApplication(moving, destination, context, reason || null), () => setMoving(null))}>{busy ? "در حال ثبت…" : "ثبت جابه‌جایی"}</Button>
      </DialogActions>
    </Dialog>
    <Dialog open={Boolean(inspecting)} onClose={busy ? undefined : () => setInspecting(null)} fullWidth maxWidth="sm">
      <DialogTitle>مسئول و تاریخچهٔ {inspecting?.full_name}</DialogTitle>
      <DialogContent><Stack spacing={2} sx={{ pt: 1 }}>
        {error && <Alert severity="error">{error}</Alert>}
        {inspecting && <OwnerSelect owners={owners} value={inspecting.owner_id} disabled={busy} onChange={owner_id => {
          void mutate(() => assignApplication(inspecting.id, owner_id), () => setInspecting({ ...inspecting, owner_id }))
        }} />}
        <Divider />
        {!events && !historyError && <CircularProgress aria-label="بارگذاری تاریخچهٔ درخواست" />}
        {historyError && <Alert severity="error">{historyError}</Alert>}
        {events?.toReversed().map(event => <Box key={event.id} sx={{ pb: 2, borderBottom: 1, borderColor: "divider" }}>
          <Typography sx={{ fontSize: 13, fontWeight: 700 }}>{eventLabels[event.event_type] ?? "رویداد درخواست"}</Typography>
          <Typography color="text.secondary" variant="caption">{formatJalali(event.created_at)} · {event.actor_user_id ? ownerLabel(owners, event.actor_user_id) : "سیستم"}</Typography>
          {typeof event.data.to_stage_name === "string" && <Typography variant="body2">{String(event.data.from_stage_name)} ← {event.data.to_stage_name}</Typography>}
          {typeof event.data.context === "string" && <Typography sx={{ whiteSpace: "pre-wrap", fontSize: 13, mt: 1 }}>{event.data.context}</Typography>}
          {typeof event.data.reason === "string" && <Typography variant="body2">دلیل: {reasons[event.data.reason as keyof typeof reasons] ?? event.data.reason}</Typography>}
        </Box>)}
      </Stack></DialogContent>
      <DialogActions><Button onClick={() => setInspecting(null)} disabled={busy}>بستن</Button></DialogActions>
    </Dialog>
    <Dialog open={sourcing} onClose={busy ? undefined : () => setSourcing(false)} fullWidth maxWidth="sm">
      <DialogTitle>افزودن کاندیدا از بانک</DialogTitle>
      <DialogContent><Stack spacing={3} sx={{ pt: 1 }}>
        {error && <Alert severity="error">{error}</Alert>}
        <Typography variant="body2" color="text.secondary">افزودن مجدد، درخواست دومی نمی‌سازد. درخواست پایان‌یافته با حفظ مسئول و تاریخچه، به «شناسایی‌شده» بازمی‌گردد.</Typography>
        <TextField select label="فرصت شغلی باز" value={sourceRole} onChange={e => setSourceRole(e.target.value)}>
          {data?.roles.filter(role => role.status === "open").map(role => <MenuItem key={role.id} value={role.id}>{role.title}</MenuItem>)}
        </TextField>
        <TextField label="پیدا کردن در بانک" value={candidateSearch} onChange={e => setCandidateSearch(e.target.value)} />
        {!candidates && <CircularProgress aria-label="بارگذاری بانک کاندیداها" />}
        {candidates && !candidateList.length && <Alert severity="info">کاندیدایی پیدا نشد. <Button component={Link} to="/upload">بارگذاری رزومه</Button></Alert>}
        <TextField select label="کاندیدا" value={candidateId} onChange={e => setCandidateId(e.target.value)}>
          {candidateList.map(candidate => <MenuItem key={candidate.id} value={candidate.id}>{candidate.full_name} · {candidate.email ?? candidate.headline ?? "بدون عنوان"}</MenuItem>)}
        </TextField>
        <OwnerSelect owners={owners} value={sourceOwner} onChange={setSourceOwner} label="مسئول درخواست جدید (اختیاری)" />
      </Stack></DialogContent>
      <DialogActions sx={{ p: 3 }}><Button disabled={busy} onClick={() => setSourcing(false)}>انصراف</Button>
        <Button variant="contained" disabled={busy || !sourceRole || !candidateId} onClick={() => void mutate(() => addToRole(sourceRole, candidateId, sourceOwner), () => setSourcing(false))}>{busy ? "در حال ثبت…" : "افزودن یا بازگشایی"}</Button>
      </DialogActions>
    </Dialog>
  </AppShell>
}
