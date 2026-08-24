import { alpha, createTheme } from '@mui/material/styles'

declare module '@mui/material/styles' {
  interface TypeBackground {
    canvas: string
    container: string
    containerLow: string
    containerHigh: string
    containerHighest: string
  }
}

const primary = '#4563b5'
const secondary = '#008b8b'
const ink = '#202431'
const muted = '#626977'

export const studioTheme = createTheme({
  cssVariables: true,
  palette: {
    mode: 'light',
    primary: { main: primary, dark: '#30498f', light: '#7890d4', contrastText: '#ffffff' },
    secondary: { main: secondary, dark: '#006363', light: '#33a8a8', contrastText: '#ffffff' },
    success: { main: '#138a63', dark: '#0c6146', light: '#3baa82' },
    warning: { main: '#b76a00', dark: '#8a4f00', light: '#d4923a' },
    error: { main: '#c43d4b', dark: '#9a2d39', light: '#d66a74' },
    info: { main: '#3b6aa0', dark: '#2b4e76', light: '#6b90bb' },
    background: {
      default: '#f4f5f8',
      paper: '#ffffff',
      canvas: '#fbfcff',
      containerLow: '#f1f2f6',
      container: '#ebeef5',
      containerHigh: '#e5e9f2',
      containerHighest: '#dce2ee',
    },
    text: { primary: ink, secondary: muted },
    divider: '#d9dde6',
    action: {
      selected: alpha(primary, 0.12),
      hover: alpha(primary, 0.06),
      focus: alpha(primary, 0.16),
    },
  },
  shape: { borderRadius: 12 },
  spacing: 8,
  typography: {
    fontFamily: 'Roboto, system-ui, -apple-system, "Segoe UI", sans-serif',
    fontWeightLight: 400,
    fontWeightRegular: 400,
    fontWeightMedium: 500,
    fontWeightBold: 700,
    h6: { fontWeight: 500, fontSize: '1.25rem', letterSpacing: 0, lineHeight: 1.3 },
    subtitle1: { fontWeight: 500, fontSize: '1rem', letterSpacing: 0.15, lineHeight: 1.4 },
    subtitle2: { fontWeight: 500, fontSize: '0.875rem', letterSpacing: 0.1, lineHeight: 1.45 },
    body1: { fontSize: '0.9375rem', lineHeight: 1.5, letterSpacing: 0.15 },
    body2: { fontSize: '0.8125rem', lineHeight: 1.45, letterSpacing: 0.25 },
    button: { fontWeight: 500, textTransform: 'none', letterSpacing: 0.15 },
    caption: { fontSize: '0.75rem', lineHeight: 1.4, letterSpacing: 0.4 },
    overline: { fontWeight: 500, letterSpacing: 1, fontSize: '0.6875rem' },
  },
  shadows: [
    'none',
    '0px 1px 2px rgba(26, 35, 54, 0.08), 0px 1px 3px 1px rgba(26, 35, 54, 0.06)',
    '0px 1px 2px rgba(26, 35, 54, 0.08), 0px 2px 6px 2px rgba(26, 35, 54, 0.06)',
    '0px 4px 8px 3px rgba(26, 35, 54, 0.06), 0px 1px 3px rgba(26, 35, 54, 0.08)',
    '0px 6px 10px 4px rgba(26, 35, 54, 0.06), 0px 2px 4px rgba(26, 35, 54, 0.08)',
    '0px 8px 12px 6px rgba(26, 35, 54, 0.06), 0px 4px 4px rgba(26, 35, 54, 0.08)',
    'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none',
    'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none',
  ],
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          margin: 0,
          minWidth: 1120,
          overflow: 'hidden',
          backgroundColor: '#f4f5f8',
        },
        '*': {
          boxSizing: 'border-box',
          scrollbarColor: '#aab2c2 #f1f2f6',
          scrollbarWidth: 'thin',
        },
        '*::-webkit-scrollbar': { width: 10, height: 10 },
        '*::-webkit-scrollbar-track': { backgroundColor: '#f1f2f6' },
        '*::-webkit-scrollbar-thumb': {
          backgroundColor: '#aeb7ca',
          border: '2px solid #f1f2f6',
          borderRadius: 8,
        },
        '*::-webkit-scrollbar-thumb:hover': { backgroundColor: '#8d98ae' },
        '*::-webkit-scrollbar-thumb:active': { backgroundColor: '#6f7c95' },
        '@media (forced-colors: active)': {
          '*': { scrollbarColor: 'auto' },
        },
        '@media (prefers-reduced-motion: reduce)': {
          '*, *::before, *::after': {
            animationDuration: '0.01ms !important',
            animationIterationCount: '1 !important',
            transitionDuration: '0.01ms !important',
          },
        },
      },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: { backgroundImage: 'none' },
        rounded: { borderRadius: 16 },
      },
    },
    MuiAppBar: {
      defaultProps: { elevation: 0, color: 'inherit', square: true },
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          color: ink,
        },
      },
    },
    MuiToolbar: {
      styleOverrides: {
        root: { minHeight: '64px !important' },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 20, paddingInline: 20, minHeight: 40 },
        sizeLarge: { borderRadius: 24, minHeight: 44, paddingInline: 24 },
        sizeSmall: { borderRadius: 16, minHeight: 32, paddingInline: 16 },
        contained: { boxShadow: '0 1px 2px rgba(36, 54, 159, 0.24)' },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: { borderRadius: 20 },
        sizeSmall: { borderRadius: 12 },
      },
    },
    MuiFab: {
      styleOverrides: {
        root: { borderRadius: 16, boxShadow: '0 2px 8px rgba(36, 54, 159, 0.28)' },
      },
    },
    MuiTextField: {
      defaultProps: { size: 'small', variant: 'filled' },
    },
    MuiFilledInput: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          backgroundColor: '#ebeef5',
          '&:before': { display: 'none' },
          '&:after': { borderBottomWidth: 2 },
          '&:hover': { backgroundColor: '#e5e9f2' },
          '&.Mui-focused': { backgroundColor: '#e5e9f2' },
          '&.Mui-disabled': { backgroundColor: '#f1f2f6' },
        },
      },
    },
    
    MuiTooltip: {
      defaultProps: { arrow: true, enterDelay: 400 },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 500, borderRadius: 8 },
        sizeSmall: { height: 24, borderRadius: 8 },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: ({ theme }) => ({
          borderRadius: 12,
          marginInline: 4,
          '&.Mui-selected': {
            backgroundColor: alpha(theme.palette.primary.main, 0.12),
            '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.16) },
          },
        }),
      },
    },
    MuiListItemIcon: {
      styleOverrides: {
        root: { minWidth: 36, color: muted },
      },
    },
    MuiTabs: {
      styleOverrides: {
        indicator: { height: 3, borderRadius: '3px 3px 0 0' },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
          minHeight: 48,
        },
      },
    },
    MuiToggleButtonGroup: {
      styleOverrides: {
        root: {
          backgroundColor: '#ebeef5',
          borderRadius: 20,
          padding: 4,
          gap: 0,
        },
        grouped: { margin: 0 },
      },
    },
    MuiToggleButton: {
      styleOverrides: {
        root: {
          border: 0,
          borderRadius: '16px !important',
          textTransform: 'none',
          fontWeight: 500,
          paddingInline: 12,
          color: muted,
          '&.Mui-selected': {
            backgroundColor: '#ffffff',
            color: primary,
            boxShadow: '0 1px 2px rgba(26, 35, 54, 0.12)',
            '&:hover': { backgroundColor: '#ffffff' },
          },
        },
        sizeSmall: { paddingBlock: 4, paddingInline: 10 },
      },
    },
    MuiAlert: {
      defaultProps: { variant: 'standard' },
      styleOverrides: {
        root: { borderRadius: 12 },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: { fontVariantNumeric: 'tabular-nums' },
        head: { fontWeight: 500, backgroundColor: '#f1f2f6', color: muted },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': { backgroundColor: alpha(primary, 0.04) },
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: { height: 3, borderRadius: 0 },
      },
    },
    MuiAccordion: {
      defaultProps: { elevation: 0, disableGutters: true },
      styleOverrides: {
        root: {
          backgroundColor: 'transparent',
          '&:before': { display: 'none' },
        },
      },
    },
    MuiAccordionSummary: {
      styleOverrides: {
        root: {
          minHeight: 44,
          paddingInline: 0,
          '& .MuiAccordionSummary-content': { margin: '8px 0' },
        },
      },
    },
    MuiAccordionDetails: {
      styleOverrides: {
        root: { padding: '0 0 12px' },
      },
    },
    MuiSnackbar: {
      defaultProps: { anchorOrigin: { vertical: 'bottom', horizontal: 'center' } },
    },
    MuiMenu: {
      styleOverrides: {
        paper: { borderRadius: 12, padding: 4, boxShadow: '0px 4px 8px 3px rgba(26, 35, 54, 0.06), 0px 1px 3px rgba(26, 35, 54, 0.08)' },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: { borderRadius: 8, minHeight: 40 },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: { borderColor: '#d9dde6' },
      },
    },
    MuiFormControlLabel: {
      styleOverrides: {
        root: { marginLeft: 0 },
      },
    },
  },
})
