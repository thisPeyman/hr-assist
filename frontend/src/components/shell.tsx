import type { ReactNode } from "react"

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
          {actions}
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>
    </div>
  )
}
