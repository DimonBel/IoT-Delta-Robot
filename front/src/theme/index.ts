import { createTheme } from '@mui/material/styles';

const palette = {
  bg: '#0c0e14',
  surface: '#141722',
  surfaceHover: '#1a1e2e',
  surfaceBorder: '#1f2437',
  border: '#2a3050',
  text: '#d4d8e8',
  textSecondary: '#6b7394',
  textMuted: '#3e4563',
  success: '#22c55e',
  successDim: '#16a34a',
  successBg: 'rgba(34,197,94,0.08)',
  error: '#ef4444',
  errorDim: '#dc2626',
  errorBg: 'rgba(239,68,68,0.08)',
  warning: '#f59e0b',
  warningDim: '#d97706',
  warningBg: 'rgba(245,158,11,0.08)',
  info: '#3b82f6',
  infoBg: 'rgba(59,130,246,0.08)',
  apple: '#ef4444',
  orange: '#f97316',
  veggie: '#22c55e',
  accent: '#3b82f6',
};

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#3b82f6', dark: '#2563eb' },
    secondary: { main: '#6b7394' },
    error: { main: '#ef4444' },
    warning: { main: '#f59e0b' },
    success: { main: '#22c55e' },
    background: {
      default: palette.bg,
      paper: palette.surface,
    },
    text: {
      primary: palette.text,
      secondary: palette.textSecondary,
      disabled: palette.textMuted,
    },
    divider: palette.surfaceBorder,
  },
  typography: {
    fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
    h6: {
      fontWeight: 600,
      fontSize: '0.8125rem',
      color: palette.text,
    },
    body1: {
      fontSize: '0.8125rem',
      color: palette.text,
    },
    body2: {
      fontSize: '0.75rem',
      color: palette.textSecondary,
    },
    caption: {
      fontFamily: "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace",
      fontSize: '0.6875rem',
      color: palette.textSecondary,
    },
    overline: {
      fontFamily: "'Inter', system-ui, sans-serif",
      fontSize: '0.625rem',
      fontWeight: 600,
      letterSpacing: '0.08em',
      textTransform: 'uppercase' as const,
      color: palette.textMuted,
    },
    button: {
      textTransform: 'none' as const,
      fontWeight: 500,
      fontSize: '0.8125rem',
    },
  },
  shape: {
    borderRadius: 6,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: palette.bg,
          color: palette.text,
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 4,
          fontWeight: 500,
          textTransform: 'none',
          fontSize: '0.8125rem',
        },
        contained: {
          boxShadow: 'none',
          '&:hover': { boxShadow: 'none' },
        },
        outlined: {
          borderColor: palette.border,
          '&:hover': {
            borderColor: palette.textSecondary,
            backgroundColor: palette.surfaceHover,
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          border: `1px solid ${palette.surfaceBorder}`,
          backgroundImage: 'none',
          backgroundColor: palette.surface,
        },
      },
    },
    MuiSlider: {
      styleOverrides: {
        root: { height: 3 },
        thumb: { width: 12, height: 12 },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: 4 },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderColor: palette.surfaceBorder,
          fontSize: '0.8125rem',
        },
        head: {
          color: palette.textMuted,
          fontWeight: 600,
          fontSize: '0.6875rem',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          '& .MuiTableCell-root': {
            borderBottom: `1px solid ${palette.border}`,
          },
        },
      },
    },
    MuiButtonGroup: {
      styleOverrides: {
        grouped: {
          borderColor: palette.border,
        },
      },
    },
  },
});

export default theme;
export { palette };
