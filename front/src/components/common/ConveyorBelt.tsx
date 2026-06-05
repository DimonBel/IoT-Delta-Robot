import { useState, useEffect, memo } from 'react';
import { Box } from '@mui/material';
import { palette } from '../../theme';
import type { BeltItem } from '../../types';

interface ConveyorBeltProps {
  items: BeltItem[];
  running: boolean;
}

function ConveyorBeltComponent({ items, running }: ConveyorBeltProps) {
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    if (!running) return;
    let raf: number;
    const step = () => {
      setOffset((o) => (o + 1.2) % 40);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [running]);

  return (
    <Box
      sx={{
        position: 'relative',
        height: 52,
        overflow: 'hidden',
        background: palette.bg,
        borderRadius: 1,
        border: `1px solid ${palette.surfaceBorder}`,
      }}
    >
      <svg width="100%" height={52} style={{ position: 'absolute', inset: 0 }} preserveAspectRatio="none">
        {Array.from({ length: 22 }, (_, i) => (
          <rect
            key={i}
            x={i * 40 - offset}
            y={18}
            width={28}
            height={16}
            rx={3}
            fill={palette.surface}
            stroke={palette.surfaceBorder}
            strokeWidth={0.5}
          />
        ))}
      </svg>
      {items.map((item) => (
        <Box
          key={item.id}
          sx={{
            position: 'absolute',
            top: '50%',
            transform: 'translateY(-50%)',
            left: `${item.x}%`,
            width: 22,
            height: 22,
            borderRadius: '50%',
            background: `${item.color}18`,
            border: `1px solid ${item.color}44`,
            fontSize: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'left 0.05s linear',
            pointerEvents: 'none',
            userSelect: 'none',
          }}
        >
          {item.emoji}
        </Box>
      ))}
      <Box
        sx={{
          position: 'absolute',
          right: 0,
          top: 0,
          bottom: 0,
          width: 40,
          background: `linear-gradient(to right, transparent, ${palette.bg})`,
        }}
      />
    </Box>
  );
}

export const ConveyorBelt = memo(ConveyorBeltComponent);
