import { memo } from 'react';
import { Box, Typography, Slider } from '@mui/material';
import { palette } from '../../theme';

interface ParameterSliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit: string;
  disabled?: boolean;
  onChange: (value: number) => void;
}

function ParameterSliderInner({ label, value, min, max, step = 1, unit, disabled = false, onChange }: ParameterSliderProps) {
  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: '2px' }}>
        <Typography sx={{ fontSize: 11, color: palette.textSecondary }}>{label}</Typography>
        <Typography
          sx={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
            color: disabled ? palette.textMuted : palette.text,
          }}
        >
          {value}{unit}
        </Typography>
      </Box>
      <Slider
        size="small"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(_, v) => onChange(v as number)}
        disabled={disabled}
        sx={{
          color: disabled ? palette.textMuted : palette.accent,
          '& .MuiSlider-track': { transition: 'width 0.1s' },
          '& .MuiSlider-thumb': { transition: 'left 0.1s' },
        }}
      />
    </Box>
  );
}

export const ParameterSlider = memo(ParameterSliderInner);
