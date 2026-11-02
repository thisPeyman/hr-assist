import { lazy, Suspense } from "react"
import { Navigate, Outlet, Route, Routes } from "react-router"
import { Box, CircularProgress } from "@mui/material"
import { useAuth } from "@/auth"
import { AppShell } from "@/components/shell"
import { LoginPage } from "@/pages/login"
import { SignupPage } from "@/pages/signup"
const ResumesPage = lazy(() =>
  import("@/pages/resumes").then((module) => ({ default: module.ResumesPage })),
)
const UploadPage = lazy(() =>
  import("@/pages/upload").then((module) => ({ default: module.UploadPage })),
)
const CandidateBankPage = lazy(() =>
  import("@/pages/candidates").then((module) => ({
    default: module.CandidateBankPage,
  })),
)
const CandidatePage = lazy(() =>
  import("@/pages/candidate-profile").then((module) => ({
    default: module.CandidatePage,
  })),
)
const ReviewPage = lazy(() => import("@/pages/review").then(module => ({ default: module.ReviewPage })))
const IngestionSettingsPage = lazy(() => import("@/pages/ingestion-settings").then(module => ({ default: module.IngestionSettingsPage })))
const PipelinePage = lazy(() => import("@/pages/pipeline").then(module => ({ default: module.PipelinePage })))
const RolesPage = lazy(() => import("@/pages/roles").then(module => ({ default: module.RolesPage })))
const SearchPage = lazy(() => import("@/pages/search").then(module => ({ default: module.SearchPage })))

function Protected({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth()
  if (loading)
    return (
      <Box sx={{ display: "grid", placeItems: "center", minHeight: "100svh" }}>
        <CircularProgress aria-label="در حال بارگذاری" />
      </Box>
    )
  if (!me) return <Navigate to="/login" replace />
  return children
}

function ProtectedShell() {
  return <Protected><AppShell><Outlet /></AppShell></Protected>
}

export default function App() {
  return (
    <Suspense
      fallback={
        <Box
          sx={{ display: "grid", placeItems: "center", minHeight: "100svh" }}
        >
          <CircularProgress aria-label="در حال بارگذاری صفحه" />
        </Box>
      }
    >
      <Routes>
        <Route element={<ProtectedShell />}>
          <Route path="/search" element={<SearchPage />} />
          <Route path="/board" element={<PipelinePage />} />
          <Route path="/roles" element={<RolesPage />} />
          <Route path="/roles/:roleId" element={<PipelinePage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/settings/ingestion" element={<IngestionSettingsPage />} />
          <Route path="/candidates" element={<CandidateBankPage />} />
          <Route path="/candidates/:id" element={<CandidatePage />} />
          <Route path="/resumes" element={<ResumesPage />} />
          <Route path="/upload" element={<UploadPage />} />
        </Route>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="*" element={<Navigate to="/search" replace />} />
      </Routes>
    </Suspense>
  )
}
