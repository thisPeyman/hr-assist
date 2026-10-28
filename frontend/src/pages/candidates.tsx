import { useEffect, useState } from "react"
import { Link } from "react-router"
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material"
import { AppShell } from "@/components/shell"
import { fetchCandidates, persianError, type CandidateSummary } from "@/lib/api"
import { formatJalali } from "@/lib/jalali"

export function CandidateBankPage() {
  const [items, setItems] = useState<CandidateSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  useEffect(() => {
    let active = true
    fetchCandidates()
      .then((data) => {
        if (active) setItems(data)
      })
      .catch((cause) => {
        if (active) setError(persianError(cause))
      })
    return () => {
      active = false
    }
  }, [])
  const filtered = (items ?? []).filter((item) =>
    `${item.full_name} ${item.email ?? ""} ${item.headline ?? ""}`
      .toLocaleLowerCase()
      .includes(search.toLocaleLowerCase()),
  )
  return (
    <AppShell>
      <Typography variant="h4">بانک کاندیداها</Typography>
      <Typography color="text.secondary" sx={{ mt: 1, mb: 3 }}>
        هر فرد یک پروفایل دارد؛ رزومه‌های جدید و اصلاحات HR در همان پرونده جمع
        می‌شوند.
      </Typography>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Paper variant="outlined" sx={{ overflow: "hidden" }}>
        <Box sx={{ p: 2.5 }}>
          <TextField
            label="جست‌وجوی نام، ایمیل یا عنوان"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            sx={{ width: "100%", maxWidth: 440 }}
          />
        </Box>
        {items === null && !error ? (
          <Box sx={{ p: 5, textAlign: "center" }}>
            <CircularProgress />
          </Box>
        ) : (
          <TableContainer>
            <Table sx={{ minWidth: 650 }} aria-label="بانک کاندیداها">
              <TableHead>
                <TableRow>
                  <TableCell>نام و عنوان حرفه‌ای</TableCell>
                  <TableCell>ایمیل</TableCell>
                  <TableCell>تاریخ ثبت</TableCell>
                  <TableCell>پرونده</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filtered.map((item) => (
                  <TableRow key={item.id} hover>
                    <TableCell>
                      <Typography sx={{ fontWeight: 650 }} dir="auto">
                        {item.full_name}
                      </Typography>
                      <Typography
                        color="text.secondary"
                        sx={{ fontSize: 12 }}
                        dir="auto"
                      >
                        {item.headline}
                      </Typography>
                      {item.new_resume_received && (
                        <Chip
                          size="small"
                          color="info"
                          label="رزومهٔ جدید"
                          sx={{ mt: 1 }}
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography dir="auto" sx={{ fontSize: 13 }}>
                        {item.email ?? "ثبت نشده"}
                      </Typography>
                    </TableCell>
                    <TableCell>{formatJalali(item.created_at)}</TableCell>
                    <TableCell>
                      <Button component={Link} to={`/candidates/${item.id}`}>
                        مشاهدهٔ پروفایل
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
        {items && !filtered.length && (
          <Stack sx={{ p: 4, alignItems: "center" }}>
            <Typography>کاندیدایی پیدا نشد.</Typography>
            <Button component={Link} to="/resumes">
              رفتن به رزومه‌ها
            </Button>
          </Stack>
        )}
      </Paper>
    </AppShell>
  )
}
