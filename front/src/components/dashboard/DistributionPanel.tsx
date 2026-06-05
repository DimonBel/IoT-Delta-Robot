import { memo } from 'react';
import { Box, Typography } from '@mui/material';
import { palette } from '../../theme';
import type { Category } from '../../types';

interface DistributionPanelProps {
  categories: Category[];
  counts: Record<string, number>;
  total: number;
}

function DistributionPanelInner({ categories, counts, total }: DistributionPanelProps) {
  return (
    <Box
      sx={{
        background: palette.surface,
        border: `1px solid ${palette.surfaceBorder}`,
        borderRadius: 1,
        p: '14px 16px',
      }}
    >
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
        Distribution
      </Typography>
      {total === 0 ? (
        <Typography sx={{ color: palette.textMuted, textAlign: 'center', py: 2, fontSize: 12 }}>
          Awaiting data&hellip;
        </Typography>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {categories.map((cat) => {
            const pct = (counts[cat.key] / total) * 100;
            return (
              <Box key={cat.key}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: '4px' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Box sx={{ width: 6, height: 6, borderRadius: '1px', background: cat.color, opacity: 0.7 }} />
                    <Typography sx={{ fontSize: 12 }}>{cat.label}</Typography>
                  </Box>
                  <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: palette.textSecondary }}>
                    {pct.toFixed(1)}%
                  </Typography>
                </Box>
                <Box sx={{ height: 3, background: palette.surfaceBorder, borderRadius: 1, overflow: 'hidden' }}>
                  <Box
                    sx={{
                      height: '100%',
                      width: `${pct}%`,
                      background: cat.color,
                      borderRadius: 1,
                      transition: 'width 0.5s ease',
                      opacity: 0.5,
                    }}
                  />
                </Box>
              </Box>
            );
          })}
          <Box sx={{ pt: 1, borderTop: `1px solid ${palette.surfaceBorder}`, display: 'flex', justifyContent: 'space-between' }}>
            <Typography sx={{ fontSize: 11, color: palette.textMuted }}>Total</Typography>
            <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: palette.text }}>
              {total}
            </Typography>
          </Box>
        </Box>
      )}
    </Box>
  );
}

export const DistributionPanel = memo(DistributionPanelInner);
