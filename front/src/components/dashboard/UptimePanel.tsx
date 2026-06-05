import { useState, memo } from 'react';
import { Box, Typography } from '@mui/material';
import { palette } from '../../theme';
import type { UptimeSegment } from '../../types';
import { UPTIME_SEGMENTS, UPTIME_TYPE_META } from '../../constants';

function UptimePanelComponent() {
  const [hovered, setHovered] = useState<UptimeSegment | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const totalHours = UPTIME_SEGMENTS.reduce((s, seg) => s + seg.hours, 0);
  const summary: Record<string, number> = {};
  UPTIME_SEGMENTS.forEach((seg) => {
    summary[seg.type] = (summary[seg.type] || 0) + seg.hours;
  });
  const uptime = (((summary['work'] || 0) / totalHours) * 100).toFixed(1);

  const handleMouseMove = (e: React.MouseEvent, seg: UptimeSegment) => {
    const root = (e.currentTarget as HTMLElement).closest('[data-uptime-root]');
    if (!root) return;
    const rect = root.getBoundingClientRect();
    setTooltipPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    setHovered(seg);
  };

  return (
    <Box
      data-uptime-root="1"
      sx={{
        background: palette.surface,
        border: `1px solid ${palette.surfaceBorder}`,
        borderRadius: 1,
        p: '14px 16px',
        position: 'relative',
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Typography
          sx={{
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: palette.textMuted,
          }}
        >
          System Uptime &mdash; Today
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Typography
            sx={{
              fontFamily: "'JetBrains Mono', monospace",
              fontWeight: 400,
              fontSize: 18,
              color: palette.success,
              lineHeight: 1,
            }}
          >
            {uptime}%
          </Typography>
          <Typography sx={{ fontSize: 10, color: palette.textMuted }}>uptime</Typography>
        </Box>
      </Box>

      <Box
        sx={{
          display: 'flex',
          borderRadius: '3px',
          overflow: 'hidden',
          height: 28,
          mb: 1,
          gap: '1px',
        }}
        onMouseLeave={() => setHovered(null)}
      >
        {UPTIME_SEGMENTS.map((seg, i) => (
          <Box
            key={i}
            onMouseMove={(e) => handleMouseMove(e, seg)}
            onMouseEnter={(e) => handleMouseMove(e, seg)}
            sx={{
              flex: seg.hours,
              background: seg.color,
              opacity: hovered ? (hovered === seg ? 0.9 : 0.2) : 0.5,
              cursor: 'pointer',
              transition: 'opacity 0.1s',
            }}
          />
        ))}
      </Box>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1.5 }}>
        {['06', '08', '10', '12', '14', '16', '18'].map((t) => (
          <Typography key={t} sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: palette.textMuted }}>
            {t}:00
          </Typography>
        ))}
      </Box>

      <Box sx={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        {Object.entries(summary).map(([type, hrs]) => {
          const meta = UPTIME_TYPE_META[type as UptimeSegment['type']];
          const seg = UPTIME_SEGMENTS.find((s) => s.type === type)!;
          return (
            <Box
              key={type}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                px: '8px',
                py: '4px',
                borderRadius: '3px',
                background: hovered?.type === type ? `${seg.color}12` : palette.bg,
                border: `1px solid ${hovered?.type === type ? `${seg.color}30` : palette.surfaceBorder}`,
                transition: 'all 0.1s',
                cursor: 'default',
              }}
            >
              <Box sx={{ width: 6, height: 6, borderRadius: '1px', background: seg.color, opacity: 0.6 }} />
              <Typography sx={{ fontSize: 11, color: palette.text }}>{meta.label}</Typography>
              <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: palette.textMuted }}>
                {(hrs as number).toFixed(1)}h
              </Typography>
            </Box>
          );
        })}
      </Box>

      {hovered && (
        <Box
          sx={{
            position: 'absolute',
            left: Math.min(tooltipPos.x + 10, 440),
            top: tooltipPos.y - 8,
            background: '#1a1e2e',
            border: `1px solid ${palette.border}`,
            color: palette.text,
            borderRadius: '4px',
            p: '10px 14px',
            width: 240,
            pointerEvents: 'none',
            zIndex: 10,
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: '4px' }}>
            <Typography sx={{ fontWeight: 600, fontSize: 12 }}>{hovered.label}</Typography>
            <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: palette.textMuted }}>
              {hovered.start}&ndash;{hovered.end}
            </Typography>
          </Box>
          <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: palette.textMuted, mb: '6px' }}>
            {hovered.hours.toFixed(1)}h &middot; {((hovered.hours / totalHours) * 100).toFixed(0)}%
          </Typography>
          <Typography sx={{ fontSize: 11, lineHeight: 1.5, color: palette.textSecondary }}>
            {hovered.detail}
          </Typography>
        </Box>
      )}
    </Box>
  );
}

export const UptimePanel = memo(UptimePanelComponent);
