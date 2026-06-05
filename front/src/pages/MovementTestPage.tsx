import { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Button,
} from '@mui/material';
import { AxisRow, ActionButtons, StatusLine } from '../components/movement';
import { palette } from '../theme';

const AXES = ['X', 'Y', 'Z', 'U', 'V', 'W'] as const;
type AxisKey = (typeof AXES)[number];

function createInitialState(): Record<AxisKey, number> {
  return { X: 0, Y: 0, Z: 0, U: 0, V: 0, W: 0 };
}

export default function MovementTestPage() {
  const [state, setState] = useState<Record<AxisKey, number>>(createInitialState);
  const [status, setStatus] = useState('idle');

  const adjust = useCallback((axis: string, delta: number) => {
    setState((prev) => ({ ...prev, [axis]: prev[axis as AxisKey] + delta }));
  }, []);

  const sendMove = useCallback(async () => {
    setStatus('sending...');
    try {
      const response = await fetch('/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(state),
      });
      if (!response.ok) { setStatus('send failed'); return; }
      const data = await response.json();
      setStatus(`sent: ${JSON.stringify(data.values)}`);
    } catch { setStatus('send failed'); }
  }, [state]);

  const callIsDelta = useCallback(async () => {
    setStatus('checking is_delta...');
    try {
      const response = await fetch('/is_delta', { method: 'POST' });
      if (!response.ok) { setStatus('is_delta failed'); return; }
      const data = await response.json();
      setStatus(`is_delta: ${data.is_delta}`);
    } catch { setStatus('is_delta failed'); }
  }, []);

  const getPosition = useCallback(async () => {
    setStatus('reading position...');
    try {
      const response = await fetch('/position', { method: 'GET' });
      if (!response.ok) { setStatus('position failed'); return; }
      const data = await response.json();
      if (data.values) {
        setState((prev) => {
          const next = { ...prev };
          AXES.forEach((axis) => {
            if (Object.prototype.hasOwnProperty.call(data.values, axis)) {
              next[axis] = Number(data.values[axis]);
            }
          });
          return next;
        });
      }
      setStatus(`position: ${JSON.stringify(data.values)}`);
    } catch { setStatus('position failed'); }
  }, []);

  const homeAxes = useCallback(async () => {
    setStatus('homing...');
    try {
      const response = await fetch('/home', { method: 'POST' });
      if (!response.ok) { setStatus('home failed'); return; }
      const data = await response.json();
      setStatus(`home: ${data.status}`);
    } catch { setStatus('home failed'); }
  }, []);

  return (
    <Box sx={{ p: 2, maxWidth: 720, mx: 'auto' }}>
      <Typography
        sx={{
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: palette.textMuted,
          mb: 1.5,
        }}
      >
        Movement Test
      </Typography>

      <Paper elevation={0} sx={{ overflow: 'hidden' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell align="center" sx={{ width: 40 }}>Axis</TableCell>
              <TableCell align="center">Position</TableCell>
              <TableCell align="center">Adjust</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {AXES.map((axis) => (
              <AxisRow key={axis} axis={axis} value={state[axis]} onAdjust={adjust} />
            ))}
          </TableBody>
        </Table>
      </Paper>

      <Box sx={{ mt: 1.5, display: 'flex', gap: 1, alignItems: 'center' }}>
        <ActionButtons onIsDelta={callIsDelta} onGetPosition={getPosition} onHome={homeAxes} />
        <Box sx={{ flex: 1 }} />
        <Button variant="contained" onClick={sendMove} size="small" sx={{ fontWeight: 600 }}>
          Send Move
        </Button>
      </Box>

      <StatusLine text={status} />
    </Box>
  );
}
