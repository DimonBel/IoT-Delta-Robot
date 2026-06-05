import { createTheme } from '@mui/material/styles';

const palette = {
  bg: '#f4f6fb',
  surface: '#ffffff',
  surfaceHover: '#f1f4fb',
  surfaceBorder: '#e4e8f1',
  border: '#d6dce8',
  text: '#1b2433',
  textSecondary: '#4f5b70',
  textMuted: '#7d889d',
  success: '#1f8f5f',
  successDim: '#197348',
  successBg: 'rgba(31,143,95,0.12)',
  error: '#c43d3d',
  errorDim: '#a93333',
  errorBg: 'rgba(196,61,61,0.12)',
  warning: '#b56a1a',
  warningDim: '#935616',
  warningBg: 'rgba(181,106,26,0.12)',
  info: '#2a6df4',
  infoBg: 'rgba(42,109,244,0.12)',
  apple: '#e24a4a',
  orange: '#d97321',
  veggie: '#1f8f5f',
  accent: '#2a6df4',
};

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: palette.accent, dark: '#1f5ad0' },
    secondary: { main: palette.textSecondary },
    error: { main: palette.error },
    warning: { main: palette.warning },
    success: { main: palette.success },
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
    fontFamily: "'Space Grotesk', system-ui, -apple-system, sans-serif",
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
      fontFamily: "'IBM Plex Mono', 'Fira Code', 'SF Mono', monospace",
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
          borderRadius: 6,
          fontWeight: 600,
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
            backgroundColor: '#f5f7fc',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 8,
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
