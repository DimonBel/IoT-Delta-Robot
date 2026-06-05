import { useState, useCallback } from 'react';

export function useTweaks<T extends object>(
  defaults: T,
): [T, (keyOrEdits: string | Partial<T>, val?: unknown) => void] {
  const [values, setValues] = useState<T>(defaults);

  const setTweak = useCallback(
    (keyOrEdits: string | Partial<T>, val?: unknown) => {
      const edits: Partial<T> =
        typeof keyOrEdits === 'object' && keyOrEdits !== null
          ? keyOrEdits
          : ({ [keyOrEdits as string]: val } as Partial<T>);
      setValues((prev) => ({ ...prev, ...edits }));
    },
    [],
  );

  return [values, setTweak];
}
