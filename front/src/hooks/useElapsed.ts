import { useState, useRef, useCallback } from 'react';

export function formatElapsed(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return [h, m, s].map((v) => String(v).padStart(2, '0')).join(':');
}

export function useElapsed(active: boolean) {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number | null>(null);

  const start = useCallback(() => {
    startRef.current = Date.now();
    setElapsed(0);
  }, []);

  const stop = useCallback(() => {
    startRef.current = null;
    setElapsed(0);
  }, []);

  return { elapsed, start, stop, active };
}
