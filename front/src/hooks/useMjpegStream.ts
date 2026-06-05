import { useState, useEffect, useRef, useCallback } from 'react';

export function useMjpegStream(url: string, active: boolean) {
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const [error, setError] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const urlRef = useRef<string | null>(null);

  const stop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!active || !url) {
      stop();
      setFrameUrl(null);
      setLive(false);
      return;
    }

    let cancelled = false;
    const ac = new AbortController();
    abortRef.current = ac;

    const BOUNDARY = '--frame';

    const run = async () => {
      try {
        const res = await fetch(url, {
          signal: ac.signal,
          headers: { 'ngrok-skip-browser-warning': 'true', Accept: 'multipart/x-mixed-replace' },
        });

        if (!res.ok || !res.body) {
          if (!cancelled) setError(true);
          return;
        }

        const reader = res.body.getReader();
        let buf = new Uint8Array(0);

        while (!cancelled) {
          const { done, value } = await reader.read();
          if (done) break;

          const next = new Uint8Array(buf.length + value.length);
          next.set(buf);
          next.set(value, buf.length);
          buf = next;

          let start: number | undefined;
          let idx: number;

          while ((idx = findSequence(buf, BOUNDARY, start)) !== -1) {
            const headerEnd = findSequence(buf, '\r\n\r\n', idx);
            if (headerEnd === -1) break;

            const nextBoundary = findSequence(buf, BOUNDARY, headerEnd);
            if (nextBoundary === -1) break;

            const jpegStart = headerEnd + 4;
            const jpegEnd = nextBoundary - 2;
            if (jpegEnd <= jpegStart) {
              start = nextBoundary + BOUNDARY.length;
              continue;
            }

            const jpegData = buf.slice(jpegStart, jpegEnd);

            if (urlRef.current) URL.revokeObjectURL(urlRef.current);
            const blob = new Blob([jpegData], { type: 'image/jpeg' });
            const blobUrl = URL.createObjectURL(blob);
            urlRef.current = blobUrl;

            if (!cancelled) {
              setFrameUrl(blobUrl);
              setLive(true);
              setError(false);
            }

            buf = buf.slice(nextBoundary);
            start = undefined;
          }
        }
      } catch (e) {
        if (!cancelled && !(e instanceof DOMException && (e as DOMException).name === 'AbortError')) {
          setError(true);
          setLive(false);
        }
      }
    };

    run();

    return () => {
      cancelled = true;
      stop();
    };
  }, [url, active, stop]);

  return { frameUrl, live, error };
}

function findSequence(buf: Uint8Array, seq: string, fromIndex?: number): number {
  const bytes = new TextEncoder().encode(seq);
  const start = fromIndex ?? 0;
  for (let i = start; i <= buf.length - bytes.length; i++) {
    let match = true;
    for (let j = 0; j < bytes.length; j++) {
      if (buf[i + j] !== bytes[j]) {
        match = false;
        break;
      }
    }
    if (match) return i;
  }
  return -1;
}
