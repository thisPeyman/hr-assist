import { Navigate, Route, Routes } from "react-router"

import { useAuth } from "@/auth"
import { CandidatePage } from "@/pages/candidate"
import { HomePage } from "@/pages/home"
import { LoginPage } from "@/pages/login"
import { PoolPage } from "@/pages/pool"
import { SignupPage } from "@/pages/signup"

function Protected({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex min-h-svh items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">در حال بارگذاری…</p>
      </div>
    )
  }
  if (!me) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <Protected>
            <HomePage />
          </Protected>
        }
      />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route
        path="/pool"
        element={
          <Protected>
            <PoolPage />
          </Protected>
        }
      />
      <Route
        path="/candidates/:id"
        element={
          <Protected>
            <CandidatePage />
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
