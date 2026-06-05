import { memo } from 'react';
import { TableRow, TableCell, Typography, Button, Box } from '@mui/material';
import { palette } from '../../theme';

const DELTAS = [-10, -5, -1, 1, 5, 10];

interface AxisRowProps {
  axis: string;
  value: number;
  onAdjust: (axis: string, delta: number) => void;
}

function AxisRowInner({ axis, value, onAdjust }: AxisRowProps) {
  return (
    <TableRow sx={{ '&:hover': { background: palette.surfaceHover } }}>
      <TableCell align="center">
        <Typography
          sx={{
            fontFamily: "'JetBrains Mono', monospace",
            fontWeight: 600,
            fontSize: 12,
            color: palette.text,
          }}
        >
          {axis}
        </Typography>
      </TableCell>
      <TableCell align="center">
        <Typography
          sx={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 12,
            color: palette.text,
          }}
        >
          {value.toFixed(2)}
        </Typography>
      </TableCell>
      <TableCell align="center">
        <Box sx={{ display: 'flex', gap: '2px', justifyContent: 'center' }}>
          {DELTAS.map((delta) => (
            <Button
              key={delta}
              onClick={() => onAdjust(axis, delta)}
              size="small"
              variant="outlined"
              sx={{
                minWidth: '32px',
                px: 0,
                py: '1px',
                fontSize: 11,
                fontFamily: "'JetBrains Mono', monospace",
                borderColor: palette.surfaceBorder,
                color: delta > 0 ? palette.success : palette.error,
                '&:hover': {
                  borderColor: delta > 0 ? palette.success : palette.error,
                  background: delta > 0 ? palette.successBg : palette.errorBg,
                },
              }}
            >
              {delta > 0 ? `+${delta}` : `${delta}`}
            </Button>
          ))}
        </Box>
      </TableCell>
    </TableRow>
  );
}

export const AxisRow = memo(AxisRowInner);
