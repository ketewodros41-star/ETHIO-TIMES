"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { eventsApi } from "./api";

interface NewEventsPoll {
  hasNew: boolean;
  newCount: number;
  dismiss: () => void;
  refresh: () => void;
}

/**
 * Polls /api/v1/events/latest-timestamp every 15 seconds.
 * Returns a banner state when new events are detected since the last refresh.
 */
export function useNewEventsPoller(
  onRefresh?: () => void
): NewEventsPoll {
  const lastSeenAt = useRef<string | null>(null);
  const lastSeenCount = useRef<number>(0);
  const [hasNew, setHasNew] = useState(false);
  const [newCount, setNewCount] = useState(0);

  const dismiss = useCallback(() => {
    setHasNew(false);
    setNewCount(0);
  }, []);

  const refresh = useCallback(() => {
    dismiss();
    onRefresh?.();
  }, [dismiss, onRefresh]);

  useEffect(() => {
    let mounted = true;

    const poll = async () => {
      // Don't poll if document is backgrounded or tab is inactive
      if (typeof document !== "undefined" && document.visibilityState === "hidden") {
        return;
      }

      try {
        const data = await eventsApi.latestTimestamp();
        if (!mounted) return;

        // First poll: just record baseline, don't show banner
        if (lastSeenAt.current === null) {
          lastSeenAt.current = data.latest_at;
          lastSeenCount.current = data.total_count;
          return;
        }

        // Check if there are genuinely new events or updated coverage
        const isNewer =
          data.latest_at &&
          lastSeenAt.current &&
          data.latest_at > lastSeenAt.current;

        const countDiff = data.total_count - lastSeenCount.current;

        if (isNewer) {
          setHasNew(true);
          setNewCount(countDiff > 0 ? countDiff : 1);
        }
      } catch {
        // Silently ignore polling errors - network blips shouldn't break the UI
      }
    };

    // Initial poll to set baseline
    poll();

    // Poll every 30 seconds while tab is active
    const interval = setInterval(poll, 30_000);

    // Immediately poll when returning from another tab
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        poll();
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      mounted = false;
      clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { hasNew, newCount, dismiss, refresh };
}
