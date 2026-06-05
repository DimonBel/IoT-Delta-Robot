import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Box, Fab } from '@mui/material';
import { Settings } from '@mui/icons-material';
import { ThemeProvider, CssBaseline } from '@mui/material';
import theme from './theme';
import { AppHeader } from './components/layout';
import DashboardPage from './pages/DashboardPage';
import ControlPage from './pages/ControlPage';
import MovementTestPage from './pages/MovementTestPage';
import GridControlPage from './pages/GridControlPage';
import {
  TweaksPanel,
  TweakSection,
  TweakSlider,
  TweakToggle,
  TweakColor,
} from './components/tweaks/TweaksPanel';
import { useTweaks } from './hooks/useTweaks';

interface TweakValues {
  conveyorSpeed: number;
  armSpeed: number;
  pickHeight: number;
  sensitivity: number;
  dark: boolean;
  accentColor: string;
}

const DEFAULT_TWEAKS: TweakValues = {
  conveyorSpeed: 65,
  armSpeed: 70,
  pickHeight: 40,
  sensitivity: 88,
  dark: false,
  accentColor: '#1a1c1e',
};

function DashboardWithTweaks() {
  const [tweaks, setTweak] = useTweaks<TweakValues>(DEFAULT_TWEAKS);

  return (
    <>
      <DashboardPage />
      <TweakPanelWrapper tweaks={tweaks} setTweak={setTweak} />
    </>
  );
}

function ControlWithTweaks() {
  const [tweaks, setTweak] = useTweaks<TweakValues>(DEFAULT_TWEAKS);

  return (
    <>
      <ControlPage />
      <TweakPanelWrapper tweaks={tweaks} setTweak={setTweak} />
    </>
  );
}

function TweakPanelWrapper({
  tweaks,
  setTweak,
}: {
  tweaks: TweakValues;
  setTweak: (keyOrEdits: string | Partial<TweakValues>, val?: unknown) => void;
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === '`' && e.ctrlKey) {
        setOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <>
      <Fab
        size="small"
        onClick={() => setOpen((prev) => !prev)}
        sx={{
          position: 'fixed',
          bottom: 16,
          left: 16,
          zIndex: 1000,
          background: 'rgba(0,0,0,0.06)',
          boxShadow: 'none',
          color: 'text.secondary',
          '&:hover': {
            background: 'rgba(0,0,0,0.1)',
          },
        }}
      >
        <Settings fontSize="small" />
      </Fab>
      <TweaksPanel open={open} onClose={() => setOpen(false)}>
        <TweakSection label="Simulation" />
        <TweakSlider
          label="Conveyor Speed"
          value={tweaks.conveyorSpeed}
          min={10}
          max={100}
          unit="%"
          onChange={(v) => setTweak('conveyorSpeed', v)}
        />
        <TweakSlider
          label="Arm Speed"
          value={tweaks.armSpeed}
          min={10}
          max={100}
          unit="%"
          onChange={(v) => setTweak('armSpeed', v)}
        />
        <TweakSlider
          label="Pick Height"
          value={tweaks.pickHeight}
          min={10}
          max={80}
          unit="mm"
          onChange={(v) => setTweak('pickHeight', v)}
        />
        <TweakSlider
          label="Sensitivity"
          value={tweaks.sensitivity}
          min={50}
          max={100}
          unit="%"
          onChange={(v) => setTweak('sensitivity', v)}
        />
        <TweakSection label="Theme" />
        <TweakColor
          label="Accent"
          value={tweaks.accentColor}
          onChange={(v) => setTweak('accentColor', v)}
        />
        <TweakToggle
          label="Dark mode"
          value={tweaks.dark}
          onChange={(v) => setTweak('dark', v)}
        />
      </TweaksPanel>
    </>
  );
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Box
          sx={{
            minHeight: '100vh',
            background: 'background.default',
            fontFamily: "'Space Grotesk', system-ui, sans-serif",
          }}
        >
          <AppHeader connected={false} />
          <Routes>
            <Route path="/" element={<DashboardWithTweaks />} />
            <Route path="/control" element={<ControlWithTweaks />} />
            <Route path="/movement" element={<MovementTestPage />} />
            <Route path="/grid" element={<GridControlPage />} />
          </Routes>
        </Box>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
