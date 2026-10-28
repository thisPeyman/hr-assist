import { useState, type FormEvent } from "react"
import { Link, useNavigate } from "react-router"
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material"
import { useAuth } from "@/auth"
import { login, persianError, signup } from "@/lib/api"
import { Wordmark } from "@/components/shell"

export function AuthForm({ registering = false }: { registering?: boolean }) {
  const navigate = useNavigate()
  const { refresh } = useAuth()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [org, setOrg] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (registering) await signup({ email, password, org_name: org })
      else await login(email, password)
      await refresh()
      navigate("/resumes", { replace: true })
    } catch (cause) {
      setError(persianError(cause))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Box
      sx={{
        minHeight: "100svh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        p: 2,
      }}
    >
      <Stack spacing={4} sx={{ width: "100%", maxWidth: 420 }}>
        <Box sx={{ alignSelf: "center" }}>
          <Wordmark />
        </Box>
        <Paper variant="outlined" sx={{ p: { xs: 3, sm: 4 } }}>
          <Typography variant="h5">
            {registering ? "ساخت حساب سازمان" : "ورود به حساب"}
          </Typography>
          <Typography
            color="text.secondary"
            sx={{ ...{ mt: 1, mb: 3 }, fontSize: 13 }}
          >
            {registering
              ? "فضای مدیریت رزومه‌های سازمان را ایجاد کنید."
              : "برای مدیریت رزومه‌ها وارد فضای کاری خود شوید."}
          </Typography>
          <Stack
            component="form"
            onSubmit={(event) => void submit(event)}
            spacing={2.5}
          >
            {error && <Alert severity="error">{error}</Alert>}
            {registering && (
              <TextField
                label="نام سازمان"
                required
                value={org}
                onChange={(event) => setOrg(event.target.value)}
                autoComplete="organization"
              />
            )}
            <TextField
              label="ایمیل"
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              slotProps={{ htmlInput: { dir: "ltr" } }}
            />
            <TextField
              label="گذرواژه"
              type="password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={registering ? "new-password" : "current-password"}
              slotProps={{
                htmlInput: { minLength: registering ? 8 : undefined },
              }}
            />
            <Button
              variant="contained"
              size="large"
              type="submit"
              disabled={busy}
              startIcon={
                busy ? (
                  <CircularProgress size={16} color="inherit" />
                ) : undefined
              }
            >
              {busy ? "لطفاً صبر کنید…" : registering ? "ایجاد حساب" : "ورود"}
            </Button>
          </Stack>
          <Typography
            color="text.secondary"
            sx={{ ...{ mt: 3, textAlign: "center" }, fontSize: 12 }}
          >
            {registering ? "حساب دارید؟ " : "حساب ندارید؟ "}
            <Box
              component={Link}
              to={registering ? "/login" : "/signup"}
              sx={{ color: "primary.main", fontWeight: 650 }}
            >
              {registering ? "وارد شوید" : "ثبت‌نام کنید"}
            </Box>
          </Typography>
        </Paper>
      </Stack>
    </Box>
  )
}
