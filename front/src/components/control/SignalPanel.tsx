import { memo } from 'react';
import { Box, Typography } from '@mui/material';
import { palette } from '../../theme';

interface SignalPanelProps {
  connected: boolean;
}

const SIGNAL_DATA = [
  { label: 'Latency', val: '12ms', color: palette.success },
  { label: 'Pkt Loss', val: '0.0%', color: palette.success },
  { label: 'Signal', val: '\u2588\u2588\u2588\u2588\u2591', color: palette.text },
];

function SignalPanelInner({ connected }: SignalPanelProps) {
  return (
    <Box sx={{ background: palette.surface, border: `1px solid ${palette.surfaceBorder}`, borderRadius: 1, p: '14px 16px' }}>
      <Typography sx={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: palette.textMuted, mb: 1 }}>
        Signal
      </Typography>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {SIGNAL_DATA.map((s) => (
          <Box key={s.label} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography sx={{ fontSize: 11, color: palette.textMuted }}>{s.label}</Typography>
            <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: connected ? s.color : palette.textMuted }}>
              {connected ? s.val : '\u2014'}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

export const SignalPanel = memo(SignalPanelInner);
