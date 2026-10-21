import { useEffect, useState } from "react"
import { Link, useParams } from "react-router"
import {
  ChevronRightIcon,
  FileTextIcon,
  LinkIcon,
  MailIcon,
  MapPinIcon,
  PhoneIcon,
} from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { AppShell } from "@/components/shell"
import {
  fetchCandidate,
  persianError,
  type CandidateDetail,
  type ProfileLink,
  type ProfileWorkExperience,
} from "@/lib/api"
import { formatJalali } from "@/lib/jalali"
import { formatDateRange, parseStatusLabel } from "@/lib/profile"

function ProfileLinkIcon({ link }: { link: ProfileLink }) {
  return <LinkIcon className="size-3.5" data-type={link.type ?? "other"} />
}

const STATUS_BADGE: Record<string, string> = {
  extracted: "bg-primary text-primary-foreground",
  needs_review: "bg-accent text-accent-foreground",
  failed: "bg-destructive/10 text-destructive",
  not_a_resume: "bg-muted text-muted-foreground",
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-sm font-semibold tracking-wide text-muted-foreground">
      {children}
    </h2>
  )
}

/** The work-history rail: a turquoise rule with Jalali ranges in saffron ink. */
function ExperienceItem({ experience }: { experience: ProfileWorkExperience }) {
  const range = formatDateRange(
    experience.start_date,
    experience.end_date,
    experience.current
  )
  return (
    <li className="border-s-2 border-primary/30 ps-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="font-semibold text-foreground">
          {experience.title}
          {experience.company && (
            <span className="font-normal text-muted-foreground">
              {" "}
              — {experience.company}
            </span>
          )}
        </p>
        {range && (
          <p className="text-sm text-accent-foreground">{range}</p>
        )}
      </div>
      {experience.location && (
        <p className="mt-0.5 text-sm text-muted-foreground">
          {experience.location}
        </p>
      )}
      {experience.bullets && experience.bullets.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 ps-5 text-sm text-foreground/90">
          {experience.bullets.map((bullet, index) => (
            <li key={index}>{bullet}</li>
          ))}
        </ul>
      )}
    </li>
  )
}

function ProfileBody({ candidate }: { candidate: CandidateDetail }) {
  const profile = candidate.profile
  if (!profile) {
    return (
      <p className="text-sm text-muted-foreground">
        پروفایل ساخت‌یافته‌ای برای نمایش نیست.
      </p>
    )
  }

  const education = profile.education.filter(
    (item) => item.degree || item.field || item.institution
  )
  const contact = profile.contact

  return (
    <div className="space-y-8">
      {contact.links && contact.links.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {contact.links
            .filter((link) => link.url)
            .map((link, index) => (
              <a
                key={index}
                href={link.url ?? "#"}
                target="_blank"
                rel="noreferrer"
                dir="ltr"
                className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs text-foreground transition-colors hover:bg-secondary"
              >
                <ProfileLinkIcon link={link} />
                {link.type === "other" || !link.type ? link.url : link.type}
              </a>
            ))}
        </div>
      )}

      {profile.summary && (
        <section className="space-y-2">
          <SectionTitle>در رزومه آمده</SectionTitle>
          <blockquote className="border-s-2 border-border ps-4 text-sm leading-7 text-foreground/90">
            {profile.summary}
          </blockquote>
        </section>
      )}

      {profile.skills.length > 0 && (
        <section className="space-y-2">
          <SectionTitle>مهارت‌ها</SectionTitle>
          <div className="flex flex-wrap gap-1.5">
            {profile.skills.map((skill) => (
              <Badge key={skill} variant="outline">
                {skill}
              </Badge>
            ))}
          </div>
        </section>
      )}

      {profile.industries.length > 0 && (
        <section className="space-y-2">
          <SectionTitle>صنایع</SectionTitle>
          <div className="flex flex-wrap gap-1.5">
            {profile.industries.map((industry) => (
              <Badge key={industry} variant="secondary">
                {industry}
              </Badge>
            ))}
          </div>
        </section>
      )}

      {profile.work_experience.length > 0 && (
        <section className="space-y-3">
          <SectionTitle>سوابق شغلی</SectionTitle>
          <ul className="space-y-5">
            {profile.work_experience.map((experience, index) => (
              <ExperienceItem key={index} experience={experience} />
            ))}
          </ul>
        </section>
      )}

      {education.length > 0 && (
        <section className="space-y-3">
          <SectionTitle>تحصیلات</SectionTitle>
          <ul className="space-y-3">
            {education.map((item, index) => {
              const range = formatDateRange(
                item.start_date,
                item.end_date,
                false
              )
              return (
                <li key={index}>
                  <p className="font-medium text-foreground">
                    {item.degree}
                    {item.field && ` — ${item.field}`}
                  </p>
                  {item.institution && (
                    <p className="text-sm text-muted-foreground">
                      {item.institution}
                    </p>
                  )}
                  {range && (
                    <p className="text-sm text-accent-foreground">{range}</p>
                  )}
                </li>
              )
            })}
          </ul>
        </section>
      )}

      {profile.languages.length > 0 && (
        <section className="space-y-2">
          <SectionTitle>زبان‌ها</SectionTitle>
          <ul className="space-y-1 text-sm text-foreground/90">
            {profile.languages.map((language, index) => (
              <li key={index}>
                {language.language}
                {language.proficiency && (
                  <span className="text-muted-foreground">
                    {" "}
                    — {language.proficiency}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {profile.certifications.length > 0 && (
        <section className="space-y-2">
          <SectionTitle>گواهی‌نامه‌ها</SectionTitle>
          <ul className="space-y-1 text-sm text-foreground/90">
            {profile.certifications.map((certification, index) => (
              <li key={index}>
                {certification.name}
                {certification.issuer && (
                  <span className="text-muted-foreground">
                    {" "}
                    — {certification.issuer}
                  </span>
                )}
                {certification.date && (
                  <span className="text-muted-foreground">
                    {" "}
                    ({certification.date})
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {profile.extraction_notes.length > 0 && (
        <>
          <Separator />
          <section className="space-y-2">
            <SectionTitle>یادداشت‌های استخراج</SectionTitle>
            <ul className="list-disc space-y-1 ps-5 text-xs text-muted-foreground">
              {profile.extraction_notes.map((note, index) => (
                <li key={index}>{note}</li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  )
}

export function CandidatePage() {
  const { id } = useParams<{ id: string }>()
  const [candidate, setCandidate] = useState<CandidateDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    if (!id) return
    fetchCandidate(id)
      .then((detail) => {
        if (alive) setCandidate(detail)
      })
      .catch((e) => {
        if (alive) setError(persianError(e))
      })
    return () => {
      alive = false
    }
  }, [id])

  if (error) {
    return (
      <AppShell>
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <div className="mt-4">
          <Link
            to="/pool"
            className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            <ChevronRightIcon className="size-4" />
            بازگشت به مجموعه استعدادها
          </Link>
        </div>
      </AppShell>
    )
  }

  if (!candidate) {
    return (
      <AppShell>
        <p className="py-16 text-center text-sm text-muted-foreground">
          در حال بارگذاری…
        </p>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <Link
        to="/pool"
        className="mb-6 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
      >
        <ChevronRightIcon className="size-4" />
        مجموعه استعدادها
      </Link>

      {/* Identity */}
      <section className="border-s-2 border-accent ps-4">
        <h1 className="text-2xl font-bold text-foreground sm:text-3xl">
          {candidate.full_name}
        </h1>
        {candidate.headline && (
          <p className="mt-1 text-muted-foreground">{candidate.headline}</p>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
          {candidate.email && (
            <span dir="ltr" className="inline-flex items-center gap-1.5">
              <MailIcon className="size-3.5" />
              {candidate.email}
            </span>
          )}
          {candidate.phone && (
            <span dir="ltr" className="inline-flex items-center gap-1.5">
              <PhoneIcon className="size-3.5" />
              {candidate.phone}
            </span>
          )}
          {candidate.location && (
            <span className="inline-flex items-center gap-1.5">
              <MapPinIcon className="size-3.5" />
              {candidate.location}
            </span>
          )}
        </div>
      </section>

      {/* Latest resume — the source document and its explicit status. */}
      {candidate.resume && (
        <Card className="mt-6">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
                <FileTextIcon className="size-4" />
              </span>
              <div className="min-w-0">
                <p dir="ltr" className="truncate text-sm font-medium text-foreground">
                  {candidate.resume.filename}
                </p>
                <p className="text-xs text-muted-foreground">
                  بارگذاری {formatJalali(candidate.resume.uploaded_at)}
                </p>
              </div>
            </div>
            <span
              className={[
                "rounded-full px-3 py-1 text-xs font-medium",
                STATUS_BADGE[candidate.resume.parse_status] ??
                  "bg-muted text-muted-foreground",
              ].join(" ")}
            >
              {parseStatusLabel(
                candidate.resume.parse_status,
                candidate.resume.parse_reason
              )}
            </span>
          </CardContent>
        </Card>
      )}

      <div className="mt-8">
        <ProfileBody candidate={candidate} />
      </div>
    </AppShell>
  )
}
