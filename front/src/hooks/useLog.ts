import { useState, useCallback } from 'react';
import type { LogEntry, LogType } from '../types';

let globalLogId = 0;

function formatTime(date: Date): string {
  const h = String(date.getHours()).padStart(2, '0');
  const m = String(date.getMinutes()).padStart(2, '0');
  const s = String(date.getSeconds()).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

export function useLog(maxEntries = 80) {
  const [logs, setLogs] = useState<LogEntry[]>([]);

  const addLog = useCallback(
    (msg: string, type: LogType = 'info') => {
      const time = formatTime(new Date());
      setLogs((prev) =>
        [
          ...prev,
          { id: globalLogId++, time, msg, type },
        ].slice(-maxEntries),
      );
    },
    [maxEntries],
  );

  const clearLogs = useCallback(() => setLogs([]), []);

  return { logs, addLog, clearLogs };
}
