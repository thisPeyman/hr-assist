import { useState } from "react"
import { Link } from "react-router"
import { UsersIcon } from "lucide-react"

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
import { formatJalali } from "@/lib/jalali"

export function HomePage() {
  const { me } = useAuth()
  // Storage stays Gregorian ISO; conversion happens only here, at render.
  // en-CA renders the LOCAL date as YYYY-MM-DD (toISOString would be UTC and
  // wrong for "today" in Iran's evenings).
  const [todayIso] = useState(() => new Date().toLocaleDateString("en-CA"))

  if (!me) return null
  return (
    <AppShell>
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
                <UsersIcon />
              </EmptyMedia>
              <EmptyTitle>با یک رزومه شروع کنید</EmptyTitle>
              <EmptyDescription>
                رزومه‌ها را در مجموعه استعدادها بارگذاری کنید تا پروفایل
                ساخت‌یافته هر شخص به‌طور خودکار ساخته شود.
              </EmptyDescription>
            </EmptyHeader>
            <EmptyMedia>
              <Button asChild>
                <Link to="/pool">رفتن به مجموعه استعدادها</Link>
              </Button>
            </EmptyMedia>
          </Empty>
        </CardContent>
      </Card>
    </AppShell>
  )
}
