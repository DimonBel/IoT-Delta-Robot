import { memo } from 'react';
import { palette } from '../../theme';
import type { RobotState } from '../../types';

interface DeltaArmVizProps {
  state: RobotState;
}

const STATE_ARM_COLORS: Record<string, string> = {
  'E-STOP': palette.error,
  RUNNING: palette.text,
  PICK: palette.warning,
  PLACE: palette.warning,
};
const STATE_DOT_COLORS: Record<string, string> = {
  'E-STOP': palette.error,
  IDLE: palette.success,
  RUNNING: palette.success,
  PICK: palette.warning,
  PLACE: palette.warning,
};

function DeltaArmVizComponent({ state }: DeltaArmVizProps) {
  const isRunning = state === 'RUNNING' || state === 'PICK' || state === 'PLACE';
  const isEStop = state === 'E-STOP';
  const isPick = state === 'PICK';
  const isPlace = state === 'PLACE';

  const armCol = STATE_ARM_COLORS[state] || palette.textMuted;
  const dotCol = STATE_DOT_COLORS[state] || palette.textMuted;
  const endY = isPick ? 110 : isPlace ? 68 : 88;

  const arms = [
    { angle: -90, anim: 'arm-a 1.4s ease-in-out infinite' },
    { angle: 30, anim: 'arm-b 1.6s ease-in-out infinite' },
    { angle: 150, anim: 'arm-c 1.5s ease-in-out infinite' },
  ];

  return (
    <svg viewBox="0 0 200 160" width={160} height={128} style={{ display: 'block', margin: '0 auto' }}>
      <style>
        {`
          @keyframes arm-a { 0%,100%{transform:rotate(-12deg);} 50%{transform:rotate(12deg);} }
          @keyframes arm-b { 0%,100%{transform:rotate(12deg);} 50%{transform:rotate(-8deg);} }
          @keyframes arm-c { 0%,100%{transform:rotate(-8deg);} 50%{transform:rotate(14deg);} }
        `}
      </style>
      <rect x="72" y="22" width="56" height="8" rx="4" fill={palette.surfaceBorder} stroke={palette.border} strokeWidth="0.5" />
      {arms.map((arm, i) => {
        const rad = (arm.angle * Math.PI) / 180;
        const bx = 100 + Math.cos(rad) * 22;
        const by = 26 + Math.sin(rad) * 10;
        const tx = 100 + Math.cos(rad) * 40;
        const ty = endY + Math.sin(rad) * 12;
        return (
          <g
            key={i}
            style={{ transformOrigin: `${bx}px ${by}px`, animation: isRunning ? arm.anim : 'none' }}
          >
            <line x1={bx} y1={by} x2={tx} y2={ty} stroke={armCol} strokeWidth="1.8" strokeLinecap="round" opacity={isEStop ? 0.4 : 0.75} />
            <circle cx={bx} cy={by} r={3} fill={armCol} opacity={0.6} />
            <circle cx={tx} cy={ty} r={2} fill={armCol} opacity={0.4} />
          </g>
        );
      })}
      <circle cx={100} cy={endY} r={7} fill={dotCol} opacity={isEStop ? 0.15 : 0.1} style={{ transition: 'cy 0.3s ease' }} />
      <circle
        cx={100}
        cy={endY}
        r={4}
        fill={dotCol}
        style={{
          transition: 'cy 0.3s ease',
          filter: `drop-shadow(0 0 3px ${dotCol}55)`,
        }}
      />
      <rect x="24" y="132" width="152" height="9" rx="3" fill={palette.surfaceBorder} stroke={palette.border} strokeWidth="0.5" />
      <text x="100" y="139.5" textAnchor="middle" fill={palette.textMuted} fontSize="6.5" fontFamily="'JetBrains Mono', monospace" letterSpacing="0.08em">
        CONVEYOR
      </text>
    </svg>
  );
}

export const DeltaArmViz = memo(DeltaArmVizComponent);
