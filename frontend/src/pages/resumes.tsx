import { useEffect, useState, type FormEvent } from "react"
import { Link, useNavigate } from "react-router"
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material"
import {
  Download,
  Eye,
  FileText,
  Pencil,
  RefreshCw,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react"
import { AppShell } from "@/components/shell"
import {
  deleteResume,
  fetchResume,
  fetchResumes,
  persianError,
  updateResume,
  type ResumeDetail,
  type ResumeEdit,
  type ResumeItem,
} from "@/lib/api"
import { formatJalali } from "@/lib/jalali"
import { formatDateRange, formatResumeDate, parseStatusLabel } from "@/lib/profile"
import { reviewProfile } from "@/lib/review"

function Status({ item }: { item: ResumeItem }) {
  const color =
    item.status === "needs_review"
      ? "warning"
      : ["failed", "not_a_resume"].includes(item.status)
        ? "error"
        : item.status === "pending"
          ? "info"
          : "success"
  return (
    <Chip
      size="small"
      color={color}
      variant="outlined"
      label={parseStatusLabel(item.status)}
    />
  )
}

export function Preview({ jobId }: { jobId: string }) {
  const [page, setPage] = useState(0)
  const [pages, setPages] = useState(1)
  const [image, setImage] = useState<{ page: number; url: string } | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    let url: string | undefined
    fetch(`/api/review/${jobId}/preview?page=${page}`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("preview unavailable")
        const blob = await response.blob()
        if (controller.signal.aborted) return
        url = URL.createObjectURL(blob)
        setPages(Number(response.headers.get("X-Page-Count")) || 1)
        setImage({ page, url })
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true)
      })
    return () => {
      controller.abort()
      if (url) URL.revokeObjectURL(url)
    }
  }, [jobId, page])
  if (failed)
    return (
      <Alert severity="info">
        پیش‌نمایش این قالب در دسترس نیست؛ فایل اصلی را دریافت کنید.
      </Alert>
    )
  return (
    <Stack spacing={2}>
      <Box
        sx={{
          minHeight: 180,
          border: 1,
          borderColor: "divider",
          borderRadius: 1,
          overflow: "hidden",
          bgcolor: "#f8fafc",
          display: "grid",
          placeItems: "center",
        }}
      >
        {image?.page === page ? (
          <Box
            component="img"
            src={image.url}
            alt={`صفحهٔ ${(page + 1).toLocaleString("fa-IR")} رزومه`}
            sx={{ width: "100%", maxHeight: 650, objectFit: "contain" }}
          />
        ) : (
          <CircularProgress size={24} />
        )}
      </Box>
      {pages > 1 && (
        <Stack
          direction="row"
          sx={{ justifyContent: "space-between", alignItems: "center" }}
        >
          <Button
            size="small"
            disabled={page === 0}
            onClick={() => setPage((old) => old - 1)}
          >
            صفحهٔ قبل
          </Button>
          <Typography sx={{ fontSize: 12 }}>
            {(page + 1).toLocaleString("fa-IR")} از{" "}
            {pages.toLocaleString("fa-IR")}
          </Typography>
          <Button
            size="small"
            disabled={page + 1 >= pages}
            onClick={() => setPage((old) => old + 1)}
          >
            صفحهٔ بعد
          </Button>
        </Stack>
      )}
    </Stack>
  )
}

export function Profile({ detail }: { detail: ResumeDetail }) {
  const profile = reviewProfile(detail.profile)
  if (!detail.profile)
    return (
      <Alert severity="info">
        هنوز اطلاعات ساختاریافته‌ای از این رزومه استخراج نشده است. می‌توانید
        اطلاعات را به‌صورت دستی ثبت کنید.
      </Alert>
    )
  return (
    <Stack spacing={2.5}>
      <Box>
        <Typography variant="h5" dir="auto">
          {profile.contact.full_name ??
            detail.candidate_name ??
            "نام استخراج نشده"}
        </Typography>
        {profile.headline && (
          <Typography color="text.secondary" dir="auto" sx={{ mt: 0.5 }}>
            {profile.headline}
          </Typography>
        )}
        <Stack spacing={0.5} sx={{ mt: 2 }}>
          {[
            profile.contact.email,
            profile.contact.phone,
            profile.contact.location,
          ]
            .filter(Boolean)
            .map((value, index) => (
              <Typography key={index} dir="auto" sx={{ fontSize: 13 }}>
                {value}
              </Typography>
            ))}
        </Stack>
      </Box>
      {profile.summary && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1 }}>
            معرفی
          </Typography>
          <Typography dir="auto" sx={{ fontSize: 13, lineHeight: 2 }}>
            {profile.summary}
          </Typography>
        </Box>
      )}
      {profile.skills.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1 }}>
            مهارت‌ها
          </Typography>
          <Stack direction="row" useFlexGap sx={{ flexWrap: "wrap", gap: 1 }}>
            {profile.skills.map((skill, index) => (
              <Chip key={index} size="small" label={skill} />
            ))}
          </Stack>
        </Box>
      )}
      {profile.work_experience.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1 }}>
            سوابق کاری
          </Typography>
          <Stack spacing={2}>
            {profile.work_experience.map((work, index) => (
              <Box
                key={index}
                sx={{
                  borderInlineStart: "2px solid",
                  borderColor: "primary.light",
                  paddingInlineStart: 2,
                }}
              >
                <Typography dir="auto" sx={{ fontSize: 14, fontWeight: 650 }}>
                  {work.title}
                </Typography>
                <Typography dir="auto" sx={{ fontSize: 13 }}>
                  {work.company}
                </Typography>
                {work.location && (
                  <Typography
                    dir="auto"
                    color="text.secondary"
                    sx={{ fontSize: 12 }}
                  >
                    {work.location}
                  </Typography>
                )}
                <Typography
                  color="text.secondary"
                  dir="auto"
                  sx={{ fontSize: 11 }}
                >
                  {formatDateRange(
                    work.start_date,
                    work.end_date,
                    work.current,
                  )}
                </Typography>
                {work.bullets?.map((bullet, i) => (
                  <Typography
                    key={i}
                    dir="auto"
                    sx={{ ...{ mt: 0.5 }, fontSize: 12, lineHeight: 1.9 }}
                  >
                    {bullet}
                  </Typography>
                ))}
              </Box>
            ))}
          </Stack>
        </Box>
      )}
      {profile.education.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1 }}>
            تحصیلات
          </Typography>
          {profile.education.map((education, index) => (
            <Box key={index} sx={{ mb: 1.5 }}>
              <Typography dir="auto" sx={{ fontSize: 13, fontWeight: 600 }}>
                {[education.degree, education.field].filter(Boolean).join("، ")}
              </Typography>
              <Typography dir="auto" sx={{ fontSize: 12 }}>
                {education.institution}
              </Typography>
              <Typography
                color="text.secondary"
                dir="auto"
                sx={{ fontSize: 11 }}
              >
                {formatDateRange(
                  education.start_date,
                  education.end_date,
                  false,
                )}
              </Typography>
            </Box>
          ))}
        </Box>
      )}
      {profile.languages.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1 }}>
            زبان‌ها
          </Typography>
          {profile.languages.map((language, index) => (
            <Typography key={index} dir="auto" sx={{ fontSize: 13 }}>
              {[language.language, language.proficiency]
                .filter(Boolean)
                .join(" — ")}
            </Typography>
          ))}
        </Box>
      )}
      {profile.certifications.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1 }}>
            گواهی‌ها
          </Typography>
          {profile.certifications.map((certificate, index) => (
            <Typography key={index} dir="auto" sx={{ fontSize: 13 }}>
              {[certificate.name, certificate.issuer, formatResumeDate(certificate.date)]
                .filter(Boolean)
                .join(" — ")}
            </Typography>
          ))}
        </Box>
      )}
      {profile.industries.length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1 }}>
            صنایع
          </Typography>
          <Stack direction="row" useFlexGap sx={{ flexWrap: "wrap", gap: 1 }}>
            {profile.industries.map((industry, i) => (
              <Chip key={i} size="small" label={industry} />
            ))}
          </Stack>
        </Box>
      )}
      {(profile.contact.links ?? []).length > 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 1 }}>
            پیوندها
          </Typography>
          {profile.contact.links?.map((link, i) => (
            <Typography
              key={i}
              dir="auto"
              sx={{ fontSize: 13, overflowWrap: "anywhere" }}
            >
              {link.type ? `${link.type}: ` : ""}
              {link.url && /^https?:\/\//i.test(link.url) ? (
                <a href={link.url} target="_blank" rel="noreferrer">
                  {link.url}
                </a>
              ) : (
                link.url
              )}
            </Typography>
          ))}
        </Box>
      )}
      {profile.extraction_notes.length > 0 && (
        <Alert severity="warning">
          <Typography sx={{ fontWeight: 650, fontSize: 13 }}>
            یادداشت‌های استخراج؛ نیازمند بررسی HR
          </Typography>
          {profile.extraction_notes.map((note, index) => (
            <Typography
              key={index}
              dir="auto"
              sx={{ ...{ mt: 1 }, fontSize: 12 }}
            >
              {note}
            </Typography>
          ))}
        </Alert>
      )}
    </Stack>
  )
}

function ResumeDialog({
  id,
  initialMode,
  onClose,
  onSaved,
}: {
  id: string
  initialMode: "view" | "edit"
  onClose: () => void
  onSaved: () => void
}) {
  const [detail, setDetail] = useState<ResumeDetail | null>(null)
  const [mode, setMode] = useState(initialMode)
  const [form, setForm] = useState<ResumeEdit | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    fetchResume(id, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return
        setDetail(data)
        const p = reviewProfile(data.profile)
        setForm({
          full_name: p.contact.full_name ?? data.candidate_name ?? "",
          email: p.contact.email,
          phone: p.contact.phone,
          location: p.contact.location,
          headline: p.headline,
          summary: p.summary,
          skills: p.skills,
        })
      })
      .catch((cause) => {
        if (!controller.signal.aborted) setError(persianError(cause))
      })
    return () => controller.abort()
  }, [id])
  async function save(event: FormEvent) {
    event.preventDefault()
    if (!form) return
    setBusy(true)
    setError(null)
    try {
      const initial = reviewProfile(detail?.profile ?? null)
      await updateResume(id, { ...form, expected_values: {
        "contact.full_name": initial.contact.full_name,
        "contact.email": initial.contact.email,
        "contact.phone": initial.contact.phone,
        "contact.location": initial.contact.location,
        headline: initial.headline, summary: initial.summary, skills: initial.skills,
      } })
      onSaved()
      onClose()
    } catch (cause) {
      setError(persianError(cause))
    } finally {
      setBusy(false)
    }
  }
  const quarantined = detail?.reason?.startsWith("inbound:") ?? false
  return (
    <Dialog
      open
      onClose={busy ? undefined : onClose}
      maxWidth={mode === "view" ? "lg" : "sm"}
      fullWidth
    >
      <DialogTitle>
        <Stack
          direction="row"
          sx={{ alignItems: "center", justifyContent: "space-between" }}
        >
          <Typography component="span" variant="h6">
            {mode === "edit" ? "ویرایش اطلاعات رزومه" : "جزئیات رزومه"}
          </Typography>
          <IconButton
            aria-label="بستن جزئیات"
            onClick={onClose}
            disabled={busy}
          >
            <X size={20} />
          </IconButton>
        </Stack>
      </DialogTitle>
      <DialogContent dividers>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        {!detail && !error && (
          <Box sx={{ display: "grid", placeItems: "center", py: 6 }}>
            <CircularProgress />
          </Box>
        )}
        {detail && (
          <>
            <Stack
              direction="row"
              sx={{
                ...{ mb: 2 },
                alignItems: "center",
                flexWrap: "wrap",
                gap: 2,
              }}
            >
              <Typography dir="auto" sx={{ fontSize: 13 }}>
                {detail.filename}
              </Typography>
              <Status item={detail} />
            </Stack>
            {mode === "view" ? (
              <Box
                sx={{
                  display: "grid",
                  gap: 3,
                  gridTemplateColumns: {
                    xs: "1fr",
                    md: "minmax(0,1fr) minmax(0,1fr)",
                  },
                }}
              >
                <Stack spacing={2}>
                  {quarantined ? (
                    <Alert severity="error">
                      دریافت و پیش‌نمایش فایل تا تکمیل بررسی ایمنی مسدود است.
                    </Alert>
                  ) : (
                    detail.latest_job_id && (
                      <>
                        <Button
                          component="a"
                          href={`/api/review/${detail.latest_job_id}/document`}
                          variant="outlined"
                          startIcon={<Download size={17} />}
                        >
                          دریافت فایل اصلی
                        </Button>
                        <Preview jobId={detail.latest_job_id} />
                      </>
                    )
                  )}
                  {detail.reason && (
                    <Typography color="text.secondary" sx={{ fontSize: 12 }}>
                      {parseStatusLabel(detail.status, detail.reason)}
                    </Typography>
                  )}
                </Stack>
                <Profile detail={detail} />
              </Box>
            ) : (
              form && (
                <Box
                  component="form"
                  id="resume-edit"
                  onSubmit={(event) => void save(event)}
                >
                  {quarantined && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                      ویرایش این سند تا تکمیل بررسی ایمنی مجاز نیست.
                    </Alert>
                  )}
                  <Stack spacing={2.5} sx={{ pt: 1 }}>
                    {(
                      [
                        ["full_name", "نام و نام خانوادگی"],
                        ["email", "ایمیل"],
                        ["phone", "تلفن"],
                        ["location", "محل زندگی"],
                        ["headline", "عنوان حرفه‌ای"],
                        ["summary", "معرفی نوشته‌شده در رزومه"],
                      ] as const
                    ).map(([key, label]) => (
                      <TextField
                        key={key}
                        label={label}
                        fullWidth
                        required={key === "full_name"}
                        type={key === "email" ? "email" : "text"}
                        disabled={busy || quarantined}
                        multiline={key === "summary"}
                        minRows={key === "summary" ? 3 : undefined}
                        value={form[key] ?? ""}
                        onChange={(event) =>
                          setForm((old) =>
                            old
                              ? {
                                  ...old,
                                  [key]:
                                    event.target.value ||
                                    (key === "full_name" ? "" : null),
                                }
                              : old,
                          )
                        }
                      />
                    ))}
                    <TextField
                      label="مهارت‌ها؛ هر مورد در یک خط"
                      multiline
                      minRows={3}
                      value={form.skills.join("\n")}
                      disabled={busy || quarantined}
                      onChange={(event) =>
                        setForm((old) =>
                          old
                            ? { ...old, skills: event.target.value.split("\n") }
                            : old,
                        )
                      }
                    />
                  </Stack>
                </Box>
              )
            )}
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ p: 2, gap: 1 }}>
        <Button onClick={onClose} disabled={busy}>
          بستن
        </Button>
        {detail &&
          (mode === "view" ? (
            <Button
              variant="contained"
              startIcon={<Pencil size={16} />}
              onClick={() => setMode("edit")}
              disabled={quarantined}
            >
              ویرایش اطلاعات
            </Button>
          ) : (
            <Button
              variant="contained"
              type="submit"
              form="resume-edit"
              disabled={busy || quarantined || !form?.full_name.trim()}
            >
              {busy ? "در حال ذخیره…" : "ذخیره و تأیید اطلاعات"}
            </Button>
          ))}
      </DialogActions>
    </Dialog>
  )
}

export function ResumesPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<ResumeItem[]>([])
  const [next, setNext] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState("")
  const [search, setSearch] = useState("")
  const [version, setVersion] = useState(0)
  const [selected, setSelected] = useState<{
    id: string
    mode: "view" | "edit"
  } | null>(null)
  const [deleting, setDeleting] = useState<ResumeItem | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    fetchResumes(search, undefined, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setItems(data.items)
          setNext(data.next_cursor)
        }
      })
      .catch((cause) => {
        if (!controller.signal.aborted) setError(persianError(cause))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [search, version])
  async function more() {
    if (!next) return
    setLoading(true)
    setError(null)
    try {
      const data = await fetchResumes(search, next)
      setItems((old) => [...old, ...data.items])
      setNext(data.next_cursor)
    } catch (cause) {
      setError(persianError(cause))
    } finally {
      setLoading(false)
    }
  }
  async function remove() {
    if (!deleting) return
    setDeleteBusy(true)
    setDeleteError(null)
    try {
      await deleteResume(deleting.id)
      setItems((old) => old.filter((item) => item.id !== deleting.id))
      setDeleting(null)
    } catch (cause) {
      setDeleteError(persianError(cause))
    } finally {
      setDeleteBusy(false)
    }
  }
  return (
    <AppShell>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={2}
        sx={{
          ...{ mb: 3 },
          justifyContent: "space-between",
          alignItems: { sm: "center" },
        }}
      >
        <Box>
          <Typography variant="h4">رزومه‌های دریافت‌شده</Typography>
          <Typography color="text.secondary" sx={{ mt: 1 }}>
            فایل‌ها و اطلاعات استخراج‌شده را مشاهده، اصلاح و مدیریت کنید.
          </Typography>
        </Box>
        <Button
          component={Link}
          to="/upload"
          variant="contained"
          startIcon={<Upload size={18} />}
        >
          بارگذاری رزومه
        </Button>
      </Stack>
      <Paper variant="outlined" sx={{ overflow: "hidden" }}>
        <Stack
          component="form"
          direction="row"
          spacing={1.5}
          onSubmit={(event) => {
            event.preventDefault()
            setSearch(searchInput)
            setVersion((old) => old + 1)
          }}
          sx={{ p: 2.5 }}
        >
          <TextField
            label="جست‌وجوی نام، فایل یا ایمیل"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            sx={{ maxWidth: 420, flex: 1 }}
          />
          <Button type="submit" variant="outlined" aria-label="جست‌وجو">
            <Search size={18} />
          </Button>
          <Tooltip title="تازه‌سازی">
            <IconButton
              aria-label="تازه‌سازی فهرست"
              disabled={loading}
              onClick={() => setVersion((old) => old + 1)}
            >
              <RefreshCw size={18} />
            </IconButton>
          </Tooltip>
        </Stack>
        <Divider />
        {error && (
          <Alert severity="error" sx={{ m: 2 }}>
            {error}
          </Alert>
        )}
        <TableContainer sx={{ display: items.length ? "block" : "none" }}>
          <Table aria-label="فهرست رزومه‌های دریافت‌شده" sx={{ minWidth: 850 }}>
            <TableHead>
              <TableRow>
                <TableCell>فایل رزومه</TableCell>
                <TableCell>کاندیدا</TableCell>
                <TableCell>وضعیت تحلیل</TableCell>
                <TableCell>تاریخ دریافت</TableCell>
                <TableCell align="center">عملیات</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id} hover>
                  <TableCell>
                    <Stack
                      direction="row"
                      spacing={1.5}
                      sx={{ alignItems: "center" }}
                    >
                      <Box
                        sx={{
                          bgcolor: "#edf3fb",
                          p: 1,
                          borderRadius: 1,
                          color: "primary.main",
                          display: "flex",
                        }}
                      >
                        <FileText size={20} />
                      </Box>
                      <Box>
                        <Typography
                          dir="auto"
                          sx={{
                            ...{ maxWidth: 220, overflowWrap: "anywhere" },
                            fontSize: 13,
                            fontWeight: 600,
                          }}
                        >
                          {item.filename}
                        </Typography>
                        <Typography
                          color="text.secondary"
                          sx={{ fontSize: 10 }}
                        >
                          {item.filename.split(".").pop()?.toUpperCase()}
                        </Typography>
                      </Box>
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Typography
                      dir="auto"
                      sx={{ fontSize: 13, fontWeight: 600 }}
                    >
                      {item.candidate_name ?? "استخراج نشده"}
                    </Typography>
                    <Typography
                      color="text.secondary"
                      dir="auto"
                      sx={{ fontSize: 11 }}
                    >
                      {item.candidate_email}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Status item={item} />
                  </TableCell>
                  <TableCell>
                    <Typography sx={{ fontSize: 12 }}>
                      {formatJalali(item.created_at)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Stack
                      direction="row"
                      spacing={0.5}
                      sx={{ justifyContent: "center" }}
                    >
                      <Tooltip title="مشاهده">
                        <IconButton
                          aria-label={`مشاهده ${item.filename}`}
                          color="primary"
                          onClick={() =>
                            item.candidate_id
                              ? navigate(`/candidates/${item.candidate_id}`)
                              : setSelected({ id: item.id, mode: "view" })
                          }
                        >
                          <Eye size={18} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="ویرایش">
                        <IconButton
                          aria-label={`ویرایش ${item.filename}`}
                          onClick={() =>
                            item.candidate_id
                              ? navigate(
                                  `/candidates/${item.candidate_id}?edit=1`,
                                )
                              : setSelected({ id: item.id, mode: "edit" })
                          }
                        >
                          <Pencil size={17} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="حذف">
                        <IconButton
                          aria-label={`حذف ${item.filename}`}
                          color="error"
                          onClick={() => {
                            setDeleting(item)
                            setDeleteError(null)
                          }}
                        >
                          <Trash2 size={17} />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        {!items.length && (
          <Box sx={{ py: 7, px: 2, textAlign: "center" }}>
            {loading ? (
              <CircularProgress size={28} aria-label="بارگذاری فهرست" />
            ) : (
              <Stack spacing={1.5} sx={{ alignItems: "center" }}>
                <FileText size={35} color="#94a3b8" />
                <Typography sx={{ fontWeight: 650 }}>
                  {search
                    ? "رزومه‌ای مطابق جست‌وجو پیدا نشد"
                    : "هنوز رزومه‌ای دریافت نشده است"}
                </Typography>
                <Typography color="text.secondary" sx={{ fontSize: 13 }}>
                  {search
                    ? "عبارت دیگری را امتحان کنید."
                    : "اولین فایل را از بخش بارگذاری اضافه کنید."}
                </Typography>
              </Stack>
            )}
          </Box>
        )}
        <Stack
          direction="row"
          sx={{
            ...{ p: 2 },
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Typography color="text.secondary" sx={{ fontSize: 12 }}>
            {items.length.toLocaleString("fa-IR")} رزومه نمایش داده شده
          </Typography>
          {next && (
            <Button disabled={loading} onClick={() => void more()}>
              {loading ? "در حال بارگذاری…" : "نمایش بیشتر"}
            </Button>
          )}
        </Stack>
      </Paper>
      {selected && (
        <ResumeDialog
          key={selected.id}
          id={selected.id}
          initialMode={selected.mode}
          onClose={() => setSelected(null)}
          onSaved={() => setVersion((old) => old + 1)}
        />
      )}
      <Dialog
        open={Boolean(deleting)}
        onClose={deleteBusy ? undefined : () => setDeleting(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>حذف رزومه</DialogTitle>
        <DialogContent>
          {deleteError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {deleteError}
            </Alert>
          )}
          <DialogContentText>
            فایل «{deleting?.filename}» و نتیجهٔ تحلیل آن حذف می‌شود. این کار
            قابل بازگشت نیست. پروندهٔ فرد، یادداشت‌ها و تاریخچه حفظ می‌شوند.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button disabled={deleteBusy} onClick={() => setDeleting(null)}>
            انصراف
          </Button>
          <Button
            variant="contained"
            color="error"
            disabled={deleteBusy}
            onClick={() => void remove()}
          >
            {deleteBusy ? "در حال حذف…" : "حذف رزومه"}
          </Button>
        </DialogActions>
      </Dialog>
    </AppShell>
  )
}
