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

const primary = '#35635d'
const secondary = '#256b8b'
const ink = '#253037'
const muted = '#68747b'

// One border family across 2D, Frame 3D and Continuum 3D.
const borderColor = '#e2e7e4'
const controlRadius = 6
const borderWidth = 1
const emphasisWidth = 2

export const studioTheme = createTheme({
  cssVariables: true,
  palette: {
    mode: 'light',
    primary: { main: primary, dark: '#234a45', light: '#789d96', contrastText: '#ffffff' },
    secondary: { main: secondary, dark: '#164d68', light: '#5896b2', contrastText: '#ffffff' },
    success: { main: '#138a63', dark: '#0c6146', light: '#3baa82' },
    warning: { main: '#b76a00', dark: '#8a4f00', light: '#d4923a' },
    error: { main: '#bd4552', dark: '#9a2d39', light: '#d66a74' },
    info: { main: '#3b6aa0', dark: '#2b4e76', light: '#6b90bb' },
    background: {
      default: '#f4f6f5',
      paper: '#ffffff',
      canvas: '#fcfdfc',
      containerLow: '#f7f9f8',
      container: '#f0f4f2',
      containerHigh: '#e6eeea',
      containerHighest: '#d5e2dc',
    },
    text: { primary: ink, secondary: muted },
    divider: borderColor,
    action: {
      selected: alpha(primary, 0.12),
      hover: alpha(primary, 0.06),
      focus: alpha(primary, 0.16),
    },
  },
  shape: { borderRadius: controlRadius },
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
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
    'none',
  ],
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        ':root': {
          '--studio-control-radius': `${controlRadius}px`,
          '--studio-border-width': `${borderWidth}px`,
          '--studio-emphasis-width': `${emphasisWidth}px`,
        },
        body: {
          margin: 0,
          minWidth: 0,
          overflowX: 'auto',
          overflowY: 'hidden',
          backgroundColor: '#f4f6f5',
        },
        textarea: { resize: 'none' },
        ':focus-visible': { outline: `${emphasisWidth}px solid ${primary}`, outlineOffset: 2 },
        '*': {
          boxSizing: 'border-box',
          scrollbarColor: '#aab2c2 #f7f9f8',
          scrollbarWidth: 'thin',
        },
        '*::-webkit-scrollbar': { width: 10, height: 10 },
        '*::-webkit-scrollbar-track': { backgroundColor: '#f7f9f8' },
        '*::-webkit-scrollbar-thumb': {
          backgroundColor: '#aeb7ca',
          border: '2px solid #f7f9f8',
          borderRadius: controlRadius,
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
        rounded: { borderRadius: controlRadius },
        outlined: { border: `${borderWidth}px solid ${borderColor}` },
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
        root: { borderRadius: controlRadius, whiteSpace: 'nowrap', paddingInline: 14, minHeight: 36 },
        sizeLarge: { borderRadius: controlRadius, minHeight: 38, paddingInline: 18 },
        sizeSmall: { borderRadius: controlRadius, minHeight: 30, paddingInline: 12 },
        contained: { boxShadow: 'none' },
        outlined: {
          borderWidth,
          borderColor,
          '&:hover': { borderColor: 'currentColor', borderWidth },
          '&.MuiButton-colorError': { borderColor: 'var(--mui-palette-error-main)' },
          '&.MuiButton-colorWarning': { borderColor: 'var(--mui-palette-warning-main)' },
          '&.Mui-disabled': { borderColor },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: { borderRadius: controlRadius },
        sizeSmall: { borderRadius: controlRadius },
      },
    },
    MuiFab: {
      styleOverrides: {
        root: { borderRadius: controlRadius, boxShadow: '0 2px 8px rgba(36, 54, 159, 0.28)' },
      },
    },
    MuiTextField: {
      defaultProps: { size: 'small', variant: 'outlined' },
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
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: controlRadius,
          backgroundColor: '#ffffff',
          fontSize: 13,
          '& .MuiOutlinedInput-notchedOutline': { borderColor, borderWidth },
          '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'var(--mui-palette-primary-light)' },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: primary, borderWidth: emphasisWidth },
          '&.Mui-error .MuiOutlinedInput-notchedOutline': { borderColor: 'var(--mui-palette-error-main)' },
          '&.Mui-disabled .MuiOutlinedInput-notchedOutline': { borderColor, borderWidth },
          '&.Mui-disabled': { backgroundColor: '#f7f9f8' },
        },
      },
    },
    MuiInputLabel: { styleOverrides: { root: { fontSize: 13 } } },
    MuiFormHelperText: {
      styleOverrides: { root: { marginLeft: 0, marginRight: 0, fontSize: 11, lineHeight: 1.5 } },
    },
    MuiFilledInput: {
      styleOverrides: {
        root: {
          borderRadius: controlRadius,
          backgroundColor: '#f0f4f2',
          '&:before': { display: 'none' },
          '&:after': { borderBottomWidth: 2 },
          '&:hover': { backgroundColor: '#e6eeea' },
          '&.Mui-focused': { backgroundColor: '#f0f4f2' },
          '&.Mui-disabled': { backgroundColor: '#f7f9f8' },
        },
      },
    },

    MuiTooltip: {
      defaultProps: { arrow: true, enterDelay: 400 },
      styleOverrides: { tooltip: { borderRadius: controlRadius } },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 600, borderRadius: controlRadius, fontVariantNumeric: 'tabular-nums' },
        sizeSmall: { height: 22, borderRadius: controlRadius, fontSize: 11 },
        outlined: { borderWidth, '&.MuiChip-colorDefault': { borderColor } },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: ({ theme }) => ({
          borderRadius: controlRadius,
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
          backgroundColor: '#f0f4f2',
          borderRadius: controlRadius,
          padding: 3,
          gap: 0,
        },
        grouped: { margin: 0 },
      },
    },
    MuiToggleButton: {
      styleOverrides: {
        root: {
          border: 0,
          borderRadius: `${controlRadius}px !important`,
          textTransform: 'none',
          whiteSpace: 'nowrap',
          fontWeight: 500,
          paddingInline: 12,
          color: muted,
          '&.Mui-selected': {
            backgroundColor: '#ffffff',
            color: primary,
            boxShadow: 'none',
            '&:hover': { backgroundColor: '#ffffff' },
          },
        },
        sizeSmall: { paddingBlock: 4, paddingInline: 10 },
      },
    },
    MuiAlert: {
      defaultProps: { variant: 'standard' },
      styleOverrides: {
        root: { borderRadius: controlRadius },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: { fontVariantNumeric: 'tabular-nums', borderBottom: `${borderWidth}px solid ${borderColor}` },
        head: { fontWeight: 600, backgroundColor: '#f7f9f8', color: muted },
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
        paper: {
          borderRadius: controlRadius,
          border: `${borderWidth}px solid ${borderColor}`,
          padding: 4,
          boxShadow: '0px 4px 8px 3px rgba(26, 35, 54, 0.06), 0px 1px 3px rgba(26, 35, 54, 0.08)',
        },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: { borderRadius: controlRadius, minHeight: 40 },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: { borderColor, borderBottomWidth: borderWidth, '&.MuiDivider-vertical': { borderBottomWidth: 0, borderRightWidth: borderWidth } },
      },
    },
    MuiFormControlLabel: {
      styleOverrides: {
        root: { marginLeft: 0 },
      },
    },
  },
})
