import { useState } from "react"
import { useNavigate } from "react-router"
import { LogOutIcon, MailXIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { AppShell } from "@/components/shell"
import { useAuth } from "@/auth"
import { logout } from "@/lib/api"
import { formatJalali } from "@/lib/jalali"

const ROLE_LABELS: Record<string, string> = {
  admin: "مدیر",
  member: "عضو",
}

export function HomePage() {
  const { me, refresh } = useAuth()
  const navigate = useNavigate()
  const [loggingOut, setLoggingOut] = useState(false)
  // Storage stays Gregorian ISO; conversion happens only here, at render.
  // en-CA renders the LOCAL date as YYYY-MM-DD (toISOString would be UTC and
  // wrong for "today" in Iran's evenings).
  const [todayIso] = useState(() => new Date().toLocaleDateString("en-CA"))

  async function onLogout() {
    setLoggingOut(true)
    try {
      await logout()
      await refresh()
      navigate("/login")
    } finally {
      setLoggingOut(false)
    }
  }

  if (!me) return null
  return (
    <AppShell
      actions={
        <div className="flex items-center gap-3">
          <Badge variant="secondary">{ROLE_LABELS[me.role] ?? me.role}</Badge>
          <span dir="ltr" className="hidden text-sm text-muted-foreground sm:inline">
            {me.email}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={onLogout}
            disabled={loggingOut}
          >
            <LogOutIcon data-icon="inline-start" />
            خروج
          </Button>
        </div>
      }
    >
      {/* Signature: the Jalali desk-diary date, saffron-ruled. */}
      <section className="border-s-2 border-accent ps-4">
        <p className="text-sm text-muted-foreground">امروز</p>
        <p className="text-3xl font-bold text-foreground sm:text-4xl">
          {formatJalali(todayIso)}
        </p>
        <h1 className="mt-3 text-xl font-semibold text-foreground">
          خوش آمدید، {me.org.name}
        </h1>
      </section>

      <Card className="mt-8">
        <CardContent className="py-10">
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <MailXIcon />
              </EmptyMedia>
              <EmptyTitle>هنوز داده‌ای برای نمایش نیست</EmptyTitle>
              <EmptyDescription>
                استخراج رزومه، جست‌وجو و برنامه‌ریزی مصاحبه به‌تازگی به این فضا
                اضافه می‌شوند.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        </CardContent>
      </Card>
    </AppShell>
  )
}
