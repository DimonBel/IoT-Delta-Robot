import { memo } from 'react';
import { Box, Typography, Button } from '@mui/material';
import { CONNECTION_INFO } from '../../constants';
import { palette } from '../../theme';

interface ConnectionPanelProps {
  connected: boolean;
  connecting: boolean;
  elapsed: number;
  onConnect: () => void;
  onDisconnect: () => void;
}

function ConnectionPanelInner({ connected, connecting, elapsed, onConnect, onDisconnect }: ConnectionPanelProps) {
  const fmt = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return [h, m, sec].map((v) => String(v).padStart(2, '0')).join(':');
  };

  const rows = [
    { label: 'HOST', val: CONNECTION_INFO.host },
    { label: 'PROTO', val: CONNECTION_INFO.protocol },
    ...(connected ? [{ label: 'SESSION', val: fmt(elapsed), highlight: true }] : []),
  ];

  return (
    <Box sx={{ background: palette.surface, border: `1px solid ${palette.surfaceBorder}`, borderRadius: 1, p: '14px 16px' }}>
      <Typography sx={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: palette.textMuted, mb: 1.5 }}>
        Connection
      </Typography>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: '4px', mb: 1.5 }}>
        {rows.map((r) => (
          <Box key={r.label} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: '2px', px: '6px', background: palette.bg, borderRadius: '3px' }}>
            <Typography sx={{ fontSize: 10, color: palette.textMuted, fontWeight: 600 }}>{r.label}</Typography>
            <Typography
              sx={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                color: 'highlight' in r && r.highlight ? palette.success : palette.text,
              }}
            >
              {r.val}
            </Typography>
          </Box>
        ))}
      </Box>
      {!connected ? (
        <Button fullWidth onClick={onConnect} disabled={connecting} variant="contained" size="small" sx={{ py: '6px' }}>
          {connecting ? 'Connecting\u2026' : 'Connect'}
        </Button>
      ) : (
        <Button fullWidth variant="outlined" onClick={onDisconnect} size="small" sx={{ py: '5px', color: palette.textSecondary, borderColor: palette.surfaceBorder }}>
          Disconnect
        </Button>
      )}
    </Box>
  );
}

export const ConnectionPanel = memo(ConnectionPanelInner);
