import { memo } from 'react';
import { Box, Typography } from '@mui/material';
import { palette } from '../../theme';

interface StatusLineProps {
  text: string;
}

function StatusLineInner({ text }: StatusLineProps) {
  return (
    <Box sx={{ mt: 1, py: '6px', px: '8px', background: palette.bg, borderRadius: '3px', border: `1px solid ${palette.surfaceBorder}` }}>
      <Typography
        sx={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          color: text.includes('failed') ? palette.error : palette.textSecondary,
        }}
      >
        {text}
      </Typography>
    </Box>
  );
}

export const StatusLine = memo(StatusLineInner);
