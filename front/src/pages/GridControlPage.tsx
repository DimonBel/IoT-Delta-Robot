import { useState, useCallback, useRef, useEffect } from 'react';
import { Box, Typography, Button, Slider } from '@mui/material';
import { palette } from '../theme';

const WORKSPACE = 400;
const HALF = WORKSPACE / 2;
const CELLS = 40;
const CELL_UNITS = WORKSPACE / CELLS;

type AxisState = { X: number; Y: number; Z: number; U: number; V: number; W: number };
const AXES: (keyof AxisState)[] = ['X', 'Y', 'Z', 'U', 'V', 'W'];

type CameraDetection = { id: number; label: string; x_mm: number; y_mm: number; confidence: number };

const DETECTION_COLOR = '#e24a4a';


function createInitialState(): AxisState {
  return { X: 0, Y: 0, Z: 0, U: 0, V: 0, W: 0 };
}

function cellCenter(row: number, col: number): { x: number; y: number } {
  return {
    x: Math.round(-(col * CELL_UNITS + CELL_UNITS / 2 - HALF)),
    y: Math.round(row * CELL_UNITS + CELL_UNITS / 2 - HALF),
  };
}

function getCellFromPos(pos: number, inverted = false): number {
  const adjusted = inverted ? -pos + HALF : pos + HALF;
  return Math.min(Math.max(Math.floor(adjusted / CELL_UNITS), 0), CELLS - 1);
}

function useGridSize(): { ref: React.RefObject<HTMLDivElement | null>; px: number } {
  const ref = useRef<HTMLDivElement | null>(null);
  const [px, setPx] = useState(500);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const h = entry.contentRect.height;
      setPx(Math.floor(h - 24));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, px };
}

function CameraStreamCard({ height }: { height: number }) {
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const prevUrlRef = useRef<string | null>(null);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const r = await fetch('/snapshot');
        if (r.ok && alive) {
          const blob = await r.blob();
          const url = URL.createObjectURL(blob);
          if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current);
          prevUrlRef.current = url;
          setFrameUrl(url);
          setLive(true);
        } else if (alive) {
          setLive(false);
        }
      } catch {
        if (alive) setLive(false);
      }
      if (alive) setTimeout(poll, 500);
    };
    poll();
    return () => {
      alive = false;
      if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current);
    };
  }, []);

  return (
    <Box sx={{ background: palette.surface, border: `1px solid ${palette.surfaceBorder}`, borderRadius: 1, p: '10px 12px', display: 'flex', flexDirection: 'column', height }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.75, flexShrink: 0 }}>
        <Typography sx={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: palette.textMuted }}>
          Camera Feed
        </Typography>
        {live && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Box sx={{ width: 5, height: 5, borderRadius: '50%', background: palette.success, animation: 'blink 1.6s ease infinite' }} />
            <style>{'@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}'}</style>
            <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: palette.success }}>LIVE</Typography>
          </Box>
        )}
      </Box>
      <Box
        sx={{
          position: 'relative',
          flex: 1,
          background: palette.bg,
          borderRadius: '3px',
          border: `1px solid ${palette.surfaceBorder}`,
          overflow: 'hidden',
        }}
      >
        {frameUrl ? (
          <img src={frameUrl} alt="Camera" style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }} />
        ) : (
          <Box sx={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: palette.textMuted }}>
              CONNECTING...
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}

export default function GridControlPage() {
  const [target, setTarget] = useState<AxisState>(createInitialState);
  const [current, setCurrent] = useState<AxisState>(createInitialState);
  const [status, setStatus] = useState('idle');
  const [speed, setSpeed] = useState(50);
  const [acceleration, setAcceleration] = useState(500);
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number } | null>(null);
  const [detections, setDetections] = useState<CameraDetection[]>([]);
  const { ref: gridContainerRef, px } = useGridSize();
  const cellPx = px / CELLS;

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const r = await fetch('/detections');
        if (r.ok && alive) setDetections(await r.json());
      } catch { /* server not ready yet */ }
      if (alive) setTimeout(poll, 300);
    };
    poll();
    return () => { alive = false; };
  }, []);

  const handleCellClick = useCallback((row: number, col: number) => {
    const { x, y } = cellCenter(row, col);
    setSelectedCell({ row, col });
    setTarget((prev) => ({ ...prev, X: x, Y: y }));
  }, []);

  const handleZChange = useCallback((_: unknown, val: number | number[]) => {
    setTarget((prev) => ({ ...prev, Z: val as number }));
  }, []);

  const updateMotion = useCallback(async (nextSpeed: number, nextAcceleration: number) => {
    try {
      await fetch('/motion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speed: nextSpeed, acceleration: nextAcceleration }),
      });
    } catch {
      setStatus('motion update failed');
    }
  }, []);

  useEffect(() => {
    updateMotion(speed, acceleration);
  }, [updateMotion]);

  const handleSpeedCommit = useCallback((_: Event | React.SyntheticEvent, value: number | number[]) => {
    const next = Array.isArray(value) ? value[0] : value;
    setSpeed(next);
    updateMotion(next, acceleration);
  }, [acceleration, updateMotion]);

  const handleAccelerationCommit = useCallback((_: Event | React.SyntheticEvent, value: number | number[]) => {
    const next = Array.isArray(value) ? value[0] : value;
    setAcceleration(next);
    updateMotion(speed, next);
  }, [speed, updateMotion]);

  const sendMove = useCallback(async () => {
    setStatus('sending...');
    try {
      const response = await fetch('/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(target),
      });
      if (!response.ok) {
        setStatus('send failed');
        return;
      }
      await response.json();
      setCurrent({ ...target });
      setStatus(`sent: X=${target.X} Y=${target.Y} Z=${target.Z}`);
    } catch {
      setStatus('send failed');
    }
  }, [target]);

  const getPosition = useCallback(async () => {
    setStatus('reading position...');
    try {
      const response = await fetch('/position', { method: 'GET' });
      if (!response.ok) {
        setStatus('position failed');
        return;
      }
      const data = await response.json();
      if (data.values) {
        const next = { ...createInitialState() };
        AXES.forEach((axis) => {
          if (Object.prototype.hasOwnProperty.call(data.values, axis)) {
            next[axis] = Number(data.values[axis]);
          }
        });
        setCurrent(next);
        setTarget(next);
        setSelectedCell({ row: getCellFromPos(next.Y), col: getCellFromPos(next.X, true) });
        setStatus(`position: X=${next.X} Y=${next.Y} Z=${next.Z}`);
      }
    } catch {
      setStatus('position failed');
    }
  }, []);

  const homeAxes = useCallback(async () => {
    setStatus('homing...');
    try {
      const response = await fetch('/home', { method: 'POST' });
      if (!response.ok) {
        setStatus('home failed');
        return;
      }
      const data = await response.json();
      if (data.values) {
        const next = { ...createInitialState() };
        AXES.forEach((axis) => {
          if (Object.prototype.hasOwnProperty.call(data.values, axis)) {
            next[axis] = Number(data.values[axis]);
          }
        });
        setCurrent(next);
        setTarget(next);
        setSelectedCell({ row: getCellFromPos(next.Y), col: getCellFromPos(next.X, true) });
      } else {
        setCurrent(createInitialState());
        setTarget(createInitialState());
        setSelectedCell(null);
      }
      setStatus(`home: ${data.status}`);
    } catch {
      setStatus('home failed');
    }
  }, []);

  const targetCol = getCellFromPos(target.X, true);
  const targetRow = getCellFromPos(target.Y);
  const currentCol = getCellFromPos(current.X, true);
  const currentRow = getCellFromPos(current.Y);

  return (
    <Box sx={{ p: 2, pb: 3, height: 'calc(100vh - 48px)', display: 'flex', gap: 2, overflow: 'hidden' }}>
      <Box
        ref={gridContainerRef}
        sx={{ display: 'flex', gap: 2, flex: 1, minWidth: 0 }}
      >
        <Box
          sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
            <Typography
              sx={{
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                color: palette.textMuted,
              }}
            >
              Workspace Grid &mdash; {WORKSPACE}&times;{WORKSPACE}mm
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', background: palette.accent }} />
                <Typography sx={{ fontSize: 11, color: palette.textMuted }}>Target</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', background: palette.success }} />
                <Typography sx={{ fontSize: 11, color: palette.textMuted }}>Current</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', background: DETECTION_COLOR }} />
                <Typography sx={{ fontSize: 11, color: palette.textMuted }}>Detected</Typography>
              </Box>
            </Box>
          </Box>

        <Box
          sx={{
            position: 'relative',
            width: px,
            height: px,
            flexShrink: 0,
            background: palette.bg,
            border: `1px solid ${palette.border}`,
            borderRadius: 1,
            overflow: 'hidden',
            cursor: 'crosshair',
          }}
        >
          <svg
            width={px}
            height={px}
            viewBox={`0 0 ${px} ${px}`}
            style={{ position: 'absolute', inset: 0 }}
          >
            {Array.from({ length: CELLS + 1 }, (_, i) => (
              <line
                key={`h${i}`}
                x1={0}
                y1={i * cellPx}
                x2={px}
                y2={i * cellPx}
                stroke={palette.surfaceBorder}
                strokeWidth={i % 5 === 0 ? 0.8 : 0.3}
              />
            ))}
            {Array.from({ length: CELLS + 1 }, (_, i) => (
              <line
                key={`v${i}`}
                x1={i * cellPx}
                y1={0}
                x2={i * cellPx}
                y2={px}
                stroke={palette.surfaceBorder}
                strokeWidth={i % 5 === 0 ? 0.8 : 0.3}
              />
            ))}

            {Array.from({ length: CELLS + 1 }).map((_, i) =>
              i % 5 === 0 ? (
                <text
                  key={`xl${i}`}
                  x={i * cellPx + 2}
                  y={px - 3}
                  fill={palette.textMuted}
                  fontSize={8}
                  fontFamily="'JetBrains Mono', monospace"
                >
                  {-(i * CELL_UNITS - HALF)}
                </text>
              ) : null,
            )}
            {Array.from({ length: CELLS + 1 }).map((_, i) =>
              i % 5 === 0 ? (
                <text
                  key={`yl${i}`}
                  x={2}
                  y={i * cellPx - 3}
                  fill={palette.textMuted}
                  fontSize={8}
                  fontFamily="'JetBrains Mono', monospace"
                >
                  {i * CELL_UNITS - HALF}
                </text>
              ) : null,
            )}

            {selectedCell && currentRow === targetRow && currentCol === targetCol ? null : (
              <>
                <rect
                  x={currentCol * cellPx + 1}
                  y={currentRow * cellPx + 1}
                  width={cellPx - 2}
                  height={cellPx - 2}
                  fill={`${palette.success}15`}
                  stroke={palette.success}
                  strokeWidth={1}
                  strokeDasharray="3 2"
                  rx={1}
                />
              </>
            )}

            <line x1={px / 2} y1={0} x2={px / 2} y2={px} stroke={palette.border} strokeWidth={0.8} strokeDasharray="4 4" />
            <line x1={0} y1={px / 2} x2={px} y2={px / 2} stroke={palette.border} strokeWidth={0.8} strokeDasharray="4 4" />
          </svg>

          {Array.from({ length: CELLS }, (_, row) =>
            Array.from({ length: CELLS }, (_, col) => (
              <Box
                key={`${row}-${col}`}
                onClick={() => handleCellClick(row, col)}
                sx={{
                  position: 'absolute',
                  left: col * cellPx,
                  top: row * cellPx,
                  width: cellPx,
                  height: cellPx,
                  ...(selectedCell?.row === row && selectedCell?.col === col
                    ? {
                        background: `${palette.accent}18`,
                        border: `1px solid ${palette.accent}55`,
                      }
                    : {
                        '&:hover': {
                          background: `${palette.accent}0a`,
                        },
                      }),
                  transition: 'background 0.08s',
                }}
              />
            )),
          )}

          {selectedCell && (
            <Box
              sx={{
                position: 'absolute',
                left: targetCol * cellPx + cellPx / 2,
                top: targetRow * cellPx + cellPx / 2,
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: palette.accent,
                border: `2px solid ${palette.bg}`,
                boxShadow: `0 0 6px ${palette.accent}66`,
                transform: 'translate(-50%, -50%)',
                pointerEvents: 'none',
                zIndex: 5,
              }}
            />
          )}

          {!(currentRow === targetRow && currentCol === targetCol) && (
            <Box
              sx={{
                position: 'absolute',
                left: currentCol * cellPx + cellPx / 2,
                top: currentRow * cellPx + cellPx / 2,
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: palette.success,
                border: `2px solid ${palette.bg}`,
                transform: 'translate(-50%, -50%)',
                pointerEvents: 'none',
                zIndex: 5,
              }}
            />
          )}

          <style>{'@keyframes detPulse{0%,100%{box-shadow:0 0 0 0 rgba(226,74,74,.55)}60%{box-shadow:0 0 0 7px rgba(226,74,74,0)}}'}</style>
          {detections
            .filter(d => Math.abs(d.x_mm) <= HALF && Math.abs(d.y_mm) <= HALF)
            .map(d => {
              const col = getCellFromPos(d.x_mm, true);
              const row = getCellFromPos(d.y_mm, false);
              const startCol = Math.min(Math.max(col - 1, 0), CELLS - 3);
              const startRow = Math.min(Math.max(row - 1, 0), CELLS - 3);
              return (
                <Box
                  key={`det-${d.id}`}
                  sx={{
                    position: 'absolute',
                    left: startCol * cellPx,
                    top: startRow * cellPx,
                    width: cellPx * 3,
                    height: cellPx * 3,
                    background: 'rgba(226,74,74,.24)',
                    border: `1px solid ${DETECTION_COLOR}`,
                    borderRadius: '2px',
                    zIndex: 10,
                    pointerEvents: 'none',
                  }}
                />
              );
            })
          }
        </Box>

        <CameraStreamCard height={px + 24} />
      </Box>
      </Box>

      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 1.5,
          width: 280,
          flexShrink: 0,
          overflow: 'auto',
        }}
      >
        <Box sx={{ background: palette.surface, border: `1px solid ${palette.surfaceBorder}`, borderRadius: 1, p: '14px 16px' }}>
        <Typography
          sx={{
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: palette.textMuted,
          }}
        >
          Target Position
        </Typography>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {(['X', 'Y'] as const).map((axis) => (
            <Box key={axis} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: '2px', px: '6px', background: palette.bg, borderRadius: '3px' }}>
              <Typography sx={{ fontSize: 10, color: palette.textMuted, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>{axis}</Typography>
              <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: palette.accent }}>{target[axis]}mm</Typography>
            </Box>
          ))}
        </Box>

        <Box sx={{ mt: 0.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: '2px' }}>
            <Typography sx={{ fontSize: 11, color: palette.textSecondary }}>Z Height</Typography>
            <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: palette.text }}>
              {target.Z}mm
            </Typography>
          </Box>
          <Slider
            size="small"
            min={-960}
            max={-740}
            step={5}
            value={target.Z}
            onChange={handleZChange}
            sx={{ color: palette.accent }}
          />
        </Box>

        <Box sx={{ mt: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: '2px' }}>
            <Typography sx={{ fontSize: 11, color: palette.textSecondary }}>Speed (F)</Typography>
            <Typography sx={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: palette.text }}>
              {speed}
            </Typography>
          </Box>
          <Slider
            size="small"
            min={50}
            max={400}
            step={1}
            value={speed}
            onChange={(_, val) => setSpeed(val as number)}
            onChangeCommitted={handleSpeedCommit}
            sx={{ color: palette.accent }}
          />
        </Box>

        <Box sx={{ mt: 0.75 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: '2px' }}>
            <Typography sx={{ fontSize: 11, color: palette.textSecondary }}>Acceleration (A)</Typography>
            <Typography sx={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: palette.text }}>
              {acceleration}
            </Typography>
          </Box>
          <Slider
            size="small"
            min={500}
            max={1500}
            step={10}
            value={acceleration}
            onChange={(_, val) => setAcceleration(val as number)}
            onChangeCommitted={handleAccelerationCommit}
            sx={{ color: palette.accent }}
          />
        </Box>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '4px', mt: 0.5 }}>
          {(['U', 'V', 'W'] as const).map((axis) => (
            <Box key={axis} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: '2px', px: '6px', background: palette.bg, borderRadius: '3px' }}>
              <Typography sx={{ fontSize: 10, color: palette.textMuted, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>{axis}</Typography>
              <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: palette.text }}>{target[axis]}</Typography>
            </Box>
          ))}
        </Box>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '4px', mt: 1 }}>
          <Button variant="contained" onClick={sendMove} fullWidth size="small" sx={{ fontWeight: 600 }}>
            Send Move
          </Button>
          <Box sx={{ display: 'flex', gap: '4px' }}>
            <Button variant="outlined" onClick={getPosition} size="small" sx={{ flex: 1, fontSize: 11 }}>
              Get Pos
            </Button>
            <Button variant="outlined" onClick={homeAxes} size="small" sx={{ flex: 1, fontSize: 11 }}>
              Home
            </Button>
          </Box>
        </Box>

        <Box sx={{ py: '6px', px: '8px', background: palette.bg, borderRadius: '3px', border: `1px solid ${palette.surfaceBorder}`, mt: 0.5 }}>
          <Typography
            sx={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11,
              color: status.includes('failed') ? palette.error : palette.textSecondary,
            }}
          >
            {status}
          </Typography>
        </Box>
        </Box>
      </Box>
    </Box>
  );
}
