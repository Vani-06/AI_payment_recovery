"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { api, ApiClientError } from "./api";
import type { Mode, RunSummary } from "./types";

interface RunState {
  seed: number;
  mode: Mode;
  baseline: boolean;
  running: boolean;
  error: string | null;
  lastRun: RunSummary | null;
  /** bumped after every successful run — screens key their refetch off this */
  version: number;
  setSeed: (n: number) => void;
  setMode: (m: Mode) => void;
  setBaseline: (b: boolean) => void;
  runNow: () => Promise<void>;
}

const Ctx = createContext<RunState | null>(null);

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [seed, setSeed] = useState(7);
  const [mode, setMode] = useState<Mode>("auto");
  const [baseline, setBaseline] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<RunSummary | null>(null);
  const [version, setVersion] = useState(0);

  const runNow = useCallback(async () => {
    setRunning(true);
    setError(null);
    try {
      const r = await api.run({ seed, mode, baseline });
      setLastRun(r);
      setVersion((v) => v + 1);
    } catch (e) {
      setError(
        e instanceof ApiClientError
          ? `${e.status} ${e.code}: ${e.message}`
          : "Cannot reach the API — is the backend running on :8000?",
      );
    } finally {
      setRunning(false);
    }
  }, [seed, mode, baseline]);

  return (
    <Ctx.Provider
      value={{ seed, mode, baseline, running, error, lastRun, version, setSeed, setMode, setBaseline, runNow }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useRun(): RunState {
  const c = useContext(Ctx);
  if (!c) throw new Error("useRun must be used inside <RunProvider>");
  return c;
}
