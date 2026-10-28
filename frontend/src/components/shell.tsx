import { useState, type ReactNode } from "react"
import { Link, useLocation, useNavigate } from "react-router"
import {
  AppBar,
  Avatar,
  Box,
  Button,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material"
import { FileText, LogOut, Menu, Users } from "lucide-react"
import { useAuth } from "@/auth"
import { logout } from "@/lib/api"

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
  { path: "/candidates", title: "بانک کاندیداها", icon: Users },
  { path: "/resumes", title: "رزومه‌های دریافت‌شده", icon: FileText },
]

export function AppShell({ children }: { children: ReactNode }) {
  const { me, refresh } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const [logoutError, setLogoutError] = useState(false)
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
        مدیریت رزومه‌ها
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
              to="/resumes"
              style={{ textDecoration: "none", color: "inherit" }}
            >
              <Wordmark />
            </Link>
          </Stack>
          <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
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
            top: 72,
            height: "calc(100svh - 72px)",
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
