import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { authHeaders, handleUnauthorized } from './client';

const EVENTS_URL = '/api/v1/events';
const RECONNECT_MS = 3_000;

export interface Live {
  version: number;
  connected: boolean;
  refresh: () => void;
}

export const LiveContext = createContext<Live>({ version: 0, connected: false, refresh: () => {} });

async function readEvents(signal: AbortSignal, onOpen: () => void, onEvent: (name: string) => void) {
  const res = await fetch(EVENTS_URL, { headers: { ...authHeaders(), Accept: 'text/event-stream' }, signal });
  if (res.status === 401) {
    handleUnauthorized();
    return;
  }
  if (!res.ok || !res.body) throw new Error(`events: ${res.status}`);
  onOpen();

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += value.replace(/\r/g, '');
    let end: number;
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      onEvent(/^event: ?(.*)$/m.exec(block)?.[1] ?? 'message');
    }
  }
}

export function useLiveVersion(enabled: boolean): Live {
  const [version, setVersion] = useState(0);
  const [connected, setConnected] = useState(false);
  const refresh = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    if (!enabled) return;
    const abort = new AbortController();

    (async () => {
      while (!abort.signal.aborted) {
        try {
          await readEvents(
            abort.signal,
            () => setConnected(true),
            (name) => { if (name === 'recalculated') refresh(); },
          );
        } catch {}
        if (abort.signal.aborted) return;
        setConnected(false);
        refresh();
        await new Promise((r) => setTimeout(r, RECONNECT_MS));
      }
    })();

    return () => {
      abort.abort();
      setConnected(false);
    };
  }, [enabled, refresh]);

  return useMemo(() => ({ version, connected, refresh }), [version, connected, refresh]);
}

export function useResource<T>(load: () => Promise<T>, deps: unknown[]) {
  const { version } = useContext(LiveContext);
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    load()
      .then((d) => { if (alive) { setData(d); setError(null); } })
      .catch((e: Error) => { if (alive) setError(e.message); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  return { data, error };
}
