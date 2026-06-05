import { useState, useEffect, useRef, memo } from 'react';

interface AnimCounterProps {
  value: number;
}

function AnimCounterComponent({ value }: AnimCounterProps) {
  const [display, setDisplay] = useState(value);
  const prev = useRef(value);

  useEffect(() => {
    if (value === prev.current) return;
    const start = prev.current;
    const end = value;
    const dur = 400;
    const t0 = performance.now();

    const tick = (now: number) => {
      const p = Math.min((now - t0) / dur, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      setDisplay(Math.round(start + (end - start) * ease));
      if (p < 1) requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
    prev.current = value;
  }, [value]);

  return <span>{display.toLocaleString()}</span>;
}

export const AnimCounter = memo(AnimCounterComponent);
