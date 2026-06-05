import { Box, Typography } from '@mui/material';
import { palette } from '../../theme';

interface ConnectionIndicatorProps {
  connected: boolean;
}

export function ConnectionIndicator({ connected }: ConnectionIndicatorProps) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
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
  );
}
