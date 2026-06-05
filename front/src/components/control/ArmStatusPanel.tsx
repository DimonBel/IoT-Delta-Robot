import { memo } from 'react';
import { Box, Typography } from '@mui/material';
import { DeltaArmViz } from '../common';
import { palette } from '../../theme';
import type { RobotState } from '../../types';

const STATE_COLORS: Record<RobotState, string> = {
  OFFLINE: palette.textMuted,
  IDLE: palette.success,
  RUNNING: palette.success,
  PICK: palette.warning,
  PLACE: palette.warning,
  'E-STOP': palette.error,
  HOMING: palette.info,
};

interface ArmStatusPanelProps {
  state: RobotState;
}

function ArmStatusPanelInner({ state }: ArmStatusPanelProps) {
  const stateColor = STATE_COLORS[state] || palette.textMuted;

  return (
    <Box sx={{ background: palette.surface, border: `1px solid ${palette.surfaceBorder}`, borderRadius: 1, p: '14px 16px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
      <Typography sx={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: palette.textMuted, alignSelf: 'flex-start' }}>
        Arm Status
      </Typography>
      <DeltaArmViz state={state} />
      <Box sx={{ display: 'flex', alignItems: 'center', gap: '6px', px: '10px', py: '3px', borderRadius: '3px', background: `${stateColor}10` }}>
        <Box sx={{ width: 5, height: 5, borderRadius: '50%', background: stateColor, animation: state === 'RUNNING' ? 'blink 1.4s infinite' : 'none' }} />
        <style>{'@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}'}</style>
        <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: stateColor, letterSpacing: '0.06em', fontWeight: 500 }}>
          {state}
        </Typography>
      </Box>
    </Box>
  );
}

export const ArmStatusPanel = memo(ArmStatusPanelInner);
