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

const primary = '#0f766e'
const secondary = '#256b8b'
const ink = '#20323a'
const muted = '#5e7077'

export const studioTheme = createTheme({
  cssVariables: true,
  palette: {
    mode: 'light',
    primary: { main: primary, dark: '#115e59', light: '#4aa69d', contrastText: '#ffffff' },
    secondary: { main: secondary, dark: '#164d68', light: '#5896b2', contrastText: '#ffffff' },
    success: { main: '#138a63', dark: '#0c6146', light: '#3baa82' },
    warning: { main: '#b76a00', dark: '#8a4f00', light: '#d4923a' },
    error: { main: '#bd4552', dark: '#9a2d39', light: '#d66a74' },
    info: { main: '#3b6aa0', dark: '#2b4e76', light: '#6b90bb' },
    background: {
      default: '#edf1f1',
      paper: '#ffffff',
      canvas: '#fafcfb',
      containerLow: '#f2f5f4',
      container: '#eaf0ee',
      containerHigh: '#e0e9e6',
      containerHighest: '#d5e2de',
    },
    text: { primary: ink, secondary: muted },
    divider: '#d8e2df',
    action: {
      selected: alpha(primary, 0.12),
      hover: alpha(primary, 0.06),
      focus: alpha(primary, 0.16),
    },
  },
  shape: { borderRadius: 6 },
  spacing: 8,
  typography: {
    fontFamily: '"Avenir Next", "Segoe UI", system-ui, -apple-system, sans-serif',
    fontWeightLight: 400,
    fontWeightRegular: 400,
    fontWeightMedium: 500,
    fontWeightBold: 700,
    h6: { fontWeight: 600, fontSize: '1.125rem', letterSpacing: 0, lineHeight: 1.3 },
    subtitle1: { fontWeight: 600, fontSize: '1rem', letterSpacing: 0.15, lineHeight: 1.4 },
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
          minWidth: 0,
          overflowX: 'auto',
          overflowY: 'hidden',
          backgroundColor: '#edf1f1',
        },
        'textarea': { resize: 'none' },
        ':focus-visible': { outline: '2px solid #0f766e', outlineOffset: 2 },
        '*': {
          boxSizing: 'border-box',
          scrollbarColor: '#aab2c2 #f2f5f4',
          scrollbarWidth: 'thin',
        },
        '*::-webkit-scrollbar': { width: 10, height: 10 },
        '*::-webkit-scrollbar-track': { backgroundColor: '#f2f5f4' },
        '*::-webkit-scrollbar-thumb': {
          backgroundColor: '#aeb7ca',
          border: '2px solid #f2f5f4',
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
        rounded: { borderRadius: 8 },
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
        root: { minHeight: '56px !important' },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 6, whiteSpace: 'nowrap', paddingInline: 14, minHeight: 36 },
        sizeLarge: { borderRadius: 6, minHeight: 38, paddingInline: 18 },
        sizeSmall: { borderRadius: 6, minHeight: 30, paddingInline: 12 },
        contained: { boxShadow: '0 1px 2px rgba(36, 54, 159, 0.24)' },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: { borderRadius: 6 },
        sizeSmall: { borderRadius: 6 },
      },
    },
    MuiFab: {
      styleOverrides: {
        root: { borderRadius: 6, boxShadow: '0 2px 8px rgba(36, 54, 159, 0.28)' },
      },
    },
    MuiTextField: {
      defaultProps: { size: 'small', variant: 'filled' },
    },
    MuiSelect: {
      defaultProps: {
        MenuProps: {
          slotProps: {
            paper: {
              sx: {
                width: 'min-content',
                '& .MuiMenuItem-root': { whiteSpace: 'normal', overflowWrap: 'anywhere' },
              },
            },
          },
        },
      },
    },
    MuiFilledInput: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          backgroundColor: '#eaf0ee',
          '&:before': { display: 'none' },
          '&:after': { borderBottomWidth: 2 },
          '&:hover': { backgroundColor: '#e0e9e6' },
          '&.Mui-focused': { backgroundColor: '#eaf0ee' },
          '&.Mui-disabled': { backgroundColor: '#f2f5f4' },
        },
      },
    },
    
    MuiTooltip: {
      defaultProps: { arrow: true, enterDelay: 400 },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 600, borderRadius: 5, fontVariantNumeric: 'tabular-nums' },
        sizeSmall: { height: 24, borderRadius: 8 },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: ({ theme }) => ({
          borderRadius: 6,
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
          backgroundColor: '#eaf0ee',
          borderRadius: 6,
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
          borderRadius: '5px !important',
          textTransform: 'none',
          whiteSpace: 'nowrap',
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
        root: { borderRadius: 6 },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: { fontVariantNumeric: 'tabular-nums' },
        head: { fontWeight: 600, backgroundColor: '#f2f5f4', color: muted },
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
        paper: { borderRadius: 6, padding: 4, boxShadow: '0px 4px 8px 3px rgba(26, 35, 54, 0.06), 0px 1px 3px rgba(26, 35, 54, 0.08)' },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: { borderRadius: 8, minHeight: 40 },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: { borderColor: '#d8e2df' },
      },
    },
    MuiFormControlLabel: {
      styleOverrides: {
        root: { marginLeft: 0 },
      },
    },
  },
})
