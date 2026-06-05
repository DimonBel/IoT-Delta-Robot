import { useState, useEffect, useRef } from 'react';
import { Box, Typography, Button, keyframes } from '@mui/material';
import { LogPanel } from '../components/common';
import {
  ConnectionPanel,
  ParameterSlider,
  ArmStatusPanel,
  SignalPanel,
  OutputBinsPanel,
  VisionCamera,
} from '../components/control';
import { TELEMETRY_MESSAGES } from '../constants';
import { useLog } from '../hooks/useLog';
import { palette } from '../theme';
import type { RobotState, OperationMode, RobotParameters } from '../types';

const fadeup = keyframes`from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}`;
const blink = keyframes`0%,100%{opacity:1}50%{opacity:0.3}`;

export default function ControlPage() {
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [sysState, setSysState] = useState<RobotState>('OFFLINE');
  const [mode, setMode] = useState<OperationMode>('AUTO');
  const [params, setParams] = useState<RobotParameters>({
    convSpeed: 65,
    armSpeed: 70,
    pickHeight: 40,
    sensitivity: 88,
  });
  const [elapsed, setElapsed] = useState(0);
  const { logs, addLog, clearLogs } = useLog();
  const sesRef = useRef<number | null>(null);

  useEffect(() => {
    if (!connected) return;
    sesRef.current = Date.now();
    const t = setInterval(
      () => setElapsed(Math.floor((Date.now() - sesRef.current!) / 1000)),
      1000,
    );
    return () => clearInterval(t);
  }, [connected]);

  useEffect(() => {
    if (sysState !== 'RUNNING') return;
    const cycle: RobotState[] = ['RUNNING', 'RUNNING', 'RUNNING', 'PICK', 'PLACE'];
    const t = setInterval(() => {
      const s = cycle[Math.floor(Math.random() * cycle.length)];
      setSysState(s);
      if (s === 'PICK') addLog('Pick \u2014 object detected & grasped', 'ok');
      if (s === 'PLACE') addLog('Place \u2014 item sorted to bin', 'ok');
    }, 1900);
    return () => clearInterval(t);
  }, [sysState, addLog]);

  useEffect(() => {
    if (!connected || sysState !== 'RUNNING') return;
    const t = setInterval(() => {
      const [msg, type] = TELEMETRY_MESSAGES[Math.floor(Math.random() * TELEMETRY_MESSAGES.length)];
      addLog(msg, type);
    }, 3500);
    return () => clearInterval(t);
  }, [connected, sysState, addLog]);

  const connect = () => {
    setConnecting(true);
    addLog('Initiating connection \u2192 192.168.1.42:8080', 'info');
    setTimeout(() => {
      setConnecting(false);
      setConnected(true);
      setSysState('IDLE');
      addLog('TCP handshake OK', 'ok');
      addLog('Firmware v2.4.1 \u2014 all systems nominal', 'ok');
      addLog('Delta robot ONLINE', 'ok');
    }, 2000);
  };

  const disconnect = () => {
    if (sysState === 'RUNNING') stop();
    setConnected(false);
    setSysState('OFFLINE');
    setElapsed(0);
    addLog('Session terminated by operator', 'warn');
  };

  const start = () => {
    if (!connected || sysState === 'E-STOP') return;
    setSysState('RUNNING');
    addLog(`START \u2014 mode:${mode} conv:${params.convSpeed}% arm:${params.armSpeed}%`, 'cmd');
  };

  const stop = () => {
    if (!connected) return;
    setSysState('IDLE');
    addLog('STOP \u2014 conveyor halted', 'cmd');
  };

  const home = () => {
    if (!connected) return;
    setSysState('HOMING');
    addLog('HOME sequence initiated', 'cmd');
    setTimeout(() => {
      setSysState('IDLE');
      addLog('Homing complete \u2014 (0, 0, 0)', 'ok');
    }, 2600);
  };

  const eStop = () => {
    setSysState('E-STOP');
    setConnected(false);
    addLog('\u26A0 EMERGENCY STOP \u2014 all motion halted', 'err');
    addLog('Manual reset required', 'warn');
  };

  const reset = () => {
    setSysState('OFFLINE');
    setConnected(false);
    addLog('System reset \u2014 reconnect to resume', 'warn');
  };

  const manualPick = () => {
    if (!connected || mode !== 'MANUAL' || sysState !== 'IDLE') return;
    addLog('MANUAL PICK', 'cmd');
    setSysState('PICK');
    setTimeout(() => {
      setSysState('IDLE');
      addLog('Manual pick complete', 'ok');
    }, 800);
  };

  const manualPlace = () => {
    if (!connected || mode !== 'MANUAL' || sysState !== 'IDLE') return;
    addLog('MANUAL PLACE', 'cmd');
    setSysState('PLACE');
    setTimeout(() => {
      setSysState('IDLE');
      addLog('Manual place complete', 'ok');
    }, 800);
  };

  const updateParam = (key: keyof RobotParameters, value: number) => {
    setParams((prev) => ({ ...prev, [key]: value }));
    const labels: Record<string, string> = {
      convSpeed: 'Conveyor',
      armSpeed: 'Arm speed',
      pickHeight: 'Pick height',
      sensitivity: 'Vision sensitivity',
    };
    const units: Record<string, string> = {
      convSpeed: '%',
      armSpeed: '%',
      pickHeight: 'mm',
      sensitivity: '%',
    };
    addLog(`${labels[key]} \u2192 ${value}${units[key]}`, 'cmd');
  };

  const isRunning = sysState === 'RUNNING';
  const isEStop = sysState === 'E-STOP';

  return (
    <Box
      sx={{
        p: 2,
        display: 'grid',
        gridTemplateColumns: '240px 1fr 240px',
        gap: 1.5,
        alignItems: 'start',
      }}
    >
      {isEStop && (
        <Box
          sx={{
            gridColumn: '1 / -1',
            background: palette.errorBg,
            border: `1px solid ${palette.error}44`,
            p: '10px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderRadius: 1,
            animation: `${fadeup} 0.15s ease`,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Box sx={{ width: 6, height: 6, borderRadius: '50%', background: palette.error, animation: `${blink} 0.8s infinite` }} />
            <Typography sx={{ fontWeight: 600, color: palette.error, fontSize: 13 }}>E-STOP Active</Typography>
            <Typography sx={{ fontSize: 12, color: palette.textSecondary }}>All motion halted</Typography>
          </Box>
          <Button
            onClick={reset}
            size="small"
            sx={{ borderColor: `${palette.error}44`, color: palette.error, fontSize: 12, fontWeight: 600 }}
            variant="outlined"
          >
            Reset
          </Button>
        </Box>
      )}

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <ConnectionPanel connected={connected} connecting={connecting} elapsed={elapsed} onConnect={connect} onDisconnect={disconnect} />
        <ArmStatusPanel state={sysState} />
        <SignalPanel connected={connected} />
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <Box sx={{ background: palette.surface, border: `1px solid ${palette.surfaceBorder}`, borderRadius: 1, p: '14px 16px' }}>
          <Typography sx={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: palette.textMuted, mb: 1.5 }}>
            System Control
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px', mb: 1 }}>
            <Button variant="contained" onClick={start} disabled={!connected || isRunning || isEStop || sysState === 'HOMING'} size="small">
              Start
            </Button>
            <Button variant="outlined" onClick={stop} disabled={!connected || !isRunning} size="small">
              Stop
            </Button>
            <Button variant="outlined" onClick={home} disabled={!connected || isRunning || isEStop} size="small">
              Home
            </Button>
          </Box>
          <Button
            fullWidth
            onClick={eStop}
            sx={{
              py: '10px',
              borderRadius: '4px',
              border: `1px solid ${palette.error}44`,
              background: palette.errorBg,
              color: palette.error,
              fontWeight: 700,
              fontSize: 13,
              letterSpacing: '0.08em',
              '&:hover': { background: `${palette.error}18` },
            }}
          >
            E-STOP
          </Button>
        </Box>

        <Box sx={{ background: palette.surface, border: `1px solid ${palette.surfaceBorder}`, borderRadius: 1, p: '14px 16px' }}>
          <Typography sx={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: palette.textMuted, mb: 1.5 }}>
            Operation Mode
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', mb: mode === 'MANUAL' ? 1 : 0 }}>
            {(['AUTO', 'MANUAL'] as OperationMode[]).map((m) => (
              <Button
                key={m}
                onClick={() => { if (!isRunning && connected) { setMode(m); addLog(`MODE \u2192 ${m}`, 'cmd'); } }}
                disabled={isRunning || !connected}
                variant={mode === m ? 'contained' : 'outlined'}
                size="small"
                sx={{ fontSize: 12 }}
              >
                {m}
              </Button>
            ))}
          </Box>
          {mode === 'MANUAL' && (
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
              <Button variant="outlined" onClick={manualPick} disabled={!connected || sysState !== 'IDLE'} size="small">
                Pick
              </Button>
              <Button variant="outlined" onClick={manualPlace} disabled={!connected || sysState !== 'IDLE'} size="small">
                Place
              </Button>
            </Box>
          )}
        </Box>

        <Box sx={{ background: palette.surface, border: `1px solid ${palette.surfaceBorder}`, borderRadius: 1, p: '14px 16px' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography sx={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: palette.textMuted }}>
              Log
            </Typography>
            <Button size="small" onClick={clearLogs} sx={{ fontSize: 10, color: palette.textMuted, minWidth: 'auto', p: 0 }}>
              Clear
            </Button>
          </Box>
          {logs.length === 0 ? (
            <Typography sx={{ color: palette.textMuted, fontSize: 11, textAlign: 'center', py: 2 }}>No events</Typography>
          ) : (
            <LogPanel entries={logs} maxHeight={220} />
          )}
        </Box>
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <Box sx={{ background: palette.surface, border: `1px solid ${palette.surfaceBorder}`, borderRadius: 1, p: '14px 16px' }}>
          <Typography sx={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: palette.textMuted, mb: 1.5 }}>
            Parameters
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <ParameterSlider label="Conveyor Speed" value={params.convSpeed} min={10} max={100} unit="%" disabled={!connected} onChange={(v) => updateParam('convSpeed', v)} />
            <ParameterSlider label="Arm Speed" value={params.armSpeed} min={10} max={100} unit="%" disabled={!connected} onChange={(v) => updateParam('armSpeed', v)} />
            <ParameterSlider label="Pick Height" value={params.pickHeight} min={10} max={80} unit="mm" disabled={!connected} onChange={(v) => updateParam('pickHeight', v)} />
            <ParameterSlider label="Sensitivity" value={params.sensitivity} min={50} max={100} unit="%" disabled={!connected} onChange={(v) => updateParam('sensitivity', v)} />
          </Box>
        </Box>
        <OutputBinsPanel />
        <VisionCamera connected={connected} />
      </Box>
    </Box>
  );
}
