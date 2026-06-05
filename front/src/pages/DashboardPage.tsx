import { useState, useEffect, useRef } from 'react';
import { Box, Typography, Button, Paper } from '@mui/material';
import { StatCard, AnimCounter, ConveyorBelt } from '../components/common';
import { CategoryCard, DistributionPanel, UptimePanel } from '../components/dashboard';
import { CATEGORIES } from '../constants';
import type { CategoryKey, BeltItem, RobotState } from '../types';
import { palette } from '../theme';

export default function DashboardPage() {
  const [counts, setCounts] = useState<Record<CategoryKey, number>>({
    apple: 0,
    orange: 0,
    veggie: 0,
  });
  const [total, setTotal] = useState(0);
  const [running, setRunning] = useState(true);
  const [robotState, setRobotState] = useState<RobotState>('IDLE');
  const [throughput, setThroughput] = useState(0);
  const [history, setHistory] = useState<Record<CategoryKey, number[]>>({
    apple: Array(22).fill(0),
    orange: Array(22).fill(0),
    veggie: Array(22).fill(0),
  });
  const [beltItems, setBeltItems] = useState<BeltItem[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const speed = 1.8;
  const sessionStart = useRef(Date.now());
  const idRef = useRef(0);

  useEffect(() => {
    const t = setInterval(
      () => setElapsed(Math.floor((Date.now() - sessionStart.current) / 1000)),
      1000,
    );
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!running) return;

    const moveTimer = setInterval(() => {
      setBeltItems((prev) => {
        const moved = prev.map((it) => ({ ...it, x: it.x + 1.4 }));
        const exited = moved.filter((it) => it.x >= 108);
        exited.forEach((item) => {
          setCounts((c) => ({ ...c, [item.key]: c[item.key] + 1 }));
          setTotal((t) => t + 1);
          setRobotState('PICK');
          setTimeout(() => setRobotState('PLACE'), 260);
          setTimeout(() => setRobotState('IDLE'), 620);
        });
        return moved.filter((it) => it.x < 108);
      });
    }, 50);

    const spawnTimer = setInterval(() => {
      const cat = CATEGORIES[Math.floor(Math.random() * CATEGORIES.length)];
      setBeltItems((prev) => [...prev, { id: idRef.current++, x: -6, ...cat }]);
    }, Math.round(1700 / speed));

    const histTimer = setInterval(() => {
      setCounts((c) => {
        setHistory((h) => ({
          apple: [...h.apple.slice(1), c.apple],
          orange: [...h.orange.slice(1), c.orange],
          veggie: [...h.veggie.slice(1), c.veggie],
        }));
        return c;
      });
      setThroughput(Math.round((Math.random() * 6 + 12) * speed));
    }, 3000);

    return () => {
      clearInterval(moveTimer);
      clearInterval(spawnTimer);
      clearInterval(histTimer);
    };
  }, [running, speed]);

  const fmtElapsed = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return [h, m, sec].map((v) => String(v).padStart(2, '0')).join(':');
  };

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          <Typography
            sx={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 13,
              color: palette.textSecondary,
              lineHeight: '32px',
            }}
          >
            {fmtElapsed(elapsed)}
          </Typography>
        </Box>
        <Button
          size="small"
          variant="outlined"
          onClick={() => setRunning((r) => !r)}
          sx={{
            fontSize: 11,
            fontFamily: "'JetBrains Mono', monospace",
            py: '2px',
            px: 1.5,
            minWidth: 'auto',
            color: running ? palette.warning : palette.success,
            borderColor: running ? `${palette.warning}44` : `${palette.success}44`,
            '&:hover': {
              borderColor: running ? palette.warning : palette.success,
              background: running ? palette.warningBg : palette.successBg,
            },
          }}
        >
          {running ? 'PAUSE' : 'RESUME'}
        </Button>
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1 }}>
        <StatCard
          label="Robot"
          value={running ? robotState : 'STOPPED'}
          dot
          dotOn={running && (robotState === 'IDLE' || robotState === 'RUNNING')}
        />
        <StatCard
          label="Throughput"
          value={running ? throughput || '\u2014' : '0'}
          unit="items/min"
        />
        <StatCard label="Total Sorted" value={<AnimCounter value={total} />} />
        <StatCard
          label="Conveyor"
          value={running ? 'ACTIVE' : 'STOPPED'}
          dot
          dotOn={running}
        />
      </Box>

      <Paper elevation={0} sx={{ p: '12px 16px' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography
            sx={{
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: palette.textMuted,
            }}
          >
            Conveyor Belt
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            {CATEGORIES.map((c) => (
              <span key={c.key} style={{ fontSize: 13 }}>
                {c.emoji}
              </span>
            ))}
            <Typography sx={{ fontSize: 10, color: palette.textMuted, ml: '4px' }}>
              &rarr; sort station
            </Typography>
          </Box>
        </Box>
        <ConveyorBelt items={beltItems} running={running} />
      </Paper>

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1 }}>
        {CATEGORIES.map((cat) => (
          <CategoryCard
            key={cat.key}
            category={cat}
            count={counts[cat.key]}
            total={total}
            history={history[cat.key]}
          />
        ))}
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: 1 }}>
        <DistributionPanel categories={CATEGORIES} counts={counts} total={total} />
        <UptimePanel />
      </Box>
    </Box>
  );
}
