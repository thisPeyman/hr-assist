import type { ReactNode } from "react"
import { CacheProvider } from "@emotion/react"
import createCache from "@emotion/cache"
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material"
import { faIR } from "@mui/material/locale"
import rtlPlugin from "@mui/stylis-plugin-rtl"
import { prefixer } from "stylis"

const cache = createCache({
  key: "mui-rtl",
  stylisPlugins: [prefixer, rtlPlugin],
})
const theme = createTheme(
  {
    direction: "rtl",
    palette: {
      primary: { main: "#1565c0" },
      background: { default: "#f5f7fa", paper: "#ffffff" },
      text: { primary: "#172b4d", secondary: "#64748b" },
      divider: "#e3e8ef",
    },
    typography: {
      fontFamily: '"Vazirmatn Variable", sans-serif',
      fontSize: 14,
      h4: { fontWeight: 750, fontSize: "1.75rem" },
      h5: { fontWeight: 700, fontSize: "1.25rem" },
      h6: { fontWeight: 700, fontSize: "1rem" },
      button: { textTransform: "none", fontWeight: 600 },
    },
    shape: { borderRadius: 10 },
    components: {
      MuiButton: { defaultProps: { disableElevation: true } },
      MuiPaper: { defaultProps: { elevation: 0 } },
      MuiTableCell: {
        styleOverrides: { head: { background: "#f8fafc", fontWeight: 700 } },
      },
      MuiTextField: { defaultProps: { size: "small" } },
    },
  },
  faIR,
)

export function AppTheme({ children }: { children: ReactNode }) {
  return (
    <CacheProvider value={cache}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </CacheProvider>
  )
}
