import { useEffect, useState } from 'react';
import { Box, Typography } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { NavigationTabs } from './NavigationTabs';
import { palette } from '../../theme';

interface AppHeaderProps {
  connected: boolean;
}

interface PersonWarning {
  active: boolean;
  seconds_since: number | null;
  count: number;
}

function usePersonWarning(): PersonWarning {
  const [state, setState] = useState<PersonWarning>({
    active: false,
    seconds_since: null,
    count: 0,
  });
  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const r = await fetch('/person-warning');
        if (r.ok && alive) {
          const data = await r.json();
          setState({
            active: !!data.active,
            seconds_since:
              typeof data.seconds_since === 'number' ? data.seconds_since : null,
            count: typeof data.count === 'number' ? data.count : 0,
          });
        }
      } catch {
        /* server not ready yet */
      }
      if (alive) setTimeout(poll, 700);
    };
    poll();
    return () => {
      alive = false;
    };
  }, []);
  return state;
}

export function AppHeader({ connected }: AppHeaderProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const personWarning = usePersonWarning();

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
        {personWarning.active && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              px: '8px',
              py: '3px',
              borderRadius: '3px',
              background: palette.warningBg,
              border: `1px solid ${palette.warning}66`,
              animation: 'warnPulse 1.6s ease infinite',
            }}
          >
            <style>{'@keyframes warnPulse{0%,100%{opacity:1}50%{opacity:.55}}'}</style>
            <Typography sx={{ fontSize: 13, lineHeight: 1, color: palette.warning }}>
              {'⚠'}
            </Typography>
            <Typography
              sx={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.04em',
                color: palette.warning,
              }}
            >
              PERSON DETECTED
              {personWarning.count > 1 ? ` ×${personWarning.count}` : ''}
            </Typography>
            {personWarning.seconds_since !== null && (
              <Typography
                sx={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10,
                  color: palette.warningDim,
                  ml: 0.25,
                }}
              >
                {`• ${personWarning.seconds_since.toFixed(1)}s`}
              </Typography>
            )}
          </Box>
        )}
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
