import { useEffect, useRef, useCallback, type ReactNode } from 'react';
import {
  Box,
  Typography,
  Slider as MuiSlider,
  Switch,
  Button,
} from '@mui/material';

interface TweaksPanelProps {
  title?: string;
  children: ReactNode;
  open: boolean;
  onClose: () => void;
}

export function TweaksPanel({
  title = 'Tweaks',
  children,
  open,
  onClose,
}: TweaksPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const offsetRef = useRef({ x: 16, y: 16 });
  const PAD = 16;

  const clampToViewport = useCallback(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const w = panel.offsetWidth;
    const h = panel.offsetHeight;
    const maxRight = Math.max(PAD, window.innerWidth - w - PAD);
    const maxBottom = Math.max(PAD, window.innerHeight - h - PAD);
    offsetRef.current = {
      x: Math.min(maxRight, Math.max(PAD, offsetRef.current.x)),
      y: Math.min(maxBottom, Math.max(PAD, offsetRef.current.y)),
    };
    panel.style.right = offsetRef.current.x + 'px';
    panel.style.bottom = offsetRef.current.y + 'px';
  }, []);

  useEffect(() => {
    if (!open) return;
    clampToViewport();
    const ro = new ResizeObserver(clampToViewport);
    ro.observe(document.documentElement);
    return () => ro.disconnect();
  }, [open, clampToViewport]);

  const onDragStart = (e: React.MouseEvent) => {
    const panel = panelRef.current;
    if (!panel) return;
    const r = panel.getBoundingClientRect();
    const sx = e.clientX;
    const sy = e.clientY;
    const startRight = window.innerWidth - r.right;
    const startBottom = window.innerHeight - r.bottom;
    const move = (ev: MouseEvent) => {
      offsetRef.current = {
        x: startRight - (ev.clientX - sx),
        y: startBottom - (ev.clientY - sy),
      };
      clampToViewport();
    };
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };

  if (!open) return null;

  return (
    <Box
      ref={panelRef}
      sx={{
        position: 'fixed',
        right: offsetRef.current.x,
        bottom: offsetRef.current.y,
        zIndex: 2147483646,
        width: 280,
        maxHeight: 'calc(100vh - 32px)',
        display: 'flex',
        flexDirection: 'column',
        background: 'rgba(250,249,247,0.78)',
        color: '#29261b',
        backdropFilter: 'blur(24px) saturate(160%)',
        WebkitBackdropFilter: 'blur(24px) saturate(160%)',
        border: '0.5px solid rgba(255,255,255,0.6)',
        borderRadius: '14px',
        boxShadow:
          '0 1px 0 rgba(255,255,255,0.5) inset, 0 12px 40px rgba(0,0,0,0.18)',
        fontFamily:
          "ui-sans-serif, system-ui, -apple-system, sans-serif",
        fontSize: '11.5px',
        lineHeight: 1.4,
        overflow: 'hidden',
      }}
    >
      <Box
        onMouseDown={onDragStart}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: '10px 8px 10px 14px',
          cursor: 'move',
          userSelect: 'none',
        }}
      >
        <Typography
          sx={{
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: '0.01em',
            color: '#29261b',
          }}
        >
          {title}
        </Typography>
        <Box
          component="button"
          onClick={onClose}
          sx={{
            appearance: 'none',
            border: 0,
            background: 'transparent',
            color: 'rgba(41,38,27,0.55)',
            width: 22,
            height: 22,
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: 13,
            lineHeight: 1,
            '&:hover': {
              background: 'rgba(0,0,0,0.06)',
              color: '#29261b',
            },
          }}
        >
          {'\u2715'}
        </Box>
      </Box>
      <Box
        sx={{
          p: '2px 14px 14px',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          overflowY: 'auto',
          overflowX: 'hidden',
          minHeight: 0,
        }}
      >
        {children}
      </Box>
    </Box>
  );
}

export function TweakSection({ label }: { label: string }) {
  return (
    <Typography
      sx={{
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        color: 'rgba(41,38,27,0.45)',
        pt: '10px',
        '&:first-of-type': { pt: 0 },
      }}
    >
      {label}
    </Typography>
  );
}

interface TweakSliderProps {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  onChange: (v: number) => void;
}

export function TweakSlider({
  label,
  value,
  min = 0,
  max = 100,
  step = 1,
  unit = '',
  onChange,
}: TweakSliderProps) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          color: 'rgba(41,38,27,0.72)',
        }}
      >
        <Typography sx={{ fontSize: '11.5px', fontWeight: 500 }}>{label}</Typography>
        <Typography sx={{ fontSize: '11.5px', color: 'rgba(41,38,27,0.5)' }}>
          {value}
          {unit}
        </Typography>
      </Box>
      <MuiSlider
        size="small"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(_, v) => onChange(v as number)}
        sx={{
          height: 4,
          borderRadius: '999px',
          background: 'rgba(0,0,0,0.12)',
          color: '#29261b',
          '& .MuiSlider-thumb': {
            width: 14,
            height: 14,
            background: '#fff',
            border: '0.5px solid rgba(0,0,0,0.12)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
          },
        }}
      />
    </Box>
  );
}

interface TweakToggleProps {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}

export function TweakToggle({ label, value, onChange }: TweakToggleProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '10px',
      }}
    >
      <Typography sx={{ fontSize: '11.5px', fontWeight: 500, color: 'rgba(41,38,27,0.72)' }}>
        {label}
      </Typography>
      <Switch
        size="small"
        checked={value}
        onChange={(e) => onChange(e.target.checked)}
        sx={{
          width: 32,
          height: 18,
          p: 0,
          '& .MuiSwitch-switchBase': {
            p: '2px',
            '&.Mui-checked': {
              '& + .MuiSwitch-track': {
                backgroundColor: '#34c759',
              },
            },
          },
          '& .MuiSwitch-thumb': {
            width: 14,
            height: 14,
            boxShadow: '0 1px 2px rgba(0,0,0,0.25)',
          },
          '& .MuiSwitch-track': {
            borderRadius: '999px',
            background: 'rgba(0,0,0,0.15)',
          },
        }}
      />
    </Box>
  );
}

interface TweakColorProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
}

export function TweakColor({ label, value, onChange }: TweakColorProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '10px',
      }}
    >
      <Typography sx={{ fontSize: '11.5px', fontWeight: 500, color: 'rgba(41,38,27,0.72)' }}>
        {label}
      </Typography>
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          appearance: 'none',
          WebkitAppearance: 'none',
          width: 56,
          height: 22,
          border: '0.5px solid rgba(0,0,0,0.1)',
          borderRadius: 6,
          padding: 0,
          cursor: 'pointer',
          background: 'transparent',
        }}
      />
    </Box>
  );
}

interface TweakButtonProps {
  label: string;
  onClick: () => void;
  secondary?: boolean;
}

export function TweakButton({ label, onClick, secondary = false }: TweakButtonProps) {
  return (
    <Button
      size="small"
      onClick={onClick}
      sx={{
        height: 26,
        borderRadius: '7px',
        fontSize: '11.5px',
        fontWeight: 500,
        textTransform: 'none',
        ...(secondary
          ? {
              background: 'rgba(0,0,0,0.06)',
              color: '#29261b',
              '&:hover': { background: 'rgba(0,0,0,0.1)' },
            }
          : {
              background: 'rgba(0,0,0,0.78)',
              color: '#fff',
              '&:hover': { background: 'rgba(0,0,0,0.88)' },
            }),
      }}
    >
      {label}
    </Button>
  );
}
