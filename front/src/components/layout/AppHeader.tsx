import { Box, Typography } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { NavigationTabs } from './NavigationTabs';
import { palette } from '../../theme';

interface AppHeaderProps {
  connected: boolean;
}

export function AppHeader({ connected }: AppHeaderProps) {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <Box
      sx={{
        height: 48,
        background: palette.surface,
        borderBottom: `1px solid ${palette.surfaceBorder}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        px: 3,
        flexShrink: 0,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <svg width="18" height="18" viewBox="0 0 28 28" fill="none">
            <polygon
              points="14,3 25,23 3,23"
              stroke={palette.text}
              strokeWidth="1.5"
              fill="none"
              strokeLinejoin="round"
            />
            <circle cx="14" cy="13" r="2" fill={palette.textSecondary} />
            <line x1="14" y1="11" x2="14" y2="5" stroke={palette.textSecondary} strokeWidth="1.2" />
            <line x1="14" y1="15" x2="9" y2="22" stroke={palette.textSecondary} strokeWidth="1.2" />
            <line x1="14" y1="15" x2="19" y2="22" stroke={palette.textSecondary} strokeWidth="1.2" />
          </svg>
          <Typography
            sx={{
              fontSize: 13,
              fontWeight: 600,
              color: palette.text,
              letterSpacing: '-0.01em',
            }}
          >
            CDR-01
          </Typography>
          <Typography
            sx={{
              fontSize: 11,
              color: palette.textMuted,
              fontFamily: "'JetBrains Mono', monospace",
              ml: -0.5,
            }}
          >
            v2.4.1
          </Typography>
        </Box>
        <Box
          sx={{
            width: 1,
            height: 20,
            background: palette.surfaceBorder,
          }}
        />
        <NavigationTabs currentPath={location.pathname} onNavigate={navigate} />
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Box
          sx={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: connected ? palette.success : palette.textMuted,
          }}
        />
        <Typography
          sx={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
            color: connected ? palette.success : palette.textMuted,
          }}
        >
          {connected ? 'ONLINE' : 'OFFLINE'}
        </Typography>
      </Box>
    </Box>
  );
}
