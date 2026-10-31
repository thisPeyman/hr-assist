import Box from "@mui/material/Box"
import Typography from "@mui/material/Typography"
import type { SummaryCategory } from "@/lib/api"
import { formatResumeDate } from "@/lib/profile"

const labels: Record<string, string> = {
  headline: "عنوان حرفه‌ای", current_titles: "عنوان شغلی فعلی",
  current_employers: "کارفرمای فعلی", experience_years: "سابقهٔ کل",
  skills: "مهارت‌ها", employers: "کارفرماهای ذکرشده", industries: "صنایع",
  education: "تحصیلات", languages: "زبان‌ها", residence: "محل زندگی", locations: "مکان‌های ذکرشده",
}
const recordLabels: Record<string, string> = {
  degree: "مدرک", field: "رشته", institution: "مؤسسه", start_date: "شروع",
  end_date: "پایان", language: "زبان", proficiency: "سطح",
}

function factText(value: SummaryCategory["items"][number]["value"], key: string) {
  if (typeof value === "number") return `${value.toLocaleString("fa-IR")} سال`
  if (typeof value === "string") return value
  const text = Object.entries(value).map(([field, item]) =>
    `${recordLabels[field] ?? field}: ${field.endsWith("_date") ? formatResumeDate(item) : item}`,
  ).join(" · ")
  return key === "languages" && !value.proficiency ? `${text} · سطح: ذکر نشده است` : text
}

export function SummaryFacts({ facts }: { facts: Record<string, SummaryCategory> }) {
  return (
    <Box sx={{ my: 2 }}>
      <Typography sx={{ fontSize: 13, fontWeight: 700 }}>اطلاعات مبنای خلاصه</Typography>
      <Typography color="text.secondary" sx={{ fontSize: 12, mt: 0.5, mb: 1.5 }}>
        برگرفته از داده‌های زمان تولید؛ تغییر پروفایل این تصویر ذخیره‌شده را به‌روز نمی‌کند.
        متن هوشمند همچنان نیازمند بازبینی انسانی است.
      </Typography>
      <Box component="dl" sx={{ m: 0, display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 1.5 }}>
        {Object.entries(labels).map(([key, label]) => {
          const category = facts[key]
          return (
            <Box key={key} sx={{ borderInlineStart: "2px solid", borderColor: category?.state === "supplied" ? "primary.main" : "divider", paddingInlineStart: 1.5, minWidth: 0 }}>
              <Typography component="dt" color="text.secondary" sx={{ fontSize: 11, mb: 0.5 }}>{label}</Typography>
              <Box component="dd" sx={{ m: 0 }}>
                {category?.items.map((item, index) => (
                  <Typography key={index} dir="auto" sx={{ fontSize: 13, lineHeight: 1.9, overflowWrap: "anywhere" }}>
                    {factText(item.value, key)}
                  </Typography>
                ))}
                {!category || category.state === "unknown" ? (
                  <Typography color="text.secondary" sx={{ fontSize: 12 }}>
                    {key === "experience_years" ? "از تاریخ‌های رزومه قابل محاسبه نیست" : "در رزومه ذکر نشده است"}
                  </Typography>
                ) : category.state === "partial" ? (
                  <Typography color="text.secondary" sx={{ fontSize: 12 }}>اطلاعات بعضی سوابق فعلی کامل نیست</Typography>
                ) : null}
              </Box>
            </Box>
          )
        })}
      </Box>
    </Box>
  )
}
