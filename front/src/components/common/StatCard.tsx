import { memo } from 'react';
import { Box, Typography } from '@mui/material';
import { palette } from '../../theme';

interface StatCardProps {
  label: string;
  value: React.ReactNode;
  unit?: string;
  dot?: boolean;
  dotOn?: boolean;
}

function StatCardComponent({ label, value, unit, dot = false, dotOn = false }: StatCardProps) {
  return (
    <Box
      sx={{
        background: palette.surface,
        border: `1px solid ${palette.surfaceBorder}`,
        borderRadius: 1,
        p: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
      }}
    >
      <Typography
        sx={{
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: palette.textMuted,
        }}
      >
        {label}
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        {dot && (
          <Box
            sx={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              flexShrink: 0,
              background: dotOn ? palette.success : palette.textMuted,
              boxShadow: dotOn ? `0 0 6px ${palette.success}44` : 'none',
            }}
          />
        )}
        <Typography
          sx={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 18,
            fontWeight: 500,
            color: palette.text,
            letterSpacing: '-0.02em',
            lineHeight: 1,
          }}
        >
          {value}
        </Typography>
        {unit && (
          <Typography sx={{ fontSize: 11, color: palette.textMuted, ml: '2px' }}>
            {unit}
          </Typography>
        )}
      </Box>
    </Box>
  );
}

export const StatCard = memo(StatCardComponent);
