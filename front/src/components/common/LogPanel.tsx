import { useEffect, useRef, memo } from 'react';
import { Box, Typography } from '@mui/material';
import { palette } from '../../theme';
import type { LogEntry } from '../../types';

const TYPE_COLORS: Record<string, string> = {
  ok: palette.success,
  warn: palette.warning,
  err: palette.error,
  info: palette.textSecondary,
  cmd: palette.info,
};

interface LogPanelProps {
  entries: LogEntry[];
  maxHeight?: number;
}

function LogPanelComponent({ entries, maxHeight = 200 }: LogPanelProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (endRef.current) {
      const p = endRef.current.parentNode as HTMLElement;
      if (p) p.scrollTop = p.scrollHeight;
    }
  }, [entries]);

  return (
    <Box
      sx={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
        height: maxHeight,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '2px',
        py: 0.5,
        '&::-webkit-scrollbar': { width: 3 },
        '&::-webkit-scrollbar-track': { background: 'transparent' },
        '&::-webkit-scrollbar-thumb': { background: palette.border, borderRadius: 2 },
      }}
    >
      {entries.map((e) => (
        <Box
          key={e.id}
          sx={{
            display: 'flex',
            gap: '8px',
            alignItems: 'flex-start',
            px: '2px',
            py: '1px',
            '&:hover': { background: palette.surfaceHover },
          }}
        >
          <Typography
            component="span"
            sx={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10,
              color: palette.textMuted,
              whiteSpace: 'nowrap',
              flexShrink: 0,
              lineHeight: '16px',
            }}
          >
            {e.time}
          </Typography>
          <Box
            sx={{
              width: 4,
              height: 4,
              borderRadius: '50%',
              background: TYPE_COLORS[e.type] || palette.textMuted,
              mt: '6px',
              flexShrink: 0,
            }}
          />
          <Typography
            component="span"
            sx={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11,
              color: e.type === 'err' ? palette.error : e.type === 'cmd' ? palette.info : palette.text,
              lineHeight: '16px',
            }}
          >
            {e.msg}
          </Typography>
        </Box>
      ))}
      <div ref={endRef} />
    </Box>
  );
}

export const LogPanel = memo(LogPanelComponent);
