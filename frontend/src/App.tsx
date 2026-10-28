import { lazy, Suspense } from "react"
import { Navigate, Route, Routes } from "react-router"
import { Box, CircularProgress } from "@mui/material"
import { useAuth } from "@/auth"
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
        <Route
          path="/candidates"
          element={
            <Protected>
              <CandidateBankPage />
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
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route
          path="/resumes"
          element={
            <Protected>
              <ResumesPage />
            </Protected>
          }
        />
        <Route
          path="/upload"
          element={
            <Protected>
              <UploadPage />
            </Protected>
          }
        />
        <Route path="*" element={<Navigate to="/resumes" replace />} />
      </Routes>
    </Suspense>
  )
}
