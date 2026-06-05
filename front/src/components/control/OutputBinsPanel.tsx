import { memo } from 'react';
import { Box, Typography } from '@mui/material';
import { OUTPUT_BINS } from '../../constants';
import { palette } from '../../theme';

function OutputBinsPanelInner() {
  return (
    <Box sx={{ background: palette.surface, border: `1px solid ${palette.surfaceBorder}`, borderRadius: 1, p: '14px 16px' }}>
      <Typography sx={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: palette.textMuted, mb: 1.5 }}>
        Output Bins
      </Typography>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {OUTPUT_BINS.map((b) => (
          <Box key={b.label}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: '4px' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Typography sx={{ fontSize: 12 }}>{b.emoji}</Typography>
                <Typography sx={{ fontSize: 12 }}>{b.label}</Typography>
              </Box>
              <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: b.fill > 80 ? palette.error : palette.textMuted }}>
                {b.fill}%
              </Typography>
            </Box>
            <Box sx={{ height: 2, background: palette.surfaceBorder, borderRadius: 1, overflow: 'hidden' }}>
              <Box sx={{ height: '100%', width: `${b.fill}%`, background: b.color, borderRadius: 1, opacity: 0.5 }} />
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

export const OutputBinsPanel = memo(OutputBinsPanelInner);
