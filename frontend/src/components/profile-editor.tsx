import type { FormEvent } from "react"
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  IconButton,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material"
import { ChevronDown, Plus, Trash2 } from "lucide-react"
import type { CandidateProfile } from "@/lib/api"
import { reviewProfile } from "@/lib/review"

type Field = { key: string; label: string; lines?: boolean }

function Collection({
  title,
  rows,
  fields,
  onChange,
  work = false,
}: {
  title: string
  rows: object[]
  fields: Field[]
  onChange: (rows: Record<string, unknown>[]) => void
  work?: boolean
}) {
  const values = rows as Record<string, unknown>[]
  const update = (index: number, key: string, value: unknown) =>
    onChange(
      values.map((row, i) => (i === index ? { ...row, [key]: value } : row)),
    )
  return (
    <Accordion
      disableGutters
      variant="outlined"
      sx={{ "&:before": { display: "none" } }}
    >
      <AccordionSummary expandIcon={<ChevronDown size={18} />}>
        <Typography sx={{ fontWeight: 650 }}>
          {title} ({rows.length.toLocaleString("fa-IR")})
        </Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={2}>
          {values.map((row, index) => (
            <Paper key={index} variant="outlined" sx={{ p: 2 }}>
              <Stack
                direction="row"
                sx={{
                  justifyContent: "space-between",
                  alignItems: "center",
                  mb: 2,
                }}
              >
                <Typography sx={{ fontSize: 12, fontWeight: 600 }}>
                  {title} — {(index + 1).toLocaleString("fa-IR")}
                </Typography>
                <IconButton
                  type="button"
                  color="error"
                  aria-label={`حذف ردیف ${title} ${index + 1}`}
                  onClick={() => onChange(values.filter((_, i) => i !== index))}
                >
                  <Trash2 size={17} />
                </IconButton>
              </Stack>
              <Box
                sx={{
                  display: "grid",
                  gap: 2,
                  gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
                }}
              >
                {fields.map((field) => (
                  <TextField
                    key={field.key}
                    label={field.label}
                    multiline={field.lines}
                    minRows={field.lines ? 2 : undefined}
                    value={
                      field.lines
                        ? Array.isArray(row[field.key])
                          ? (row[field.key] as string[]).join("\n")
                          : ""
                        : String(row[field.key] ?? "")
                    }
                    onChange={(event) =>
                      update(
                        index,
                        field.key,
                        field.lines
                          ? event.target.value.split("\n")
                          : event.target.value || null,
                      )
                    }
                    sx={field.lines ? { gridColumn: "1 / -1" } : {}}
                  />
                ))}
              </Box>
              {work && (
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={row.current === true}
                      onChange={(event) =>
                        update(index, "current", event.target.checked)
                      }
                    />
                  }
                  label="همچنان در این شغل مشغول است"
                />
              )}
            </Paper>
          ))}
          <Button
            type="button"
            variant="outlined"
            startIcon={<Plus size={17} />}
            onClick={() =>
              onChange([
                ...values,
                Object.fromEntries(
                  fields.map((field) => [field.key, field.lines ? [] : null]),
                ),
              ])
            }
          >
            افزودن {title}
          </Button>
        </Stack>
      </AccordionDetails>
    </Accordion>
  )
}

export function ProfileEditor({
  profile,
  onChange,
  onSave,
  onCancel,
  busy,
}: {
  profile: CandidateProfile
  onChange: (profile: CandidateProfile) => void
  onSave: (event: FormEvent) => void
  onCancel: () => void
  busy: boolean
}) {
  const collection = (
    key: "work_experience" | "education" | "languages" | "certifications",
    rows: Record<string, unknown>[],
  ) => onChange(reviewProfile({ ...profile, [key]: rows }))
  return (
    <Box component="form" onSubmit={onSave}>
      <Stack spacing={2.5}>
        <Alert severity="info">
          اصلاحات شما حفظ می‌شوند. رزومهٔ جدید فقط فیلدهای خالی را پر می‌کند و
          برای اختلاف‌ها پیشنهاد می‌دهد.
        </Alert>
        <Box
          sx={{
            display: "grid",
            gap: 2,
            gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
          }}
        >
          {(
            [
              ["full_name", "نام و نام خانوادگی"],
              ["email", "ایمیل"],
              ["phone", "تلفن"],
              ["location", "محل زندگی"],
            ] as const
          ).map(([key, label]) => (
            <TextField
              key={key}
              label={label}
              required={key === "full_name"}
              type={key === "email" ? "email" : "text"}
              value={profile.contact[key] ?? ""}
              onChange={(event) =>
                onChange({
                  ...profile,
                  contact: {
                    ...profile.contact,
                    [key]: event.target.value || null,
                  },
                })
              }
            />
          ))}
        </Box>
        <TextField
          label="عنوان حرفه‌ای"
          value={profile.headline ?? ""}
          onChange={(event) =>
            onChange({ ...profile, headline: event.target.value || null })
          }
        />
        <TextField
          label="معرفی نوشته‌شده در رزومه"
          multiline
          minRows={3}
          value={profile.summary ?? ""}
          onChange={(event) =>
            onChange({ ...profile, summary: event.target.value || null })
          }
        />
        <Box
          sx={{
            display: "grid",
            gap: 2,
            gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
          }}
        >
          {(
            [
              ["skills", "مهارت‌ها؛ هر مورد در یک خط"],
              ["industries", "صنایع؛ هر مورد در یک خط"],
            ] as const
          ).map(([key, label]) => (
            <TextField
              key={key}
              label={label}
              multiline
              minRows={3}
              value={profile[key].join("\n")}
              onChange={(event) =>
                onChange({ ...profile, [key]: event.target.value.split("\n") })
              }
            />
          ))}
        </Box>
        <Collection
          title="سوابق کاری"
          work
          rows={profile.work_experience}
          onChange={(rows) => collection("work_experience", rows)}
          fields={[
            { key: "title", label: "عنوان شغل" },
            { key: "company", label: "کارفرما" },
            { key: "location", label: "محل کار" },
            { key: "start_date", label: "تاریخ شروع؛ مطابق رزومه" },
            { key: "end_date", label: "تاریخ پایان؛ مطابق رزومه" },
            {
              key: "bullets",
              label: "شرح فعالیت‌ها؛ هر مورد در یک خط",
              lines: true,
            },
          ]}
        />
        <Collection
          title="تحصیلات"
          rows={profile.education}
          onChange={(rows) => collection("education", rows)}
          fields={[
            { key: "degree", label: "مقطع" },
            { key: "field", label: "رشته" },
            { key: "institution", label: "مؤسسه" },
            { key: "start_date", label: "تاریخ شروع" },
            { key: "end_date", label: "تاریخ پایان" },
          ]}
        />
        <Collection
          title="زبان‌ها"
          rows={profile.languages}
          onChange={(rows) => collection("languages", rows)}
          fields={[
            { key: "language", label: "زبان" },
            { key: "proficiency", label: "سطح" },
          ]}
        />
        <Collection
          title="گواهی‌ها"
          rows={profile.certifications}
          onChange={(rows) => collection("certifications", rows)}
          fields={[
            { key: "name", label: "نام گواهی" },
            { key: "issuer", label: "صادرکننده" },
            { key: "date", label: "تاریخ" },
          ]}
        />
        <Collection
          title="پیوندها"
          rows={profile.contact.links ?? []}
          onChange={(rows) =>
            onChange(
              reviewProfile({
                ...profile,
                contact: { ...profile.contact, links: rows },
              }),
            )
          }
          fields={[
            { key: "type", label: "نوع پیوند" },
            { key: "url", label: "نشانی" },
          ]}
        />
        <TextField
          label="زبان سند"
          value={profile.document_language ?? ""}
          onChange={(event) =>
            onChange({
              ...profile,
              document_language: event.target.value || null,
            })
          }
        />
        <TextField
          label="یادداشت‌های استخراج؛ هر مورد در یک خط"
          multiline
          minRows={2}
          value={profile.extraction_notes.join("\n")}
          onChange={(event) => onChange({ ...profile, extraction_notes: event.target.value.split("\n").filter(Boolean) })}
        />
        <Stack direction="row" spacing={2}>
          <Button
            type="submit"
            variant="contained"
            disabled={busy || !profile.contact.full_name?.trim()}
          >
            {busy ? "در حال ذخیره…" : "ذخیرهٔ پروفایل"}
          </Button>
          <Button type="button" disabled={busy} onClick={onCancel}>
            انصراف
          </Button>
        </Stack>
      </Stack>
    </Box>
  )
}
