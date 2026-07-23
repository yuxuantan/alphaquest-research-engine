import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, normalizeBootstrap, unwrapArray } from "./api";
import type { BootstrapResponse } from "./types";

interface StudioState {
  data: BootstrapResponse;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const empty: BootstrapResponse = {
  drafts: [],
  campaigns: [],
  reviews: [],
  jobs: [],
};
const Context = createContext<StudioState>({
  data: empty,
  loading: true,
  error: null,
  refresh: async () => undefined,
});

export function StudioProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<BootstrapResponse>(empty);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const activeJobIds = useRef<Set<string>>(new Set());
  const refresh = useCallback(async () => {
    try {
      const result = normalizeBootstrap(await api.bootstrap());
      setData(result);
      setError(null);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The local Studio service is unavailable.",
      );
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    const pollJobs = async () => {
      try {
        const raw = await api.jobs();
        const jobs = unwrapArray(raw, "jobs").map((job) => ({
          ...job,
          state: job.state || job.operational_state || "NOT_QUEUED",
        }));
        const nextActive = new Set(
          jobs
            .filter((job) =>
              ["QUEUED", "RUNNING", "CANCEL_REQUESTED"].includes(job.state),
            )
            .map((job) => job.job_id),
        );
        const reachedTerminal = [...activeJobIds.current].some(
          (id) => !nextActive.has(id),
        );
        activeJobIds.current = nextActive;
        setData((current) => ({ ...current, jobs }));
        if (reachedTerminal) void refresh();
      } catch {
        // Bootstrap errors already own the visible service banner. A single
        // failed queue poll must not erase the last known durable job state.
      }
    };
    const timer = window.setInterval(() => void pollJobs(), 4_000);
    return () => window.clearInterval(timer);
  }, [refresh]);
  const value = useMemo(
    () => ({ data, loading, error, refresh }),
    [data, loading, error, refresh],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export const useStudio = () => useContext(Context);

export function useAsyncAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(
    async <T,>(action: () => Promise<T>): Promise<T | undefined> => {
      setBusy(true);
      setError(null);
      try {
        return await action();
      } catch (reason) {
        setError(
          reason instanceof Error
            ? reason.message
            : "The governed action was rejected.",
        );
        return undefined;
      } finally {
        setBusy(false);
      }
    },
    [],
  );
  return { busy, error, setError, run };
}
