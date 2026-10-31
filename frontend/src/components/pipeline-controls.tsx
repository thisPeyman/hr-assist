import { useEffect, useState } from "react"
import { Link } from "react-router"
import {
  Alert, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, MenuItem, Stack, TextField, Typography,
} from "@mui/material"
import {
  addToRole, createRole, fetchRoles, fetchPipelineOwners, persianError,
  type PipelineOwner, type PipelineRole,
} from "@/lib/api"
import { ownerLabel } from "@/lib/pipeline"

export function OwnerSelect({ owners, value, onChange, disabled = false, label = "مسئول" }: {
  owners: PipelineOwner[]; value: string | null; onChange: (id: string | null) => void; disabled?: boolean; label?: string
}) {
  return <TextField select fullWidth label={label} value={value ?? ""} disabled={disabled}
    onChange={event => onChange(event.target.value || null)}>
    <MenuItem value="">بدون مسئول</MenuItem>
    {value && !owners.some(owner => owner.id === value) && <MenuItem value={value} disabled>مسئول پیشین</MenuItem>}
    {owners.map(owner => <MenuItem key={owner.id} value={owner.id} disabled={!owner.active}>
      <span dir="auto">{ownerLabel(owners, owner.id)}</span>
    </MenuItem>)}
  </TextField>
}

export function OwnerBadge({ owners, id }: { owners: PipelineOwner[]; id: string | null }) {
  return <Chip size="small" variant="outlined" label={ownerLabel(owners, id)}
    sx={{ maxWidth: "100%", color: id && owners.some(o => o.id === id && !o.active) ? "text.disabled" : "text.secondary", fontSize: 11 }} />
}

export function CreateRoleDialog({ open, onClose, onCreated, owners }: {
  open: boolean; onClose: () => void; onCreated: (role: PipelineRole) => void; owners: PipelineOwner[]
}) {
  const [title, setTitle] = useState("")
  const [owner, setOwner] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return <Dialog open={open} onClose={busy ? undefined : onClose} fullWidth maxWidth="sm">
    <form onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError(null)
      try { const role = await createRole(title.trim(), owner); setTitle(""); setOwner(null); onCreated(role) }
      catch (cause) { setError(persianError(cause)) } finally { setBusy(false) }
    }}>
      <DialogTitle>فرصت شغلی جدید</DialogTitle>
      <DialogContent><Stack spacing={3} sx={{ pt: 1 }}>
        {error && <Alert severity="error">{error}</Alert>}
        <Typography color="text.secondary" variant="body2">ابتدا پیش‌نویس بسازید؛ پس از باز کردن فرصت شغلی، کاندیداها را به آن اضافه کنید.</Typography>
        <TextField autoFocus required label="عنوان فرصت شغلی" value={title} onChange={e => setTitle(e.target.value)} slotProps={{ htmlInput: { maxLength: 200, dir: "auto" } }} />
        <OwnerSelect owners={owners} value={owner} onChange={setOwner} disabled={busy} />
      </Stack></DialogContent>
      <DialogActions sx={{ p: 3 }}><Button disabled={busy} onClick={onClose}>انصراف</Button>
        <Button type="submit" variant="contained" disabled={busy || !title.trim()}>{busy ? "در حال ساخت…" : "ساخت پیش‌نویس"}</Button>
      </DialogActions>
    </form>
  </Dialog>
}

/** Candidate-detail sourcing shares the same canonical/reopen endpoint as the board. */
export function AddToRoleButton({ candidateId, onAdded }: { candidateId: string; onAdded: () => void }) {
  const [open, setOpen] = useState(false)
  const [roles, setRoles] = useState<PipelineRole[]>([])
  const [owners, setOwners] = useState<PipelineOwner[]>([])
  const [role, setRole] = useState("")
  const [owner, setOwner] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    Promise.all([fetchRoles(controller.signal), fetchPipelineOwners(controller.signal)]).then(([r, o]) => {
      if (!controller.signal.aborted) { setRoles(r.items.filter(item => item.status === "open")); setOwners(o.items) }
    }).catch(cause => { if (!controller.signal.aborted) setError(persianError(cause)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [open])
  return <>
    <Button variant="contained" onClick={() => { setOpen(true); setSuccess(false); setRole(""); setLoading(true); setError(null) }}>افزودن به فرصت شغلی</Button>
    {success && <Alert severity="success">درخواست در همان پرونده ثبت یا بازگشایی شد. <Button component={Link} to={`/roles/${role}`}>مشاهدهٔ برد</Button></Alert>}
    <Dialog open={open} onClose={busy ? undefined : () => setOpen(false)} fullWidth maxWidth="sm">
      <DialogTitle>افزودن کاندیدا به فرصت شغلی</DialogTitle>
      <DialogContent><Stack spacing={3} sx={{ pt: 1 }}>
        {loading && <CircularProgress aria-label="بارگذاری فرصت‌های شغلی" />}
        {error && <Alert severity="error">{error}</Alert>}
        <Typography variant="body2" color="text.secondary">درخواست تکراری ساخته نمی‌شود. درخواست پایان‌یافتهٔ همین فرد در همین فرصت شغلی، با حفظ تاریخچه به «شناسایی‌شده» بازمی‌گردد؛ مسئول قبلی حفظ می‌شود.</Typography>
        {!loading && !roles.length && <Alert severity="info">فرصت شغلی بازی وجود ندارد. <Button component={Link} to="/roles">مدیریت فرصت‌ها</Button></Alert>}
        <TextField select label="فرصت شغلی باز" value={role} onChange={e => setRole(e.target.value)}>
          {roles.map(item => <MenuItem key={item.id} value={item.id}>{item.title}</MenuItem>)}
        </TextField>
        <OwnerSelect owners={owners} value={owner} onChange={setOwner} label="مسئول درخواست جدید (اختیاری)" />
      </Stack></DialogContent>
      <DialogActions sx={{ p: 3 }}><Button disabled={busy} onClick={() => setOpen(false)}>انصراف</Button>
        <Button variant="contained" disabled={busy || loading || !role} onClick={async () => {
          setBusy(true); setError(null)
          try { await addToRole(role, candidateId, owner); setOpen(false); setSuccess(true); onAdded() }
          catch (cause) { setError(persianError(cause)) } finally { setBusy(false) }
        }}>{busy ? "در حال ثبت…" : "افزودن یا بازگشایی"}</Button>
      </DialogActions>
    </Dialog>
  </>
}
