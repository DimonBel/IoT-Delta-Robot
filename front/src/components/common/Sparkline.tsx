import { memo } from 'react';

interface SparklineProps {
  data: number[];
  color: string;
  width?: number;
  height?: number;
}

function SparklineComponent({ data, color, width = 80, height = 24 }: SparklineProps) {
  const max = Math.max(...data, 1);
  const pts = data
    .map((v, i) => `${(i / (data.length - 1)) * width},${height - (v / max) * (height - 4) - 2}`)
    .join(' ');
  const last = pts.split(' ').slice(-1)[0].split(',');

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth={1.2}
        strokeLinejoin="round"
        opacity={0.5}
      />
      <circle cx={last[0]} cy={last[1]} r={2.5} fill={color} opacity={0.8} />
    </svg>
  );
}

export const Sparkline = memo(SparklineComponent);
