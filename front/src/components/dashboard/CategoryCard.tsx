import { memo } from 'react';
import { Box, Typography } from '@mui/material';
import { AnimCounter, Sparkline } from '../common';
import { palette } from '../../theme';
import type { Category } from '../../types';

interface CategoryCardProps {
  category: Category;
  count: number;
  total: number;
  history: number[];
}

function CategoryCardInner({ category, count, total, history }: CategoryCardProps) {
  const pct = total > 0 ? (count / total) * 100 : 0;

  return (
    <Box
      sx={{
        background: palette.surface,
        border: `1px solid ${palette.surfaceBorder}`,
        borderRadius: 1,
        p: '14px 16px',
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
        <Box>
          <Typography
            sx={{
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: palette.textMuted,
              mb: '6px',
            }}
          >
            {category.label}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
            <Typography
              sx={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 28,
                fontWeight: 400,
                letterSpacing: '-0.03em',
                color: category.color,
                lineHeight: 1,
              }}
            >
              <AnimCounter value={count} />
            </Typography>
          </Box>
        </Box>
        <Typography sx={{ fontSize: 20, mt: '2px' }}>{category.emoji}</Typography>
      </Box>
      <Box
        sx={{
          height: 2,
          background: palette.surfaceBorder,
          borderRadius: 1,
          mb: 1,
          overflow: 'hidden',
        }}
      >
        <Box
          sx={{
            height: '100%',
            width: `${pct}%`,
            background: category.color,
            borderRadius: 1,
            transition: 'width 0.5s ease',
            opacity: 0.6,
          }}
        />
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography sx={{ fontSize: 11, color: palette.textMuted }}>
          {pct.toFixed(1)}%
        </Typography>
        <Sparkline data={history} color={category.color} />
      </Box>
    </Box>
  );
}

export const CategoryCard = memo(CategoryCardInner);
