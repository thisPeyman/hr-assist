import { useState, type ReactNode } from "react"
import { useNavigate } from "react-router"
import { LogOutIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/auth"
import { logout } from "@/lib/api"
import { cn } from "@/lib/utils"

/** Brand mark: a deep-turquoise tile with the Persian initial «د». */
export function Wordmark({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-lg font-bold text-primary-foreground">
        د
      </span>
      <span className="text-sm font-bold tracking-tight text-foreground sm:text-base">
        دستیار هوشمند منابع انسانی
      </span>
    </div>
  )
}

const ROLE_LABELS: Record<string, string> = {
  admin: "مدیر",
  member: "عضو",
}

/** Session controls shared by every logged-in page header. */
export function HeaderActions() {
  const { me, refresh } = useAuth()
  const navigate = useNavigate()
  const [loggingOut, setLoggingOut] = useState(false)
  if (!me) return null

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

  return (
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
  )
}

/** Logged-in app chrome: header with brand + session controls. */
export function AppShell({
  children,
  actions,
}: {
  children: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="flex min-h-svh flex-col bg-background">
      <header className="sticky top-0 z-10 border-b bg-card/80 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-5xl items-center justify-between gap-4 px-4">
          <Wordmark />
          {actions ?? <HeaderActions />}
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>
    </div>
  )
}
