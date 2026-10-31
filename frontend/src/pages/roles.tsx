import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate } from "react-router"
import { Alert, Box, Button, Chip, CircularProgress, Paper, Stack, Typography } from "@mui/material"
import { AppShell } from "@/components/shell"
import { CreateRoleDialog, OwnerBadge } from "@/components/pipeline-controls"
import { roleStatusLabels } from "@/lib/pipeline"
import { fetchRoles, fetchPipelineOwners, persianError, type PipelineRole, type PipelineOwner } from "@/lib/api"

export function RolesPage() {
  const [roles, setRoles] = useState<PipelineRole[] | null>(null)
  const [owners, setOwners] = useState<PipelineOwner[]>([])
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const load = useCallback(async (signal?: AbortSignal) => {
    const [roles, owners] = await Promise.all([fetchRoles(signal), fetchPipelineOwners(signal)])
    if (!signal?.aborted) { setRoles(roles.items); setOwners(owners.items); setError(null) }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    void Promise.resolve().then(() => load(controller.signal)).catch(cause => { if (!controller.signal.aborted) setError(persianError(cause)) })
    return () => controller.abort()
  }, [load])
  return <AppShell>
    <Stack direction="row" sx={{ justifyContent: "space-between", gap: 2, mb: 3 }}>
      <Box><Typography variant="h4">فرصت‌های شغلی</Typography><Typography color="text.secondary" sx={{ mt: 1 }}>پیش‌نویس بسازید، مسئول مشخص کنید و برای شروع جذب آن را باز کنید.</Typography></Box>
      <Button variant="contained" onClick={() => setCreating(true)}>فرصت جدید</Button>
    </Stack>
    {error && <Alert severity="error">{error} <Button onClick={() => void load().catch(cause => setError(persianError(cause)))}>تلاش دوباره</Button></Alert>}
    {!roles && !error && <CircularProgress aria-label="بارگذاری فرصت‌های شغلی" />}
    {roles?.length === 0 && <Alert severity="info">هنوز فرصت شغلی‌ای ندارید. از «فرصت جدید» شروع کنید.</Alert>}
    <Stack spacing={2}>{roles?.map(role => <Paper variant="outlined" key={role.id} sx={{ p: 3 }}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ justifyContent: "space-between", alignItems: { sm: "center" } }}>
        <Box><Button component={Link} to={`/roles/${role.id}`} sx={{ p: 0, fontSize: 18, fontWeight: 750 }}><span dir="auto">{role.title}</span></Button>
          <Stack direction="row" spacing={1} sx={{ mt: 1 }}><Chip size="small" label={roleStatusLabels[role.status]} color={role.status === "open" ? "success" : "default"} /><OwnerBadge owners={owners} id={role.owner_id} /></Stack>
        </Box>
        <Button component={Link} to={`/roles/${role.id}`} variant="outlined">برد و تنظیمات فرصت</Button>
      </Stack>
    </Paper>)}</Stack>
    <CreateRoleDialog open={creating} onClose={() => setCreating(false)} owners={owners} onCreated={role => { setCreating(false); navigate(`/roles/${role.id}`) }} />
  </AppShell>
}
