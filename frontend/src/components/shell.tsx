import { useEffect, useState, type ReactNode } from "react"
import { Link, useLocation, useNavigate } from "react-router"
import {
  AppBar,
  Avatar,
  Box,
  Button,
  Chip,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  TextField,
  Toolbar,
  Typography,
} from "@mui/material"
import { BriefcaseBusiness, Columns3, FileText, Inbox, LogOut, Menu, Search, Settings, Users } from "lucide-react"
import { useAuth } from "@/auth"
import { fetchIngestionSettings, logout } from "@/lib/api"

export function Wordmark() {
  return (
    <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
      <Avatar
        variant="rounded"
        sx={{ bgcolor: "primary.main", width: 38, height: 38 }}
      >
        <FileText size={21} />
      </Avatar>
      <Typography sx={{ fontWeight: 750, fontSize: { xs: 14, sm: 16 } }}>
        دستیار منابع انسانی
      </Typography>
    </Stack>
  )
}

const navigation = [
  { path: "/search", title: "جست‌وجوی کاندیدا", icon: Search },
  { path: "/board", title: "برد استخدام", icon: Columns3 },
  { path: "/roles", title: "فرصت‌های شغلی", icon: BriefcaseBusiness },
  { path: "/candidates", title: "بانک کاندیداها", icon: Users },
  { path: "/resumes", title: "رزومه‌های دریافت‌شده", icon: FileText },
  { path: "/review", title: "صف بازبینی", icon: Inbox },
  { path: "/settings/ingestion", title: "تنظیمات دریافت", icon: Settings },
]

export function AppShell({ children }: { children: ReactNode }) {
  const { me, refresh } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const [logoutError, setLogoutError] = useState(false)
  const [reviewCount, setReviewCount] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  useEffect(() => {
    let active = true
    const load = () => {
      fetchIngestionSettings().then(data => { if (active) setReviewCount(data.review_count) })
        .catch(() => { if (active) setReviewCount(null) })
    }
    load()
    window.addEventListener("ingestion-changed", load)
    window.addEventListener("focus", load)
    return () => {
      active = false
      window.removeEventListener("ingestion-changed", load)
      window.removeEventListener("focus", load)
    }
  }, [])
  async function signOut() {
    setLeaving(true)
    try {
      await logout()
      await refresh()
      navigate("/login")
    } catch {
      setLogoutError(true)
    } finally {
      setLeaving(false)
    }
  }
  const menu = (
    <Box sx={{ px: 1.5, py: 3 }}>
      <Typography sx={{ px: 1.5, color: "text.secondary", fontSize: 11 }}>
        فضای کار استخدام
      </Typography>
      <List sx={{ mt: 1 }}>
        {navigation.map(({ path, title, icon: Icon }) => (
          <ListItemButton
            key={path}
            component={Link}
            to={path}
            selected={pathname === path || pathname.startsWith(path + "/")}
            onClick={() => setOpen(false)}
            sx={{
              borderRadius: 1,
              mb: 1,
              py: 1.25,
              "&.Mui-selected": { bgcolor: "#eaf2fc", color: "primary.main" },
            }}
          >
            <ListItemIcon sx={{ minWidth: 34, color: "inherit" }}>
              <Icon size={19} />
            </ListItemIcon>
            <ListItemText
              primary={title}
              slotProps={{ primary: { sx: { fontSize: 13, fontWeight: 600 } } }}
            />
            {path === "/review" && reviewCount !== null && <Chip size="small" color={reviewCount ? "warning" : "default"} label={reviewCount.toLocaleString("fa-IR")} />}
          </ListItemButton>
        ))}
      </List>
    </Box>
  )
  return (
    <Box sx={{ minHeight: "100svh" }}>
      <AppBar
        position="sticky"
        color="inherit"
        elevation={0}
        sx={{ borderBottom: 1, borderColor: "divider" }}
      >
        <Toolbar
          sx={{
            minHeight: "72px !important",
            gap: 2,
            justifyContent: "space-between",
          }}
        >
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <IconButton
              aria-label="باز کردن منو"
              onClick={() => setOpen(true)}
              sx={{ display: { md: "none" } }}
            >
              <Menu size={22} />
            </IconButton>
            <Link
              to="/search"
              style={{ textDecoration: "none", color: "inherit" }}
            >
              <Wordmark />
            </Link>
          </Stack>
          <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
            <Button component={Link} to="/review" size="small" aria-label={`صف بازبینی؛ ${reviewCount === null ? "شمارش در دسترس نیست" : reviewCount.toLocaleString("fa-IR") + " مورد"}`}>
              بازبینی {reviewCount === null ? "—" : reviewCount.toLocaleString("fa-IR")}
            </Button>
            <Box
              sx={{ display: { xs: "none", sm: "block" }, textAlign: "right" }}
            >
              <Typography sx={{ fontSize: 12, fontWeight: 650 }}>
                {me?.org.name}
              </Typography>
              <Typography
                color="text.secondary"
                dir="ltr"
                sx={{ fontSize: 11 }}
              >
                {me?.email}
              </Typography>
            </Box>
            <Button
              color={logoutError ? "error" : "inherit"}
              size="small"
              disabled={leaving}
              onClick={() => void signOut()}
              startIcon={<LogOut size={16} />}
            >
              {logoutError ? "تلاش دوباره برای خروج" : "خروج"}
            </Button>
          </Stack>
        </Toolbar>
        {pathname !== "/search" ? <Box component="form" onSubmit={e => { e.preventDefault(); if (searchQuery.trim()) navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`) }} sx={{ display: "flex", gap: 1, px: { xs: 2, sm: 3 }, pb: 1.5 }}>
          <TextField size="small" fullWidth label="جست‌وجو در تمام بانک کاندیداها" placeholder="مهارت، صنعت، سابقه…" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} slotProps={{ htmlInput: { maxLength: 1000 } }} />
          <Button type="submit" disabled={!searchQuery.trim()} startIcon={<Search size={17} />}>جست‌وجو</Button>
        </Box> : null}
      </AppBar>
      <Box sx={{ display: "flex", alignItems: "flex-start" }}>
        <Box
          component="aside"
          sx={{
            display: { xs: "none", md: "block" },
            width: 236,
            flexShrink: 0,
            bgcolor: "background.paper",
            borderInlineEnd: "1px solid",
            borderColor: "divider",
            position: "sticky",
            top: pathname === "/search" ? 72 : 128,
            height: pathname === "/search" ? "calc(100svh - 72px)" : "calc(100svh - 128px)",
          }}
        >
          {menu}
        </Box>
        <Box
          component="main"
          sx={{
            flex: 1,
            minWidth: 0,
            maxWidth: 1500,
            mx: "auto",
            p: { xs: 2, sm: 3, lg: 4 },
          }}
        >
          {children}
        </Box>
      </Box>
      <Drawer anchor="left" open={open} onClose={() => setOpen(false)}>
        <Box sx={{ width: 260, p: 2 }}>
          <Wordmark />
        </Box>
        <Divider />
        {menu}
      </Drawer>
    </Box>
  )
}
